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
