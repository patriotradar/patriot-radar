-- Full setup for TikTok trend intelligence feed (idempotent).
-- Run once in Supabase SQL Editor OR via: python scripts/apply_trend_feed_schema.py

create table if not exists public.trend_intelligence_feed (
  id uuid primary key default gen_random_uuid(),
  timestamp timestamptz not null default now(),
  source text not null default 'tiktok',
  type text not null check (type in ('hook', 'format', 'emotion', 'topic', 'keyword_cluster')),
  signal_strength integer not null default 0 check (signal_strength >= 0 and signal_strength <= 100),
  virality_score integer not null default 0 check (virality_score >= 0 and virality_score <= 100),
  trend_state text not null default 'emerging'
    check (trend_state in ('emerging', 'rising', 'peaking', 'fading')),
  raw_data jsonb not null default '{}'::jsonb,
  summary text not null default '',
  dedupe_key text not null,
  unique (dedupe_key)
);

-- Backfill column if table existed before virality_score was added.
alter table public.trend_intelligence_feed
  add column if not exists virality_score integer not null default 0
  check (virality_score >= 0 and virality_score <= 100);

create index if not exists trend_intelligence_feed_timestamp_idx
  on public.trend_intelligence_feed (timestamp desc);

create index if not exists trend_intelligence_feed_source_type_idx
  on public.trend_intelligence_feed (source, type);

create index if not exists trend_intelligence_feed_trend_state_idx
  on public.trend_intelligence_feed (trend_state);

create index if not exists trend_intelligence_feed_virality_idx
  on public.trend_intelligence_feed (virality_score desc);

alter table public.trend_intelligence_feed enable row level security;

drop policy if exists "Authenticated users read trend intelligence feed"
  on public.trend_intelligence_feed;
create policy "Authenticated users read trend intelligence feed"
  on public.trend_intelligence_feed
  for select
  to authenticated
  using (true);

drop policy if exists "Authenticated users insert trend intelligence feed"
  on public.trend_intelligence_feed;
create policy "Authenticated users insert trend intelligence feed"
  on public.trend_intelligence_feed
  for insert
  to authenticated
  with check (true);

drop policy if exists "Authenticated users update trend intelligence feed"
  on public.trend_intelligence_feed;
create policy "Authenticated users update trend intelligence feed"
  on public.trend_intelligence_feed
  for update
  to authenticated
  using (true)
  with check (true);

-- Backfill virality from raw_data for legacy rows.
update public.trend_intelligence_feed
set virality_score = coalesce(
  (raw_data->>'virality_score')::integer,
  round(((raw_data->'virality'->>'viral_strength_score')::numeric) * 100)::integer,
  signal_strength,
  0
)
where virality_score = 0
  and (
    raw_data ? 'virality_score'
    or raw_data->'virality' ? 'viral_strength_score'
  );
