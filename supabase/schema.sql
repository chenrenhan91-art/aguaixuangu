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
  used_by uuid references auth.users(id) on delete set null
);

-- Defensive: ensure required columns exist even if a pre-existing table
-- was created with an older / partial schema (avoids 42703 on index below).
alter table public.email_invite_codes add column if not exists email text;
alter table public.email_invite_codes add column if not exists code text;
alter table public.email_invite_codes add column if not exists status text not null default 'active';
alter table public.email_invite_codes add column if not exists created_at timestamptz not null default now();
alter table public.email_invite_codes add column if not exists used_at timestamptz;
alter table public.email_invite_codes add column if not exists used_by uuid references auth.users(id) on delete set null;
-- Free-trial support: every registered email automatically gets a 3-trading-day
-- trial window starting from trial_started_at. During the trial the user can
-- view paid content without redeeming an invite code; after the trial expires
-- the content lock returns until they enter a valid invite code.
alter table public.email_invite_codes add column if not exists trial_started_at timestamptz;

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
  known_cols text[] := array['id','email','code','status','created_at','used_at','used_by'];
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
begin
  begin
    v_email := lower(coalesce(new.email, ''));
    if v_email = '' then
      return new;
    end if;
    -- New signup: create invite-code row AND start 3-trading-day trial.
    -- on conflict keeps trial_started_at from a previous row (idempotent).
    insert into public.email_invite_codes (email, code, trial_started_at)
    values (v_email, public.generate_email_invite_code(), now())
    on conflict (email) do update
      set trial_started_at = coalesce(public.email_invite_codes.trial_started_at, excluded.trial_started_at);
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

-- Backfill: every existing auth user (confirmed or not) gets a code.
-- trial_started_at is seeded from auth.users.created_at so pre-existing
-- accounts don't retroactively gain a fresh 3-day trial — their trial is
-- measured from when they actually registered.
insert into public.email_invite_codes (email, code, trial_started_at)
select lower(u.email), public.generate_email_invite_code(), coalesce(u.created_at, now())
from auth.users u
where u.email is not null
  and not exists (
    select 1 from public.email_invite_codes c where c.email = lower(u.email)
  );

-- Backfill trial_started_at for rows that were inserted before this column
-- existed. Use auth.users.created_at when available, otherwise email_invite_codes.created_at.
update public.email_invite_codes c
   set trial_started_at = coalesce(u.created_at, c.created_at, now())
  from auth.users u
 where c.trial_started_at is null
   and lower(u.email) = lower(c.email);

update public.email_invite_codes
   set trial_started_at = coalesce(created_at, now())
 where trial_started_at is null;

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
begin
  if v_uid is null then
    return jsonb_build_object('ok', false, 'reason', 'not_authenticated');
  end if;
  select lower(email) into v_email from auth.users where id = v_uid;
  if v_email is null or v_email = '' then
    return jsonb_build_object('ok', false, 'reason', 'missing_email');
  end if;
  select code into v_code from public.email_invite_codes where email = v_email;
  if v_code is null then
    insert into public.email_invite_codes (email, code, trial_started_at)
    values (v_email, public.generate_email_invite_code(), now())
    on conflict (email) do update
      set trial_started_at = coalesce(public.email_invite_codes.trial_started_at, excluded.trial_started_at);
    select code into v_code from public.email_invite_codes where email = v_email;
  else
    -- Ensure trial_started_at is populated for pre-existing rows (defensive).
    update public.email_invite_codes
       set trial_started_at = coalesce(trial_started_at, now())
     where email = v_email and trial_started_at is null;
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
-- Free-trial helpers (3 trading days from registration).
-- Trading days = Mon–Fri in Asia/Shanghai timezone. Weekends are not
-- counted so a user registering on Saturday still gets 3 full weekdays.
-- This is a deliberate simplification; public holidays are treated as
-- trading days for trial-length accounting (business choice to keep math
-- simple and predictable).
-- ============================================================
create or replace function public.next_business_day(d date)
returns date
language plpgsql
immutable
as $$
declare
  out_d date := d;
begin
  while extract(dow from out_d) in (0, 6) loop
    out_d := out_d + 1;
  end loop;
  return out_d;
end;
$$;

create or replace function public.add_business_days(start_dt date, n int)
returns date
language plpgsql
immutable
as $$
declare
  d date := start_dt;
  added int := 0;
begin
  if n <= 0 then
    return d;
  end if;
  while added < n loop
    d := d + 1;
    if extract(dow from d) not in (0, 6) then
      added := added + 1;
    end if;
  end loop;
  return d;
end;
$$;

-- How many business days remain in the user's free trial.
-- Trial window: [effective_start, effective_start + 2 business days]
-- where effective_start = next_business_day(trial_started_at_date).
-- Returns 0 when expired or trial_started_at is null.
create or replace function public.trial_business_days_left(p_trial_started_at timestamptz)
returns int
language plpgsql
immutable
as $$
declare
  v_start date;
  v_end date;
  v_today date;
  v_left int;
begin
  if p_trial_started_at is null then
    return 0;
  end if;
  v_start := public.next_business_day((p_trial_started_at at time zone 'Asia/Shanghai')::date);
  v_end := public.add_business_days(v_start, 2);
  v_today := (now() at time zone 'Asia/Shanghai')::date;
  if v_today > v_end then
    return 0;
  end if;
  -- Count remaining business days in (v_today, v_end].
  v_left := 0;
  while v_today < v_end loop
    v_today := v_today + 1;
    if extract(dow from v_today) not in (0, 6) then
      v_left := v_left + 1;
    end if;
  end loop;
  -- If today itself is a business day and <= v_end, count it too.
  if extract(dow from (now() at time zone 'Asia/Shanghai')::date) not in (0, 6)
     and (now() at time zone 'Asia/Shanghai')::date <= v_end then
    v_left := v_left + 1;
  end if;
  return v_left;
end;
$$;

-- Unified access-state RPC for the frontend. Returns:
--   { ok: bool,
--     access: bool,               -- true => user may view paid content
--     mode: 'paid'|'trial'|'none',
--     trial_started_at: timestamptz,
--     trial_ends_on: date,        -- last trading day included in trial
--     trial_days_left: int,       -- business days (including today) remaining
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
  v_row public.email_invite_codes%rowtype;
  v_start date;
  v_end date;
  v_days_left int;
  v_redeemed boolean;
  v_access boolean;
  v_mode text;
begin
  if v_uid is null then
    return jsonb_build_object('ok', false, 'access', false, 'mode', 'none', 'reason', 'not_authenticated');
  end if;
  select lower(email) into v_email from auth.users where id = v_uid;
  if v_email is null or v_email = '' then
    return jsonb_build_object('ok', false, 'access', false, 'mode', 'none', 'reason', 'missing_email');
  end if;

  -- Ensure a row exists (self-heal) before reading.
  insert into public.email_invite_codes (email, code, trial_started_at)
  values (v_email, public.generate_email_invite_code(), now())
  on conflict (email) do update
    set trial_started_at = coalesce(public.email_invite_codes.trial_started_at, excluded.trial_started_at);

  select * into v_row from public.email_invite_codes where email = v_email;

  v_redeemed := v_row.status = 'used';
  v_days_left := public.trial_business_days_left(v_row.trial_started_at);

  if v_redeemed then
    v_access := true;
    v_mode := 'paid';
  elsif v_days_left > 0 then
    v_access := true;
    v_mode := 'trial';
  else
    v_access := false;
    v_mode := 'none';
  end if;

  if v_row.trial_started_at is not null then
    v_start := public.next_business_day((v_row.trial_started_at at time zone 'Asia/Shanghai')::date);
    v_end := public.add_business_days(v_start, 2);
  end if;

  return jsonb_build_object(
    'ok', true,
    'access', v_access,
    'mode', v_mode,
    'trial_started_at', v_row.trial_started_at,
    'trial_ends_on', v_end,
    'trial_days_left', v_days_left,
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
  v_row public.email_invite_codes%rowtype;
begin
  if v_uid is null then
    return false;
  end if;
  select lower(email) into v_email from auth.users where id = v_uid;
  if v_email is null or v_email = '' then
    return false;
  end if;
  select * into v_row from public.email_invite_codes where email = v_email;
  if not found then
    return false;
  end if;
  if v_row.status = 'used' then
    return true;
  end if;
  return public.trial_business_days_left(v_row.trial_started_at) > 0;
end;
$$;

grant execute on function public.user_has_email_invite_access(text) to authenticated;

-- Convenience view used by admin UI: list of unused (active) codes.
-- Drop first in case an older version exists with different columns
-- (PostgreSQL error 42P16: cannot drop columns from view via CREATE OR REPLACE).
drop view if exists public.v_email_invite_codes_unused;
create or replace view public.v_email_invite_codes_unused as
select id, email, code, status, created_at
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
  c.trial_started_at,
  public.trial_business_days_left(c.trial_started_at) as trial_days_left,
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
