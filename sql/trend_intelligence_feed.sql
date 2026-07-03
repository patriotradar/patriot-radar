-- =============================================================================
-- trend_intelligence_feed — idempotent production setup (safe to run repeatedly)
-- =============================================================================
-- Fixes PGRST205 when public.trend_intelligence_feed is missing.
--
-- Schema derived from:
--   trend_intelligence_store.py  (insert/upsert columns, on_conflict dedupe_key)
--   keyword_diversity.py         (select summary, raw_data, type; filter source)
--   dashboard-sync/index.html    (select *; filter source=tiktok; order timestamp)
--
-- Run in Supabase SQL Editor, or: python scripts/apply_trend_feed_schema.py
-- No DROP TABLE. No data loss.

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------
create table if not exists public.trend_intelligence_feed (
  id uuid primary key default gen_random_uuid(),
  timestamp timestamptz not null default now(),
  source text not null default 'tiktok',
  type text not null
    check (type in ('hook', 'format', 'emotion', 'topic', 'keyword_cluster')),
  signal_strength integer not null default 0
    check (signal_strength >= 0 and signal_strength <= 100),
  virality_score integer not null default 0
    check (virality_score >= 0 and virality_score <= 100),
  trend_state text not null default 'emerging'
    check (trend_state in ('emerging', 'rising', 'peaking', 'fading')),
  raw_data jsonb not null default '{}'::jsonb,
  summary text not null default '',
  dedupe_key text not null,
  constraint trend_intelligence_feed_dedupe_key_key unique (dedupe_key)
);

-- Add virality_score on legacy tables created before the column existed.
alter table public.trend_intelligence_feed
  add column if not exists virality_score integer not null default 0
    check (virality_score >= 0 and virality_score <= 100);

-- ---------------------------------------------------------------------------
-- Indexes (match query patterns: source filter + timestamp sort, upsert key)
-- ---------------------------------------------------------------------------
create unique index if not exists trend_intelligence_feed_dedupe_key_idx
  on public.trend_intelligence_feed (dedupe_key);

create index if not exists trend_intelligence_feed_source_timestamp_idx
  on public.trend_intelligence_feed (source, timestamp desc);

create index if not exists trend_intelligence_feed_timestamp_idx
  on public.trend_intelligence_feed (timestamp desc);

create index if not exists trend_intelligence_feed_source_type_idx
  on public.trend_intelligence_feed (source, type);

create index if not exists trend_intelligence_feed_trend_state_idx
  on public.trend_intelligence_feed (trend_state);

create index if not exists trend_intelligence_feed_virality_idx
  on public.trend_intelligence_feed (virality_score desc);

-- ---------------------------------------------------------------------------
-- Row Level Security (matches other dashboard tables using authenticated role)
-- ---------------------------------------------------------------------------
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

-- Service role (GitHub Actions pipeline) bypasses RLS for upserts.

-- ---------------------------------------------------------------------------
-- Backfill virality_score from raw_data for rows written before column existed
-- ---------------------------------------------------------------------------
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

-- Reload PostgREST schema cache so PGRST205 clears immediately after CREATE.
notify pgrst, 'reload schema';
