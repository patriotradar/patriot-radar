-- Isolated raw TikTok comment storage for Niche Comment Intelligence.
-- No niche binding at ingestion — relevance is computed at query time.
-- Run once in Supabase SQL Editor before enabling the comment ingest pipeline.

create table if not exists public.niche_comment_raw (
  id uuid primary key default gen_random_uuid(),
  video_id text not null,
  video_url text not null default '',
  video_caption text not null default '',
  video_author text not null default '',
  comment_text text not null,
  comment_author text not null default '',
  comment_like_count integer not null default 0,
  commented_at timestamptz,
  ingested_at timestamptz not null default now(),
  ingestion_batch text not null default '',
  source text not null default 'apify',
  metadata jsonb not null default '{}'::jsonb,
  dedupe_key text not null,
  unique (dedupe_key)
);

create index if not exists niche_comment_raw_ingested_at_idx
  on public.niche_comment_raw (ingested_at desc);

create index if not exists niche_comment_raw_video_id_idx
  on public.niche_comment_raw (video_id);

create index if not exists niche_comment_raw_video_url_idx
  on public.niche_comment_raw (video_url);

alter table public.niche_comment_raw enable row level security;

create policy "Authenticated users read niche comment raw"
  on public.niche_comment_raw
  for select
  to authenticated
  using (true);

create policy "Authenticated users insert niche comment raw"
  on public.niche_comment_raw
  for insert
  to authenticated
  with check (true);

create policy "Authenticated users update niche comment raw"
  on public.niche_comment_raw
  for update
  to authenticated
  using (true)
  with check (true);

-- Service role bypasses RLS for pipeline writes.
