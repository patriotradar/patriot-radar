-- Add virality_score to an existing trend_intelligence_feed table.
-- Safe to run multiple times. Full setup: sql/trend_intelligence_feed.sql

alter table public.trend_intelligence_feed
  add column if not exists virality_score int;

create index if not exists idx_trend_feed_virality
  on public.trend_intelligence_feed (virality_score desc);

notify pgrst, 'reload schema';
