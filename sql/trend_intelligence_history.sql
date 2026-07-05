-- Multi-source trend intelligence historical storage
-- Run in Supabase SQL Editor or via scripts/apply_trend_feed_schema.py

create table if not exists public.trend_intelligence_history (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  trend text not null default '',
  keyword text not null default '',
  source text not null,
  niche text not null default 'general',
  popularity int not null default 0,
  buying_intent int not null default 0,
  competition int not null default 50,
  opportunity_score int not null default 0,
  category text not null default 'general',
  sentiment text not null default 'neutral',
  related_creators jsonb not null default '[]'::jsonb,
  recommended_content jsonb not null default '{}'::jsonb,
  content_intelligence jsonb not null default '{}'::jsonb,
  opportunity_scores jsonb not null default '{}'::jsonb,
  signal_type text not null default 'trend',
  raw_data jsonb not null default '{}'::jsonb,
  summary text,
  dedupe_key text unique
);

create index if not exists trend_intelligence_history_source_idx
  on public.trend_intelligence_history (source, created_at desc);

create index if not exists trend_intelligence_history_keyword_idx
  on public.trend_intelligence_history (keyword);

create index if not exists trend_intelligence_history_opportunity_idx
  on public.trend_intelligence_history (opportunity_score desc, created_at desc);

create index if not exists trend_intelligence_history_niche_idx
  on public.trend_intelligence_history (niche, created_at desc);

-- Scan metadata for dashboard system status
create table if not exists public.trend_intelligence_scans (
  id uuid primary key default gen_random_uuid(),
  scanned_at timestamptz not null default now(),
  niche text not null default 'general',
  providers_online jsonb not null default '[]'::jsonb,
  providers_offline jsonb not null default '[]'::jsonb,
  trend_count int not null default 0,
  opportunity_count int not null default 0,
  warnings jsonb not null default '[]'::jsonb,
  health_status text not null default 'healthy'
);

create index if not exists trend_intelligence_scans_time_idx
  on public.trend_intelligence_scans (scanned_at desc);

-- AI / rule-based recommendations snapshots
create table if not exists public.trend_recommendations (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  niche text not null default 'general',
  recommendations jsonb not null default '{}'::jsonb,
  version text not null default '1'
);

create index if not exists trend_recommendations_niche_idx
  on public.trend_recommendations (niche, created_at desc);

alter table public.trend_intelligence_history enable row level security;
alter table public.trend_intelligence_scans enable row level security;
alter table public.trend_recommendations enable row level security;

-- Service role bypasses RLS. Optional anon read for dashboard:
-- create policy "Anon read trend history" on public.trend_intelligence_history for select using (true);
-- create policy "Anon read scans" on public.trend_intelligence_scans for select using (true);
-- create policy "Anon read recommendations" on public.trend_recommendations for select using (true);
