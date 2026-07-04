# Patriot Radar / Creator Radar — Ground-Truth Audit

Based solely on code in `/workspace`. No code was modified.

---

## 1. System Overview

- **What the software does end-to-end**
  - Collects TikTok and other external signals via Python pipelines (GitHub Actions), stores them in Supabase, and serves them to static HTML dashboards on Vercel.
  - Runs a separate Google Trends / Reddit / news scanner (`trends.py`) on a 4-hour schedule; pushes `results.json` to an external dashboard repo (`patriot-radar-dashboard`).
  - The main production UI lives in `dashboard-sync/index.html` (“Creator Radar”): auth, niche-based trend scanning, TikTok intelligence, comment virality, commerce/inventory panels, AI chat, performance logging.
  - A simpler mobile dashboard exists at root `index.html` (“Patriot Radar”): Supabase auth + TikTok trend feed only.

- **Main user-facing features (implemented)**
  - Supabase email/password auth with trial/paywall logic (`dashboard-sync/index.html`).
  - Niche-based “trend scan” using Google Suggest API (`scanNicheTrends`) → Plan tab content (daily plan, primary target, intelligence feed, etc.).
  - TikTok Trend Intelligence feed from Supabase `trend_intelligence_feed` (direct client read).
  - Live State panel from `GET /api/tiktok-live-state` (server-assembled contract + RBAC).
  - Niche Comment Intelligence + Early Virality Prediction (client-side signal computation from `niche_comment_raw`).
  - Virality Intelligence extension (reads `virality_calibration_logs`, `virality_explanations`).
  - Client-side TikTok Shop inventory predictor + reactive inventory gate (localStorage catalog).
  - My Stats, AI chat (calls `/api/chat/completions` or direct Gemini API), admin tab, referrals, performance logging.

- **Main backend pipelines (implemented)**
  - `trends.py` — Google Trends + Reddit/Twitter/news/autocomplete → `results.json` (CI every 4h).
  - `scripts/run_tiktok_trend_scan.py` → `trend_shift_engine.run_tiktok_trend_scan()` → Apify TikTok scrape → signal extraction → Supabase `trend_intelligence_feed` (CI every 6h).
  - `scripts/run_niche_comment_ingest.py` → Apify comment scrape → Supabase `niche_comment_raw` (CI every 6h).
  - `scripts/run_virality_learning_pipeline.py` → virality snapshots, calibration, explanations (CI every 6h).
  - `scripts/run_tiktok_shop_content_pipeline.py` — manual/CLI only; **no GitHub Actions workflow found**.
  - `scripts/run_tiktok_insights_pipeline.py` — Python hardened insights; separate from live-state API.
  - Vercel serverless: `/api/tiktok-live-state`, `/api/tiktok-insights`, `/api/public-config`.

---

## 2. Data Flow Map

- **Entry points**
  - **Apify** (`apify_tiktok_fetcher.py`, `apify_tiktok_comment_fetcher.py`) — TikTok videos and comments when `APIFY_API_TOKEN` is set.
  - **Google Trends / Reddit / news** (`trends.py`) — patriotic/British keyword universe.
  - **Google Suggest** (`dashboard-sync/index.html` `scanNicheTrends`) — browser fetches `suggestqueries.google.com` for niche seeds.
  - **User input** — niche, performance logs, auth metadata → Supabase `cr_analytics`, user metadata.
  - **Sample JSON fallbacks** — `data/tiktok_sample_inputs.json`, `data/tiktok_comment_sample.json`, `data/tiktok_shop_*.json`.

- **Backend movement**
  - Apify videos → `tiktok_trend_extractor` → `trend_intelligence_store.signals_to_feed_rows()` → Supabase `trend_intelligence_feed`.
  - Apify comments → `niche_comment_raw_store` → Supabase `niche_comment_raw`.
  - Virality learning → `virality_snapshot_store` → `virality_snapshots`; calibration → `virality_calibration_logs`; explanations → `virality_explanations`.
  - TikTok Shop pipeline (CLI) → predictive layer → content mode resolver → reactive gate → local/JSON output (not wired to live-state API).

- **Transformations**
  - TikTok extraction: hooks, formats, emotions, topics, keyword clusters, virality scores (`trend_intelligence_store.py`).
  - Niche signals computed **at query time** in browser (`niche-comment-intelligence.js`, `niche-comment-virality-prediction.js`).
  - Live state assembled in Node (`api/tiktok-live-state-assembler.js`) from Supabase rows + `data/feature_flags.json`.
  - Plan-tab trends scored client-side from Google Suggest suggestions (heuristic `viral_score`, `rise_percent`, etc.).

- **Storage**
  - **Supabase tables referenced in code:** `trend_intelligence_feed`, `niche_comment_raw`, `virality_snapshots`, `virality_calibration_logs`, `virality_explanations`, `tiktok_shop_inventory_gaps` (SQL only), `content_queue`, `content_performance`, `tiktok_insights_cache` (read only), `cr_analytics`.
  - **Browser cache:** `localStorage` (`cr_scan_cache_*`, `tiktok_shop_catalog`, paused/blocked attachments).
  - **CI artifacts:** `results.json` pushed to external dashboard repo.

- **Path to frontend**
  - TikTok feed: dashboard → Supabase client direct read (`refreshTiktokTrendIntelligenceFeed`).
  - Live state: dashboard → `GET /api/tiktok-live-state` with Bearer JWT.
  - Plan tab: `loadLiveStats()` → `scanNicheTrends()` → `renderAllSections()` (no server round-trip for trend scores).
  - Niche/virality panels: Supabase direct read + client computation.
  - `tiktok-insights-hardening.js` can POST to `/api/tiktok-insights` with video payloads.

---

## 3. Module Inventory (exists in codebase)

| Category | Modules |
|----------|---------|
| **Backend engines (Python)** | `trends.py`, `trend_shift_engine.py`, `tiktok_trend_extractor.py`, `tiktok_pipeline_hardening.py`, `tiktok_insights_pipeline.py`, `tiktok_trending_products_engine.py`, `niche_comment_engine.py`, `niche_comment_signal_processor.py`, `niche_comment_virality_engine.py`, `virality_intelligence_engine.py`, `virality_feedback_loop.py`, `virality_calibration_engine.py`, `virality_explainer.py`, `tiktok_shop_content_pipeline.py`, `tiktok_inventory_predictor.py`, `tiktok_shop_inventory_gate.py`, `tiktok_content_mode_resolver.py`, `inventory_gap_system.py`, `inventory_prevention_system.py` |
| **State providers (Python stubs — return empty/minimal)** | `trend_detection_engine.py`, `emerging_products_engine.py`, `trending_products_engine.py`, `content_queue_system.py`, `approval_system.py`, `performance_tracker.py`, `learning_engine.py`, `system_health_monitor.py`, `inventory_gap_system.py`, `inventory_prevention_system.py` |
| **Pipelines / CLIs** | `scripts/run_tiktok_trend_scan.py`, `scripts/run_niche_comment_ingest.py`, `scripts/run_niche_comment_virality.py`, `scripts/run_virality_learning_pipeline.py`, `scripts/run_tiktok_insights_pipeline.py`, `scripts/run_tiktok_shop_content_pipeline.py` |
| **Stores** | `trend_intelligence_store.py`, `niche_comment_raw_store.py`, `virality_snapshot_store.py` |
| **APIs (Vercel Node)** | `api/tiktok-live-state.js`, `api/tiktok-live-state-assembler.js`, `api/tiktok-access-control.js`, `api/tiktok-insights.js`, `api/public-config.js` (duplicated under `dashboard-sync/api/`) |
| **State assemblers** | `api/tiktok-live-state-assembler.js` (production path), `tiktok_live_state_assembler.py` (Python mirror; **not called by API handler**) |
| **RBAC** | `api/tiktok-access-control.js`, `tiktok_access_control.py`, `dashboard-sync/tiktok-access-control.js` |
| **Dashboards** | `index.html` (Patriot Radar), `dashboard-sync/index.html` (Creator Radar) |
| **Frontend JS modules** | `tiktok-live-state.js`, `tiktok-access-control.js`, `niche-comment-intelligence.js`, `niche-comment-virality-prediction.js`, `virality-intelligence-dashboard.js`, `tiktok-insights-hardening.js`, `tiktok-inventory-predictor.js`, `tiktok-shop-inventory-gate.js`, `tiktok-content-mode-resolver.js` |
| **Commerce / inventory** | Python: `tiktok_shop_content_pipeline.py`, `tiktok_shop_inventory_gate.py`, `tiktok_inventory_predictor.py`, `tiktok_content_mode_resolver.py`. Frontend: `tiktok-shop-inventory-gate.js`, `tiktok-inventory-predictor.js`, `tiktok-content-mode-resolver.js` |
| **CI workflows** | `trends.yml`, `tiktok-trend-scan.yml`, `niche-comment-ingest.yml`, `virality-learning-pipeline.yml`, `sync-dashboard-tiktok-feed.yml` |
| **SQL schemas** | `sql/trend_intelligence_feed.sql`, `sql/niche_comment_raw.sql`, `sql/virality_intelligence_tables.sql`, `sql/tiktok_shop_inventory_gaps.sql`, `sql/trend_intelligence_feed_add_virality.sql` |
| **Not found in codebase** | `api/chat/completions.js` (referenced in `dashboard-sync/vercel.json` and `index.html` but file absent) |

---

## 4. Live State System

- **`/api/tiktok-live-state` exists**
  - Implemented at `api/tiktok-live-state.js` and `dashboard-sync/api/tiktok-live-state.js`.
  - `GET` with optional `account_id` query param.
  - Registered in `vercel.json` with 30s max duration.

- **What it returns in practice**
  - JSON matching `emptyLiveStateContract()` schema:
    - `today_flow`, `trends`, `products`, `inventory_gaps`, `inventory_prevention`, `content_queue`, `approvals`, `performance`, `prediction`, `alerts`, `hidden_alerts`, `raw_logs`, `primary_action`, `system_health`, `access`.
  - `access` block: `{ role, admin_override, visible_modules, commerce_access }`.
  - On any handler exception: HTTP 200 with `emptyContract()` (all empty/unknown defaults).
  - Unauthenticated requests: `resolveUserFromAuthHeader` returns `null`; role defaults to `"creator"`.

- **Actual function chain (production path)**
  1. `api/tiktok-live-state.js` `handler`
  2. `resolveUserFromAuthHeader(req)` → Supabase `auth/v1/user` with Bearer token
  3. `assembleLiveState(accountId, userRecord)` in `api/tiktok-live-state-assembler.js`
  4. Data fetches (Supabase REST):
     - `trend_intelligence_feed` where `source=tiktok` (trends)
     - `tiktok_insights_cache` payload keys `emerging_products`, `trending_products` (products)
     - `content_queue`, `content_performance` filtered by `account_id` (queue, approvals, performance)
  5. `inventory_gaps` hardcoded to `[]` in Node assembler (not fetched from `tiktok_shop_inventory_gaps`)
  6. `prediction` hardcoded to `{}`
  7. `system_health`: `"degraded"` if any `catch` block fires; otherwise `"healthy"`
  8. `loadFeatureFlags()` from `data/feature_flags.json`
  9. `buildAccessContext()` → `filterLiveStateForAccess()`
  10. Response JSON

  - **Python assembler** (`tiktok_live_state_assembler.py`) dynamically imports stub engines via `_safe_invoke`; **not used by the Vercel API handler**.

- **Snapshot layer usage in live state**
  - `virality_snapshots` is **not** read or written by the live-state assembler.
  - Snapshots are written by `virality_feedback_loop.py` / `virality_intelligence_engine.py` when `persist_snapshots=True`.
  - `virality-intelligence-dashboard.js` defines `TABLES.snapshots` but `refreshViralityIntelligence()` only queries `virality_calibration_logs` and `virality_explanations` — **snapshots table is not queried in that refresh function**.
  - Performance `snapshots` inside live state refer to `content_performance` rows aggregated in the assembler, not `virality_snapshots`.

---

## 5. Frontend Behaviour

- **What the dashboard renders**
  - **Creator Radar** (`dashboard-sync/index.html`) tabs:
    - **Plan** — inventory predictor/gate panels, daily plan, content funnel, primary target (from `scanNicheTrends` results).
    - **Trends** — scoring guide, opportunities, AI insights, themes, intelligence feed, TikTok Trend Intelligence (Supabase), Live State mount, niche comment intelligence, insights hardening, virality prediction, virality intelligence extension.
    - **Discover** — breaking news, emerging topics, creator insights, live feed.
    - **My Stats** — personal intelligence, weekly scorecard, streak, audience insights.
    - **Tools** — platform optimizer, video analyzer.
    - **Ask AI**, **Audit**, **Updates**, **Admin** (admin-only).

  - **Patriot Radar** (`index.html`) — static “Top Opportunity” card (hardcoded British Army example), Overview/ Emerging Trends / Admin tabs.

- **Data sources (not live-state exclusive)**
  - **Plan tab / intelligence feed / primary target:** `loadLiveStats()` → Google Suggest (`scanNicheTrends`) + `localStorage` cache; **not** from `/api/tiktok-live-state`.
  - **TikTok Trend Intelligence panel:** direct Supabase read of `trend_intelligence_feed` (`refreshTiktokTrendIntelligenceFeed`).
  - **Live State panel:** `/api/tiktok-live-state` only (`tiktok-live-state.js`); refreshes every 60s.
  - **Niche Comment Intelligence / Virality Prediction:** direct Supabase `niche_comment_raw` + client-side computation.
  - **Virality Intelligence extension:** direct Supabase `virality_calibration_logs`, `virality_explanations`.
  - **Inventory panels:** client-side from `scanNicheTrends` results + `localStorage` `tiktok_shop_catalog`.
  - **AI features:** `/api/chat/completions` (file not in repo) or direct Gemini API when `GEMINI_KEY` is set.

- **RBAC visibility interaction**
  - `TiktokAccessControl.initFromSession()` runs on dashboard load; `TiktokLiveState.mount()` inserts Live State panel before `#tiktokTrendIntelligence`.
  - `applyModuleVisibility()` shows/hides/restricts DOM sections by `visible_modules`.
  - Restricted modules get `data-rbac-restricted="true"` and CSS class `rbac-restricted` (elements remain in DOM).

- **Sections visible by default (`feature_flags.json`, non-admin, `commerce_mode: false`)**
  - Server `visible_modules` for role `creator`: `trends`, `prediction_engine`, `analytics` (products and inventory_system excluded by commerce gate; system_health/raw_logs/hidden_alerts excluded by flags).
  - DOM sections for hidden commerce modules (`#primaryTarget`, `#contentFunnel`) receive `restrictElement` (visible but marked restricted), not `display:none`.
  - Admin-only panels (`#rbacSystemHealthPanel`, etc.) are `display:none` unless `admin_override`.

---

## 6. Commercial / Commerce Logic

- **`commerce_mode` enforcement**
  - `data/feature_flags.json`: `"commerce_mode": false`.
  - Server: `resolveVisibleModules()` excludes `products` and `inventory_system` when `commerce_mode` is false and user is not admin (`api/tiktok-access-control.js`).
  - Server: `filterLiveStateForAccess()` empties `products`, `inventory_gaps`, `inventory_prevention` when those modules are not visible.
  - Server: `commerce_access` is `true` only for admin or when `commerce_mode` is true.
  - Frontend: `canAccessCommerce()` exists in `tiktok-access-control.js` but **no call sites found** outside that module’s export.
  - Frontend commerce UI gating is via `MODULE_DOM_MAP` → `products` module controls `#primaryTarget`, `#contentFunnel`.

- **TikTok Shop integration status**
  - **Backend pipeline:** full dual-layer implementation in Python (`tiktok_shop_content_pipeline.py`); runnable via CLI with sample JSON; **no scheduled CI workflow**.
  - **Live-state API:** does not fetch `tiktok_shop_inventory_gaps`; `inventory_gaps` always `[]` in Node assembler.
  - **Frontend:** `TikTokShopInventoryGate` and `TikTokInventoryPredictor` run client-side against `localStorage` catalog; catalog loaded from localStorage key `tiktok_shop_catalog` (no Supabase catalog sync found).
  - **`tiktok_insights_cache`:** read by live-state assembler for products; **no write path found in codebase**.

- **Product attachment in reality**
  - **Python pipeline:** `attach_product_with_inventory_gate()` in `tiktok_shop_content_pipeline.py` — reactive gate blocks attachment; predictive layer sets `content_mode`; uses catalog list passed to function.
  - **Frontend:** `renderAllSections()` calls `TikTokInventoryPredictor.processTrendResults()` which calls `TikTokShopInventoryGate.processTrendResults()` — matches trend keywords to local catalog, may block attachments and render gap cards in `#tiktokShopInventoryGate`.
  - Attachment logic operates on Google Suggest trend results, not on live-state `products` array.
  - Live-state `products` come from `tiktok_insights_cache` Supabase table (empty if table unpopulated).

---

## 7. RBAC / Access Control

- **Role determination (server)**
  - Priority in `getUserRole()`:
    1. Email in `TIKTOK_ADMIN_EMAILS` or `ADMIN_EMAILS` env → `admin`
    2. `user_metadata.role` or `user_metadata.user_role` (if valid: admin/creator/viewer/test)
    3. Env `TIKTOK_ROLE_{accountId}`
    4. Default: `creator`
  - Role is **not** taken from query/body (`api/tiktok-live-state.js` comment and implementation).

- **Role determination (frontend, separate)**
  - `showDashboard()` sets `isAdmin` from `user_metadata.role === "admin"` or hardcoded `ADMIN_EMAILS` array in `index.html`.
  - `TiktokAccessControl` uses server-derived `access` from live-state API.
  - Two parallel admin checks exist (client inline + server JWT).

- **Admin override enforcement**
  - **Backend:** `admin_override: true` when role is `admin`; `filterLiveStateForAccess` returns full unredacted state; `resolveVisibleModules` returns all 8 modules regardless of feature flags.
  - **Frontend:** `admin_override` shows admin tab button, admin debug panels, sets `global.isAdminUser`, adds `rbac-admin-view` body class.
  - Admin email in root `index.html` is hardcoded: `["jamie.mahon1996@gmail.com"]`.
  - Server admin list comes from env vars only.

- **Filtering type**
  - **Backend (live-state API):** structural — non-visible module data replaced with `[]`, `{}`, or `"restricted"` before JSON is sent.
  - **Frontend:** visual/structural DOM — `hideElement` (admin-only modules), `restrictElement` (non-commerce modules), `showElement` (allowed modules).
  - TikTok trend feed and niche comment panels use **direct Supabase reads** and are **not redacted** by live-state RBAC filtering (only DOM visibility is toggled).

---

## 8. Fail Safety Behaviour

- **When Supabase fails (live-state API)**
  - `supabaseRequest()` catches errors and returns `null`.
  - Fetch helpers return `[]` or `{}` without throwing.
  - Response is HTTP 200 with empty module arrays; `system_health` remains `"healthy"` (partial failure list only populated on thrown exceptions).
  - Top-level handler `catch` returns `emptyContract()` at HTTP 200.

- **When Supabase fails (direct dashboard reads)**
  - `refreshTiktokTrendIntelligenceFeed()`: renders error message for RLS/table-missing (`PGRST205`, `42501`) or generic error string.
  - `refreshNicheCommentIntelligence()`: renders error shell via `describeError()`.
  - `refreshViralityIntelligence()`: shows “tables not found” for `PGRST205` on calibration table.
  - Root `index.html` `refreshTrendIntelligenceFeed()`: renders empty sections with descriptive messages.
  - `trend_intelligence_store.py`: returns `{stored: 0, skipped: N, error: "..."}`; never raises.
  - Missing `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`: returns `{error: "missing_supabase_credentials"}`.

- **When Apify fails (trend scan pipeline)**
  - No token: falls back to sample inputs (`trend_shift_engine._resolve_scan_inputs`).
  - Token present but fetch fails: returns `success: false`, empty signals, `fallback_refused: true`, **no sample fallback**; CI validation fails the workflow.
  - `fetch_tiktok_via_apify()`: returns `{success: false, error: "...", items: []}`; does not throw.
  - Comment ingest (`niche_comment_engine.py`): token present + Apify fail → `success: false`, no sample fallback; no token → sample file fallback.

- **When modules return empty data**
  - Live-state API: returns full schema with empty collections; `deriveFlowAndAction()` sets `next_action` based on priority (approvals → inventory gaps → products+trends → trends only → queue → refresh trends).
  - With all empty: `today_flow.status` becomes `"healthy"` (if system_health healthy) and `next_action` = `"Run trend scan to refresh signals"`.
  - Dashboard `loadLiveStats()`: if `scanNicheTrends` returns 0 results, generates seed-based fallback keywords; 12s timeout also injects emergency seed results.
  - `renderTiktokTrendIntelligenceFeed([])`: shows `TIKTOK_FEED_EMPTY_MSG`.
  - `TiktokLiveState.fetchLiveState()`: non-OK response → `emptyContract()`; sets `global.TIKTOK_LIVE_STATE`.
  - `TiktokAccessControl.initFromSession()` failure: falls back to hardcoded `visible_modules: ["trends", "prediction_engine", "analytics"]`.
  - `/api/tiktok-insights` with no videos: HTTP 200, `{success: true, message: "no_videos_provided", ...empty arrays}`.
  - Python stub engines (`get_state` returns `[]`): used only by Python assembler, not production API path.

---

## Notable Codebase Facts

- Two deployment surfaces: this repo (pipelines + `api/`) and external `patriot-radar-dashboard` (receives synced `dashboard-sync/` + `results.json`).
- Python `tiktok_live_state_assembler.py` and Node `tiktok-live-state-assembler.js` are **different implementations**; production API uses the Node version with direct Supabase queries.
- `virality_snapshots` is written by backend learning pipeline but not consumed by the live-state API or the virality dashboard refresh function.
- `tiktok_insights_cache` is read by live-state assembler but has no write path in this repo.
- `api/chat/completions.js` is referenced but **not found in codebase**.
