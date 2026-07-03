-- DEPRECATED: virality_score is included in sql/trend_intelligence_feed.sql
-- Safe to run on its own if you only need the column added to an existing table.

alter table public.trend_intelligence_feed
  add column if not exists virality_score integer not null default 0
    check (virality_score >= 0 and virality_score <= 100);

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

create index if not exists trend_intelligence_feed_virality_idx
  on public.trend_intelligence_feed (virality_score desc);

notify pgrst, 'reload schema';
