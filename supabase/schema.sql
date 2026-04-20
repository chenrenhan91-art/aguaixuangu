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

create table if not exists public.invite_codes (
  id uuid primary key default gen_random_uuid(),
  code_hash text not null unique,
  code_prefix text not null,
  max_uses integer not null default 1 check (max_uses > 0),
  used_count integer not null default 0 check (used_count >= 0),
  expires_at timestamptz,
  disabled_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_invite_codes_code_prefix
  on public.invite_codes (code_prefix);

create table if not exists public.invite_claims (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  invite_code_id uuid not null references public.invite_codes(id) on delete restrict,
  claimed_at timestamptz not null default now(),
  activated_at timestamptz,
  revoked_at timestamptz
);

create index if not exists idx_invite_claims_invite_code_id
  on public.invite_claims (invite_code_id);

create index if not exists idx_invite_claims_revoked_at
  on public.invite_claims (revoked_at);

alter table public.invite_codes enable row level security;
alter table public.invite_claims enable row level security;

create or replace function public.normalize_invite_code(raw_code text)
returns text
language sql
immutable
as $$
  select upper(regexp_replace(trim(coalesce(raw_code, '')), '[-[:space:]]+', '', 'g'));
$$;

create or replace function public.hash_invite_code(raw_code text)
returns text
language sql
immutable
as $$
  select encode(digest(public.normalize_invite_code(raw_code), 'sha256'), 'hex');
$$;

create or replace function public.reserve_invite_code_for_new_user(event jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  next_user_id uuid;
  next_email text;
  normalized_code text;
  hashed_code text;
  invite_row public.invite_codes%rowtype;
begin
  next_user_id := nullif(event->'user'->>'id', '')::uuid;
  next_email := lower(trim(coalesce(event->'user'->>'email', '')));
  normalized_code := public.normalize_invite_code(event->'user'->'user_metadata'->>'invite_code');

  if next_user_id is null then
    return jsonb_build_object('error', jsonb_build_object('http_code', 400, 'message', '注册失败：无法生成用户标识。'));
  end if;

  if next_email = '' then
    return jsonb_build_object('error', jsonb_build_object('http_code', 400, 'message', '注册失败：邮箱不能为空。'));
  end if;

  if normalized_code = '' then
    return jsonb_build_object('error', jsonb_build_object('http_code', 400, 'message', '注册失败：请输入邀请码。'));
  end if;

  hashed_code := public.hash_invite_code(normalized_code);

  select *
  into invite_row
  from public.invite_codes
  where code_hash = hashed_code
  for update;

  if not found then
    return jsonb_build_object('error', jsonb_build_object('http_code', 400, 'message', '注册失败：邀请码无效。'));
  end if;

  if invite_row.disabled_at is not null then
    return jsonb_build_object('error', jsonb_build_object('http_code', 403, 'message', '注册失败：邀请码已停用。'));
  end if;

  if invite_row.expires_at is not null and invite_row.expires_at <= now() then
    return jsonb_build_object('error', jsonb_build_object('http_code', 403, 'message', '注册失败：邀请码已过期。'));
  end if;

  if invite_row.used_count >= invite_row.max_uses then
    return jsonb_build_object('error', jsonb_build_object('http_code', 409, 'message', '注册失败：邀请码已被使用。'));
  end if;

  update public.invite_codes
  set used_count = used_count + 1
  where id = invite_row.id;

  insert into public.invite_claims (user_id, email, invite_code_id)
  values (next_user_id, next_email, invite_row.id)
  on conflict (user_id) do update
    set email = excluded.email,
        invite_code_id = excluded.invite_code_id,
        claimed_at = now(),
        activated_at = null,
        revoked_at = null;

  return '{}'::jsonb;
end;
$$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.reserve_invite_code_for_new_user(jsonb) to supabase_auth_admin;
revoke execute on function public.reserve_invite_code_for_new_user(jsonb) from anon, authenticated, public;

create or replace function public.release_stale_invite_claim(target_user_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  claim_row public.invite_claims%rowtype;
begin
  select *
  into claim_row
  from public.invite_claims
  where user_id = target_user_id
    and revoked_at is null
  for update;

  if not found then
    return false;
  end if;

  if claim_row.activated_at is not null then
    return false;
  end if;

  update public.invite_codes
  set used_count = greatest(used_count - 1, 0)
  where id = claim_row.invite_code_id;

  update public.invite_claims
  set revoked_at = now()
  where user_id = target_user_id
    and revoked_at is null
    and activated_at is null;

  return true;
end;
$$;

revoke execute on function public.release_stale_invite_claim(uuid) from anon, authenticated, public;
