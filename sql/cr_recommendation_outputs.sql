-- One-time backfill target table (versioned outputs; does not overwrite raw analytics).
-- Run once in Supabase SQL Editor before the backfill workflow.

create table if not exists public.cr_recommendation_outputs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  user_email text,
  output_version text not null,
  state text not null,
  engagement_signal text not null,
  insight_summary text not null,
  next_post jsonb not null,
  recommendation_meta jsonb,
  engagement_metrics jsonb,
  trends_last_updated text,
  backfilled_at timestamptz not null default now(),
  unique (user_id, output_version)
);

create index if not exists cr_recommendation_outputs_user_id_idx
  on public.cr_recommendation_outputs (user_id);

create index if not exists cr_recommendation_outputs_version_idx
  on public.cr_recommendation_outputs (output_version desc);

alter table public.cr_recommendation_outputs enable row level security;

-- Service role bypasses RLS. Optional read policy for authenticated users on own rows:
-- create policy "Users read own recommendations"
--   on public.cr_recommendation_outputs for select
--   using (auth.uid() = user_id);
