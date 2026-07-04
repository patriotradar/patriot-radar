-- Isolated Virality Intelligence System tables.
-- Additive only — does not modify niche_comment_raw or any existing schema.
-- Run once in Supabase SQL Editor before enabling the learning pipeline.

-- Periodic prediction snapshots for time-based memory and outcome comparison.
create table if not exists public.virality_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_at timestamptz not null default now(),
  video_id text not null,
  niche text not null default '',
  comment_velocity numeric not null default 0,
  acceleration numeric not null default 0,
  repetition_score numeric not null default 0,
  curiosity_score numeric not null default 0,
  confusion_score numeric not null default 0,
  niche_relevance_score numeric not null default 0,
  virality_score numeric not null default 0,
  signals jsonb not null default '{}'::jsonb,
  weights jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  dedupe_key text not null,
  unique (dedupe_key)
);

create index if not exists virality_snapshots_snapshot_at_idx
  on public.virality_snapshots (snapshot_at desc);

create index if not exists virality_snapshots_video_id_idx
  on public.virality_snapshots (video_id);

create index if not exists virality_snapshots_niche_idx
  on public.virality_snapshots (niche);

-- Bounded self-learning calibration history (reversible weight adjustments).
create table if not exists public.virality_calibration_logs (
  id uuid primary key default gen_random_uuid(),
  calibrated_at timestamptz not null default now(),
  previous_weights jsonb not null default '{}'::jsonb,
  new_weights jsonb not null default '{}'::jsonb,
  adjustments jsonb not null default '{}'::jsonb,
  signal_errors jsonb not null default '{}'::jsonb,
  outcomes_processed integer not null default 0,
  accuracy_before numeric,
  accuracy_after numeric,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists virality_calibration_logs_calibrated_at_idx
  on public.virality_calibration_logs (calibrated_at desc);

-- Human-readable prediction explanations with confidence scoring.
create table if not exists public.virality_explanations (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  video_id text not null,
  niche text not null default '',
  virality_score numeric not null default 0,
  confidence_level text not null default 'Medium',
  confidence_score numeric not null default 50,
  explanation jsonb not null default '{}'::jsonb,
  dedupe_key text not null,
  unique (dedupe_key)
);

create index if not exists virality_explanations_created_at_idx
  on public.virality_explanations (created_at desc);

create index if not exists virality_explanations_video_id_idx
  on public.virality_explanations (video_id);

create index if not exists virality_explanations_niche_idx
  on public.virality_explanations (niche);

alter table public.virality_snapshots enable row level security;
alter table public.virality_calibration_logs enable row level security;
alter table public.virality_explanations enable row level security;

create policy "Authenticated users read virality snapshots"
  on public.virality_snapshots for select to authenticated using (true);

create policy "Authenticated users read virality calibration logs"
  on public.virality_calibration_logs for select to authenticated using (true);

create policy "Authenticated users read virality explanations"
  on public.virality_explanations for select to authenticated using (true);

-- Service role bypasses RLS for pipeline writes.
