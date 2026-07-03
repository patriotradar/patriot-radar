-- Migration: add virality_score column to existing trend_intelligence_feed tables.
-- Safe to run multiple times (IF NOT EXISTS).

alter table public.trend_intelligence_feed
  add column if not exists virality_score integer not null default 0
  check (virality_score >= 0 and virality_score <= 100);

-- Backfill virality from raw_data where column was added after initial deploy.
update public.trend_intelligence_feed
set virality_score = coalesce(
  (raw_data->>'virality_score')::integer,
  round(((raw_data->'virality'->>'viral_strength_score')::numeric) * 100)::integer,
  0
)
where virality_score = 0
  and (
    raw_data ? 'virality_score'
    or raw_data->'virality' ? 'viral_strength_score'
  );

create index if not exists trend_intelligence_feed_virality_idx
  on public.trend_intelligence_feed (virality_score desc);
