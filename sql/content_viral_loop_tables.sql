-- Autonomous viral loop tables for content publishing, performance tracking, and strategy learning.
-- Isolated from trend_intelligence_feed and existing pipelines.
-- Run once in Supabase SQL Editor before enabling the viral loop modules.

create table if not exists public.content_queue (
  id uuid primary key default gen_random_uuid(),
  account_id text not null,
  caption text not null default '',
  hashtags text[] not null default '{}',
  hook text not null default '',
  product_name text not null default '',
  status text not null default 'queued'
    check (status in ('queued', 'posted', 'failed')),
  scheduled_time timestamptz,
  dedupe_key text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (dedupe_key)
);

create index if not exists content_queue_account_id_idx
  on public.content_queue (account_id);

create index if not exists content_queue_status_idx
  on public.content_queue (status);

create index if not exists content_queue_scheduled_time_idx
  on public.content_queue (scheduled_time);

create table if not exists public.content_performance (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_queue (id) on delete cascade,
  account_id text not null,
  performance_metrics jsonb not null default '{}'::jsonb,
  timestamp timestamptz not null default now()
);

create index if not exists content_performance_account_id_idx
  on public.content_performance (account_id);

create index if not exists content_performance_content_id_idx
  on public.content_performance (content_id);

create index if not exists content_performance_timestamp_idx
  on public.content_performance (timestamp desc);

create table if not exists public.content_strategy_weights (
  account_id text primary key,
  weights_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.content_queue enable row level security;
alter table public.content_performance enable row level security;
alter table public.content_strategy_weights enable row level security;

create policy "Authenticated users read content queue"
  on public.content_queue
  for select
  to authenticated
  using (true);

create policy "Authenticated users read content performance"
  on public.content_performance
  for select
  to authenticated
  using (true);

create policy "Authenticated users read content strategy weights"
  on public.content_strategy_weights
  for select
  to authenticated
  using (true);

-- Service role bypasses RLS for pipeline writes.
