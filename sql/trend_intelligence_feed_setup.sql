-- Alias for sql/trend_intelligence_feed.sql (same content for apply scripts / docs).

create table if not exists public.trend_intelligence_feed (
    id uuid primary key default gen_random_uuid(),

    created_at timestamptz default now(),

    source text not null,
    type text not null,

    signal_strength int default 0,
    virality_score int default 0,

    trend_state text,

    raw_data jsonb,
    summary text,

    dedupe_key text unique not null
);

alter table public.trend_intelligence_feed
  add column if not exists created_at timestamptz default now();

alter table public.trend_intelligence_feed
  add column if not exists virality_score int default 0;

create index if not exists idx_feed_source_created_at
  on public.trend_intelligence_feed (source, created_at desc);

create index if not exists idx_feed_virality
  on public.trend_intelligence_feed (virality_score desc);

create index if not exists idx_feed_dedupe
  on public.trend_intelligence_feed (dedupe_key);

alter table public.trend_intelligence_feed enable row level security;

drop policy if exists "read authenticated" on public.trend_intelligence_feed;
create policy "read authenticated"
  on public.trend_intelligence_feed
  for select
  to authenticated
  using (true);

drop policy if exists "insert service only" on public.trend_intelligence_feed;
create policy "insert service only"
  on public.trend_intelligence_feed
  for insert
  to service_role
  with check (true);

drop policy if exists "update service only" on public.trend_intelligence_feed;
create policy "update service only"
  on public.trend_intelligence_feed
  for update
  to service_role
  using (true)
  with check (true);

drop policy if exists "allow read authenticated" on public.trend_intelligence_feed;
drop policy if exists "allow insert authenticated" on public.trend_intelligence_feed;
drop policy if exists "allow update authenticated" on public.trend_intelligence_feed;
drop policy if exists "Authenticated users read trend intelligence feed" on public.trend_intelligence_feed;
drop policy if exists "Authenticated users insert trend intelligence feed" on public.trend_intelligence_feed;
drop policy if exists "Authenticated users update trend intelligence feed" on public.trend_intelligence_feed;

notify pgrst, 'reload schema';
