create extension if not exists "pgcrypto";

create table if not exists public.trade_diagnostics_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  batch_id text not null,
  filename text not null,
  broker text,
  detected_format text,
  imported_at timestamptz not null default now(),
  coverage_text text,
  diagnostics_json jsonb not null,
  ai_analysis_json jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_trade_diagnostics_history_user_imported_at
  on public.trade_diagnostics_history (user_id, imported_at desc);

alter table public.trade_diagnostics_history enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'trade_diagnostics_history'
      and policyname = 'users_select_own_trade_history'
  ) then
    create policy users_select_own_trade_history
      on public.trade_diagnostics_history
      for select
      to authenticated
      using (auth.uid() = user_id);
  end if;
end $$;

-- ============================================================
-- A-share trading calendar used by free-trial accounting.
-- Store only real trading dates. Do not infer from weekdays here; this table
-- must be seeded from an A-share calendar source such as AKShare.
-- ============================================================

create table if not exists public.a_share_trade_calendar (
  trade_date date primary key,
  source text not null default 'akshare',
  created_at timestamptz not null default now()
);

create index if not exists idx_a_share_trade_calendar_trade_date
  on public.a_share_trade_calendar (trade_date);

-- Trial policy singleton. The first time this schema is deployed, this captures
-- the rollout timestamp. Only auth.users created at/after this timestamp are
-- eligible for the new-user trial, so existing customers/users are not changed.
create table if not exists public.access_policy (
  id boolean primary key default true check (id),
  new_user_trial_enabled_at timestamptz not null default now(),
  trial_trade_days int not null default 3 check (trial_trade_days > 0),
  updated_at timestamptz not null default now()
);

insert into public.access_policy (id)
values (true)
on conflict (id) do nothing;

create or replace function public.is_new_user_trial_eligible(p_user_created_at timestamptz)
returns boolean
language plpgsql
stable
as $$
declare
  v_enabled_at timestamptz;
begin
  if p_user_created_at is null then
    return false;
  end if;
  select new_user_trial_enabled_at
    into v_enabled_at
    from public.access_policy
   where id = true;
  return v_enabled_at is not null and p_user_created_at >= v_enabled_at;
end;
$$;

-- ============================================================
-- Email invite codes: one unique code per registered email.
-- Simplified flow (no email-confirmation dependency):
--   1) User signs up with email + password (auth.users row created).
--   2) A trigger IMMEDIATELY inserts a unique invite code for that
--      email on auth.users INSERT -- regardless of whether Supabase
--      "Confirm email" is on or off. Admins read the code from
--      v_email_invite_codes_all in the backend.
--   3) User purchases and receives the code out-of-band.
--   4) User logs in with email + password, then enters the code;
--      frontend calls redeem_email_invite_code to mark it used and
--      grant access via user_has_email_invite_access.
-- ============================================================

create table if not exists public.email_invite_codes (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  code text not null unique,
  status text not null default 'active' check (status in ('active','used','disabled')),
  created_at timestamptz not null default now(),
  used_at timestamptz,
  used_by uuid references auth.users(id) on delete set null,
  trial_eligible boolean not null default false,
  trial_started_at timestamptz
);

-- Defensive: ensure required columns exist even if a pre-existing table
-- was created with an older / partial schema (avoids 42703 on index below).
alter table public.email_invite_codes add column if not exists email text;
alter table public.email_invite_codes add column if not exists code text;
alter table public.email_invite_codes add column if not exists status text not null default 'active';
alter table public.email_invite_codes add column if not exists created_at timestamptz not null default now();
alter table public.email_invite_codes add column if not exists used_at timestamptz;
alter table public.email_invite_codes add column if not exists used_by uuid references auth.users(id) on delete set null;
-- Free-trial support:
--   - Existing rows default to trial_eligible=false, so old users do not
--     receive a retroactive trial.
--   - New auth.users INSERT rows are marked trial_eligible=true by the trigger
--     below.
--   - trial_started_at remains NULL until the user's first authenticated
--     access check, which is effectively their first login/session use.
alter table public.email_invite_codes add column if not exists trial_eligible boolean not null default false;
alter table public.email_invite_codes add column if not exists trial_started_at timestamptz;
alter table public.email_invite_codes alter column trial_eligible set default false;
update public.email_invite_codes
   set trial_eligible = false
 where trial_eligible is null;
alter table public.email_invite_codes alter column trial_eligible set not null;

-- If this schema is applied over an earlier partial trial implementation,
-- explicitly keep pre-rollout users out of the new-user trial cohort.
update public.email_invite_codes c
   set trial_eligible = false
  from auth.users u, public.access_policy p
 where lower(u.email) = lower(c.email)
   and p.id = true
   and u.created_at < p.new_user_trial_enabled_at;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'email_invite_codes_status_check'
      and conrelid = 'public.email_invite_codes'::regclass
  ) then
    alter table public.email_invite_codes
      add constraint email_invite_codes_status_check
      check (status in ('active','used','disabled'));
  end if;
  if not exists (
    select 1 from pg_indexes
    where schemaname = 'public' and indexname = 'email_invite_codes_email_key'
  ) and not exists (
    select 1 from pg_constraint
    where conname = 'email_invite_codes_email_key'
      and conrelid = 'public.email_invite_codes'::regclass
  ) then
    begin
      alter table public.email_invite_codes add constraint email_invite_codes_email_key unique (email);
    exception when others then null;
    end;
  end if;
  if not exists (
    select 1 from pg_indexes
    where schemaname = 'public' and indexname = 'email_invite_codes_code_key'
  ) and not exists (
    select 1 from pg_constraint
    where conname = 'email_invite_codes_code_key'
      and conrelid = 'public.email_invite_codes'::regclass
  ) then
    begin
      alter table public.email_invite_codes add constraint email_invite_codes_code_key unique (code);
    exception when others then null;
    end;
  end if;
end $$;

create index if not exists idx_email_invite_codes_email on public.email_invite_codes (lower(email));
create index if not exists idx_email_invite_codes_code on public.email_invite_codes (code);

-- Defensive: older versions of this table may contain extra NOT NULL columns
-- (e.g. target_email, target_user_id). Relax NOT NULL on any legacy column
-- that is not part of the current schema so inserts don't break.
do $$
declare
  r record;
  known_cols text[] := array['id','email','code','status','created_at','used_at','used_by','trial_eligible','trial_started_at'];
begin
  for r in
    select column_name
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'email_invite_codes'
      and is_nullable = 'NO'
      and column_default is null
      and not (column_name = any(known_cols))
  loop
    execute format('alter table public.email_invite_codes alter column %I drop not null', r.column_name);
  end loop;
end $$;

alter table public.email_invite_codes enable row level security;

-- Deny all direct table access from anon/authenticated clients.
-- All reads/writes must go through SECURITY DEFINER RPCs below.
do $$
begin
  if exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'email_invite_codes'
  ) then
    -- no-op: keep existing policies
    null;
  end if;
end $$;

-- Generate a human-friendly unique code: INVAC + 8 hex chars.
create or replace function public.generate_email_invite_code()
returns text
language plpgsql
as $$
declare
  v_code text;
  v_tries int := 0;
begin
  loop
    v_code := 'INVAC' || upper(substr(encode(gen_random_bytes(4), 'hex'), 1, 8));
    exit when not exists (select 1 from public.email_invite_codes where code = v_code);
    v_tries := v_tries + 1;
    if v_tries > 8 then
      raise exception 'failed to generate unique invite code';
    end if;
  end loop;
  return v_code;
end;
$$;

-- Trigger function: insert a code row for every new auth.users email.
-- No longer depends on email_confirmed_at, so the flow works the same
-- whether Supabase "Confirm email" is enabled or disabled.
-- IMPORTANT: this trigger must NEVER raise — if it does, the whole
-- auth.users insert is rolled back and the user sees "Database error
-- saving new user". Any failure to generate / insert the invite code
-- is swallowed; the backfill statement below (re-run this schema) or
-- the self-heal RPC `ensure_invite_code_for_email` will pick it up.
create or replace function public.ensure_invite_code_for_confirmed_email()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_trial_eligible boolean;
begin
  begin
    v_email := lower(coalesce(new.email, ''));
    if v_email = '' then
      return new;
    end if;
    v_trial_eligible := public.is_new_user_trial_eligible(new.created_at);
    -- New signup: create invite-code row and mark it eligible for the
    -- 3-trading-day trial. Do not start the trial here; it starts on the
    -- first authenticated access check after login.
    insert into public.email_invite_codes (email, code, trial_eligible)
    values (v_email, public.generate_email_invite_code(), v_trial_eligible)
    on conflict (email) do nothing;
  exception when others then
    -- Never block auth.users insert; log and continue.
    raise warning 'ensure_invite_code_for_confirmed_email failed for %: %', new.email, sqlerrm;
  end;
  return new;
end;
$$;

drop trigger if exists trg_ensure_invite_code_on_users on auth.users;
create trigger trg_ensure_invite_code_on_users
after insert or update of email on auth.users
for each row execute function public.ensure_invite_code_for_confirmed_email();

-- Backfill: every existing auth user (confirmed or not) gets a code, but no
-- retroactive trial. Existing paid/unlocked users continue to rely on
-- status='used'; old non-paid users remain locked until they redeem a code.
insert into public.email_invite_codes (email, code, trial_eligible)
select lower(u.email), public.generate_email_invite_code(), false
from auth.users u
where u.email is not null
  and not exists (
    select 1 from public.email_invite_codes c where c.email = lower(u.email)
  );

-- Self-heal RPC: callable by the signed-in user to (re)ensure their own
-- invite code exists. Use this if the trigger was ever skipped for them.
-- SECURITY: p_email is ignored for authorization; we always read the
-- caller's email from auth.users via auth.uid() to prevent any client
-- from provisioning/hijacking a code for a different email.
drop function if exists public.ensure_invite_code_for_email(text);
create or replace function public.ensure_invite_code_for_email(p_email text default null)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_email text;
  v_code  text;
  v_user_created_at timestamptz;
  v_trial_eligible boolean := false;
begin
  if v_uid is null then
    return jsonb_build_object('ok', false, 'reason', 'not_authenticated');
  end if;
  select lower(email), created_at into v_email, v_user_created_at from auth.users where id = v_uid;
  if v_email is null or v_email = '' then
    return jsonb_build_object('ok', false, 'reason', 'missing_email');
  end if;
  v_trial_eligible := public.is_new_user_trial_eligible(v_user_created_at);
  select code into v_code from public.email_invite_codes where email = v_email;
  if v_code is null then
    -- Missing rows at runtime are normally users whose trigger did not
    -- complete. Eligibility is still guarded by the rollout cutoff.
    insert into public.email_invite_codes (email, code, trial_eligible)
    values (v_email, public.generate_email_invite_code(), v_trial_eligible)
    on conflict (email) do nothing;
    select code into v_code from public.email_invite_codes where email = v_email;
  end if;
  return jsonb_build_object('ok', true, 'code', v_code);
end;
$$;

grant execute on function public.ensure_invite_code_for_email(text) to authenticated;

-- RPC: redeem a code for the caller's email.
-- Returns jsonb: { ok: bool, reason?: text }
-- SECURITY: the email to check against is read from auth.users via
-- auth.uid(). The p_email parameter is kept for backward compatibility
-- with older clients but is NOT trusted for authorization.
-- Drop first in case an older version exists with different parameter names
-- (PostgreSQL error 42P13: cannot change name of input parameter).
drop function if exists public.redeem_email_invite_code(text, text);
drop function if exists public.redeem_email_invite_code(text);
create or replace function public.redeem_email_invite_code(p_code text, p_email text default null)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_email text;
  v_raw  text := coalesce(p_code, '');
  v_code text;
  v_row public.email_invite_codes%rowtype;
begin
  -- Normalize aggressively: strip every whitespace (incl. nbsp/ZWSP/tab/newline)
  -- and typographic punctuation often introduced by copy/paste from email or IM.
  -- This prevents false "invalid_code" when users paste "INVAC 1234 5678" or
  -- "INVAC-12345678" or the code surrounded by quotes / smart quotes.
  v_raw := regexp_replace(v_raw, '[[:space:]]+', '', 'g');
  v_raw := replace(v_raw, chr(160),    ''); -- NBSP
  v_raw := replace(v_raw, chr(8203),   ''); -- ZERO WIDTH SPACE
  v_raw := replace(v_raw, chr(8204),   ''); -- ZWNJ
  v_raw := replace(v_raw, chr(8205),   ''); -- ZWJ
  v_raw := replace(v_raw, chr(8206),   ''); -- LRM
  v_raw := replace(v_raw, chr(8207),   ''); -- RLM
  v_raw := replace(v_raw, chr(65279),  ''); -- BOM / ZERO WIDTH NO-BREAK SPACE
  v_raw := regexp_replace(v_raw, '[''"`\-_]', '', 'g');
  v_code := upper(v_raw);

  if v_uid is null then
    return jsonb_build_object('ok', false, 'reason', 'not_authenticated');
  end if;
  select lower(email) into v_email from auth.users where id = v_uid;
  if v_email is null or v_email = '' then
    return jsonb_build_object('ok', false, 'reason', 'missing_email');
  end if;
  if v_code = '' then
    return jsonb_build_object('ok', false, 'reason', 'missing_code');
  end if;

  -- Case-insensitive code lookup (belt-and-suspenders; codes are uppercase by
  -- generation, but admin-inserted or legacy rows may not be).
  select * into v_row from public.email_invite_codes where upper(code) = v_code;
  if not found then
    return jsonb_build_object('ok', false, 'reason', 'invalid_code');
  end if;

  if v_row.status = 'disabled' then
    return jsonb_build_object('ok', false, 'reason', 'already_used_or_disabled');
  end if;

  if lower(v_row.email) <> v_email then
    -- Surface the currently signed-in email (the one enforced by the server)
    -- so the user can tell whether they're logged into the wrong account.
    return jsonb_build_object(
      'ok', false,
      'reason', 'email_code_not_match',
      'user_email', v_email
    );
  end if;

  if v_row.status = 'used' then
    -- Idempotent unlock for the legitimate owner.
    if v_row.used_by is distinct from v_uid then
      update public.email_invite_codes
         set used_by = v_uid
       where id = v_row.id;
    end if;
    return jsonb_build_object('ok', true);
  end if;

  update public.email_invite_codes
     set status = 'used',
         used_at = now(),
         used_by = v_uid
   where id = v_row.id;

  return jsonb_build_object('ok', true);
end;
$$;

grant execute on function public.redeem_email_invite_code(text, text) to authenticated;

-- ============================================================
-- Free-trial helpers (3 real A-share trading days from first login).
-- The trial window is counted from the first authenticated access check, using
-- public.a_share_trade_calendar. If the calendar has not been seeded, new
-- users are not charged a trial day and access remains locked until the
-- calendar is imported.
-- ============================================================

create or replace function public.a_share_trade_calendar_ready()
returns boolean
language plpgsql
stable
as $$
declare
  v_today date := (now() at time zone 'Asia/Shanghai')::date;
  v_ready boolean;
begin
  select exists (
    select 1
    from public.a_share_trade_calendar
    where trade_date >= v_today
  ) into v_ready;
  return coalesce(v_ready, false);
end;
$$;

create or replace function public.next_a_share_trade_day(d date)
returns date
language plpgsql
stable
as $$
declare
  out_d date;
begin
  if d is null then
    return null;
  end if;
  select trade_date
    into out_d
    from public.a_share_trade_calendar
   where trade_date >= d
   order by trade_date
   limit 1;
  return out_d;
end;
$$;

create or replace function public.add_a_share_trade_days(start_dt date, n int)
returns date
language plpgsql
stable
as $$
declare
  out_d date;
begin
  if start_dt is null then
    return null;
  end if;
  select trade_date
    into out_d
    from public.a_share_trade_calendar
   where trade_date >= start_dt
   order by trade_date
   offset greatest(coalesce(n, 0), 0)
   limit 1;
  return out_d;
end;
$$;

create or replace function public.trial_a_share_trade_ends_on(p_trial_started_at timestamptz)
returns date
language plpgsql
stable
as $$
declare
  v_start date;
  v_trade_days int := 3;
begin
  if p_trial_started_at is null then
    return null;
  end if;
  select coalesce(trial_trade_days, 3)
    into v_trade_days
    from public.access_policy
   where id = true;
  v_start := public.next_a_share_trade_day((p_trial_started_at at time zone 'Asia/Shanghai')::date);
  return public.add_a_share_trade_days(v_start, greatest(v_trade_days, 1) - 1);
end;
$$;

-- How many A-share trading days remain in the user's free trial.
-- Trial window: [effective_start, effective_start + 2 A-share trading days]
-- where effective_start = first real trading day on/after trial_started_at.
-- Returns 0 when expired, not started, or the trading calendar is unavailable.
create or replace function public.trial_a_share_trade_days_left(p_trial_started_at timestamptz)
returns int
language plpgsql
stable
as $$
declare
  v_start date;
  v_end date;
  v_today date := (now() at time zone 'Asia/Shanghai')::date;
  v_left int;
begin
  if p_trial_started_at is null then
    return 0;
  end if;
  v_start := public.next_a_share_trade_day((p_trial_started_at at time zone 'Asia/Shanghai')::date);
  v_end := public.trial_a_share_trade_ends_on(p_trial_started_at);
  if v_start is null or v_end is null or v_today > v_end then
    return 0;
  end if;

  select count(*)::int
    into v_left
    from public.a_share_trade_calendar
   where trade_date between greatest(v_today, v_start) and v_end;

  return coalesce(v_left, 0);
end;
$$;

-- Backward-compatible names retained for older SQL/views. They now mean
-- "A-share trading day", not generic weekday.
create or replace function public.next_business_day(d date)
returns date
language sql
stable
as $$
  select public.next_a_share_trade_day(d);
$$;

create or replace function public.add_business_days(start_dt date, n int)
returns date
language sql
stable
as $$
  select public.add_a_share_trade_days(start_dt, n);
$$;

create or replace function public.trial_business_days_left(p_trial_started_at timestamptz)
returns int
language sql
stable
as $$
  select public.trial_a_share_trade_days_left(p_trial_started_at);
$$;

-- Unified access-state RPC for the frontend. Returns:
--   { ok: bool,
--     access: bool,               -- true => user may view paid content
--     mode: 'paid'|'trial'|'none',
--     trial_started_at: timestamptz,
--     trial_ends_on: date,        -- last trading day included in trial
--     trial_days_left: int,       -- A-share trading days including today
--     trial_eligible: bool,
--     trial_calendar_ready: bool,
--     redeemed: bool              -- true when an invite code has been used
--   }
drop function if exists public.get_user_access_state();
create or replace function public.get_user_access_state()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_email text;
  v_user_created_at timestamptz;
  v_row public.email_invite_codes%rowtype;
  v_end date;
  v_days_left int := 0;
  v_redeemed boolean;
  v_access boolean := false;
  v_mode text := 'none';
  v_calendar_ready boolean := public.a_share_trade_calendar_ready();
  v_reason text;
begin
  if v_uid is null then
    return jsonb_build_object('ok', false, 'access', false, 'mode', 'none', 'reason', 'not_authenticated');
  end if;
  select lower(email), created_at into v_email, v_user_created_at from auth.users where id = v_uid;
  if v_email is null or v_email = '' then
    return jsonb_build_object('ok', false, 'access', false, 'mode', 'none', 'reason', 'missing_email');
  end if;

  -- Ensure a row exists (self-heal) before reading. Missing runtime rows are
  -- guarded by the rollout cutoff before becoming trial-eligible.
  insert into public.email_invite_codes (email, code, trial_eligible)
  values (v_email, public.generate_email_invite_code(), public.is_new_user_trial_eligible(v_user_created_at))
  on conflict (email) do nothing;

  select * into v_row from public.email_invite_codes where email = v_email;

  v_redeemed := v_row.status = 'used';

  if v_redeemed then
    v_access := true;
    v_mode := 'paid';
  elsif coalesce(v_row.trial_eligible, false) then
    if not v_calendar_ready then
      v_reason := 'trade_calendar_missing';
    else
      -- First login/session-use activation: start only once.
      if v_row.trial_started_at is null then
        update public.email_invite_codes
           set trial_started_at = now()
         where id = v_row.id
         returning * into v_row;
      end if;

      v_days_left := public.trial_a_share_trade_days_left(v_row.trial_started_at);
      v_end := public.trial_a_share_trade_ends_on(v_row.trial_started_at);

      if v_days_left > 0 then
        v_access := true;
        v_mode := 'trial';
      else
        v_reason := 'trial_expired';
      end if;
    end if;
  else
    v_reason := 'trial_not_eligible';
  end if;

  return jsonb_build_object(
    'ok', true,
    'access', v_access,
    'mode', v_mode,
    'reason', v_reason,
    'trial_started_at', v_row.trial_started_at,
    'trial_ends_on', v_end,
    'trial_days_left', v_days_left,
    'trial_eligible', coalesce(v_row.trial_eligible, false),
    'trial_calendar_ready', v_calendar_ready,
    'redeemed', v_redeemed
  );
end;
$$;

grant execute on function public.get_user_access_state() to authenticated;

-- ============================================================
-- Legacy boolean RPC — returns true when user has EITHER a redeemed
-- invite code OR an active free trial. Prefer get_user_access_state
-- from new client code for the detailed trial metadata.
-- SECURITY: email is read from auth.users via auth.uid(); p_email is
-- accepted for backward compatibility but ignored for authorization.
drop function if exists public.user_has_email_invite_access(text);
create or replace function public.user_has_email_invite_access(p_email text default null)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_email text;
  v_user_created_at timestamptz;
  v_row public.email_invite_codes%rowtype;
begin
  if v_uid is null then
    return false;
  end if;
  select lower(email), created_at into v_email, v_user_created_at from auth.users where id = v_uid;
  if v_email is null or v_email = '' then
    return false;
  end if;
  select * into v_row from public.email_invite_codes where email = v_email;
  if not found then
    insert into public.email_invite_codes (email, code, trial_eligible)
    values (v_email, public.generate_email_invite_code(), public.is_new_user_trial_eligible(v_user_created_at))
    on conflict (email) do nothing;
    select * into v_row from public.email_invite_codes where email = v_email;
  end if;
  if v_row.status = 'used' then
    return true;
  end if;
  if not coalesce(v_row.trial_eligible, false) or not public.a_share_trade_calendar_ready() then
    return false;
  end if;
  if v_row.trial_started_at is null then
    update public.email_invite_codes
       set trial_started_at = now()
     where id = v_row.id
     returning * into v_row;
  end if;
  return public.trial_a_share_trade_days_left(v_row.trial_started_at) > 0;
end;
$$;

grant execute on function public.user_has_email_invite_access(text) to authenticated;

-- Convenience view used by admin UI: list of unused (active) codes.
-- Drop first in case an older version exists with different columns
-- (PostgreSQL error 42P16: cannot drop columns from view via CREATE OR REPLACE).
drop view if exists public.v_email_invite_codes_unused;
create or replace view public.v_email_invite_codes_unused as
select id, email, code, status, created_at, trial_eligible, trial_started_at
from public.email_invite_codes
where status = 'active';

-- Admin convenience view: every email + its single bound code + current status.
-- Useful when checking whether a user's email has been issued a code.
drop view if exists public.v_email_invite_codes_all;
create or replace view public.v_email_invite_codes_all as
select
  c.id,
  c.email,
  c.code,
  c.status,
  c.created_at,
  c.used_at,
  c.used_by,
  c.trial_eligible,
  c.trial_started_at,
  case
    when c.trial_eligible then public.trial_a_share_trade_days_left(c.trial_started_at)
    else 0
  end as trial_days_left,
  case
    when c.trial_eligible then public.trial_a_share_trade_ends_on(c.trial_started_at)
    else null
  end as trial_ends_on,
  u.id as auth_user_id,
  u.email_confirmed_at
from public.email_invite_codes c
left join auth.users u on lower(u.email) = lower(c.email);

-- One-time data heal: re-link used_by for historic rows where the FK was
-- cleared (used_by NULL after user deletion) or where the uid no longer
-- exists. We bind by email so legitimate owners keep unlocked access.
update public.email_invite_codes c
   set used_by = u.id
  from auth.users u
 where c.status = 'used'
   and lower(u.email) = lower(c.email)
   and (c.used_by is null or c.used_by <> u.id);
