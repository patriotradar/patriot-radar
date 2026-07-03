-- Alias for sql/trend_intelligence_feed.sql (same content for apply scripts / docs).

-- trend_intelligence_feed (PGRST205 FIX)
-- Safe, idempotent migration

create table if not exists public.trend_intelligence_feed (
    id uuid primary key default gen_random_uuid(),

    timestamp timestamptz default now(),

    source text,
    type text,

    signal_strength int,
    virality_score int,

    trend_state text,

    raw_data jsonb,
    summary text,

    dedupe_key text unique
);

alter table public.trend_intelligence_feed
  add column if not exists virality_score int;

create index if not exists idx_trend_feed_source_timestamp
  on public.trend_intelligence_feed (source, timestamp desc);

create index if not exists idx_trend_feed_virality
  on public.trend_intelligence_feed (virality_score desc);

create index if not exists idx_trend_feed_dedupe
  on public.trend_intelligence_feed (dedupe_key);

alter table public.trend_intelligence_feed enable row level security;

drop policy if exists "allow read authenticated" on public.trend_intelligence_feed;
create policy "allow read authenticated"
  on public.trend_intelligence_feed
  for select
  to authenticated
  using (true);

drop policy if exists "allow insert authenticated" on public.trend_intelligence_feed;
create policy "allow insert authenticated"
  on public.trend_intelligence_feed
  for insert
  to authenticated
  with check (true);

drop policy if exists "allow update authenticated" on public.trend_intelligence_feed;
create policy "allow update authenticated"
  on public.trend_intelligence_feed
  for update
  to authenticated
  using (true)
  with check (true);

notify pgrst, 'reload schema';
