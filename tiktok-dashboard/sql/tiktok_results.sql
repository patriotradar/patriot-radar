-- TikTok viral research scan results
-- `data` JSONB shape:
-- {
--   "videos": [...],
--   "comments": [...],
--   "insights": { pain_points, questions, content_opportunities, hooks, buying_signals, summary },
--   "trend_scores": [{ url, trendScore, caption }],
--   "meta": { ... }
-- }
CREATE TABLE IF NOT EXISTS tiktok_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  niche TEXT NOT NULL,
  data JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tiktok_results_niche ON tiktok_results (niche);
CREATE INDEX IF NOT EXISTS idx_tiktok_results_created_at ON tiktok_results (created_at DESC);
