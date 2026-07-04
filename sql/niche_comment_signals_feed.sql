-- Niche-Aware Comment Signals feed (isolated from trend_intelligence_feed).
-- Run once in Supabase SQL Editor before enabling the comment signal pipeline.

create table if not exists public.niche_comment_signals_feed (
  id uuid primary key default gen_random_uuid(),
  timestamp timestamptz not null default now(),
  source text not null default 'tiktok_comments',
  video_url text not null default '',
  author text not null default '',
  caption_preview text not null default '',
  comment_count integer not null default 0,
  comments_analyzed integer not null default 0,
  comment_velocity numeric not null default 0,
  repetition_score numeric not null default 0,
  curiosity_score numeric not null default 0,
  niche_relevance_score numeric not null default 0,
  composite_signal numeric not null default 0,
  signal_state text not null default 'low'
    check (signal_state in ('low', 'moderate', 'high')),
  niche_id text not null default '',
  raw_data jsonb not null default '{}'::jsonb,
  summary text not null default '',
  dedupe_key text not null,
  unique (dedupe_key)
);

create index if not exists niche_comment_signals_feed_timestamp_idx
  on public.niche_comment_signals_feed (timestamp desc);

create index if not exists niche_comment_signals_feed_composite_idx
  on public.niche_comment_signals_feed (composite_signal desc);

create index if not exists niche_comment_signals_feed_niche_idx
  on public.niche_comment_signals_feed (niche_id);

alter table public.niche_comment_signals_feed enable row level security;

create policy "Authenticated users read niche comment signals"
  on public.niche_comment_signals_feed
  for select
  to authenticated
  using (true);

create policy "Authenticated users insert niche comment signals"
  on public.niche_comment_signals_feed
  for insert
  to authenticated
  with check (true);

create policy "Authenticated users update niche comment signals"
  on public.niche_comment_signals_feed
  for update
  to authenticated
  using (true)
  with check (true);

-- Service role bypasses RLS for pipeline writes.
