-- Automation control settings for per-account posting modes.
-- Run once in Supabase SQL Editor before enabling dashboard orchestration.

create table if not exists public.automation_settings (
  account_id text primary key,
  mode text not null default 'queue_only'
    check (mode in ('queue_only', 'approval_required', 'auto_post')),
  updated_at timestamptz not null default now()
);

create index if not exists automation_settings_mode_idx
  on public.automation_settings (mode);

alter table public.automation_settings enable row level security;

create policy "Authenticated users read automation settings"
  on public.automation_settings
  for select
  to authenticated
  using (true);

create policy "Authenticated users update own automation settings"
  on public.automation_settings
  for update
  to authenticated
  using (true)
  with check (true);

create policy "Authenticated users insert automation settings"
  on public.automation_settings
  for insert
  to authenticated
  with check (true);

-- Service role bypasses RLS for pipeline reads/writes.
