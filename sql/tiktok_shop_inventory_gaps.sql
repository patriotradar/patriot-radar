-- TikTok Shop inventory gaps — paused product attachments awaiting Showcase onboarding.
-- Isolated from trend_intelligence_feed and niche_comment_raw.

create table if not exists public.tiktok_shop_inventory_gaps (
  id uuid primary key default gen_random_uuid(),
  account_id text not null,
  content_id text not null,
  pipeline_run_id text not null,
  product_name text not null,
  category text not null default 'general',
  status text not null default 'waiting_user_action',
  inventory_gap_event jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resumed_at timestamptz,
  product_id text,
  unique (account_id, content_id)
);

create index if not exists idx_tiktok_shop_inventory_gaps_account
  on public.tiktok_shop_inventory_gaps (account_id);

create index if not exists idx_tiktok_shop_inventory_gaps_status
  on public.tiktok_shop_inventory_gaps (status);

comment on table public.tiktok_shop_inventory_gaps is
  'Paused TikTok Shop product attachments when catalog inventory is missing. Human-in-the-loop Showcase onboarding.';
