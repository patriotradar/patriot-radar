# Patriot Radar — Architecture Analysis Report

**Repository:** `patriotradar/patriot-radar`  
**Analysis date:** 2026-07-03  
**Scope:** Full repository inventory and production flow (analysis only — no code changes)

---

## Executive Summary

This repository is a **scheduled trend scanner** for UK patriotic content topics. It contains **one production engine** (`trends.py`), **one active CI/CD pipeline** (`.github/workflows/trends.yml`), and **two orphaned artifacts** (`patriot trends scanner`, `index.html`) that are not part of the live flow.

Results are pushed to an **external dashboard repository** (`patriot-radar-dashboard`). This repo itself only stores the scanner, workflow, and a heartbeat file (`last-run.txt`).

---

## 1. Current Architecture

### 1.1 High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRIGGER LAYER                               │
│  GitHub Actions cron (every 4 hours) + manual workflow_dispatch │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              THIS REPO: patriot-radar                           │
│                                                                 │
│  .github/workflows/trends.yml                                   │
│       │                                                         │
│       ├── pip install -r requirements.txt                       │
│       ├── python trends.py  ◄── sole runtime entry point        │
│       ├── upload results.txt + results.json (artifacts)         │
│       ├── push results.json → patriot-radar-dashboard repo      │
│       └── commit last-run.txt → this repo (heartbeat only)      │
│                                                                 │
│  ORPHANED (not in production flow):                             │
│    • patriot trends scanner  (stale workflow copy)              │
│    • index.html              (broken static dashboard UI)       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   trends.py INTERNAL PIPELINE                   │
│                                                                 │
│  ┌──────────────┐   ┌──────────────────────────────────────┐   │
│  │ Google Trends│   │ DISCOVERY SUBSYSTEMS (6 sources)     │   │
│  │ (pytrends)   │   │  • Related queries + UK trending       │   │
│  │ Core scoring │   │  • Reddit RSS (8 subreddits)           │   │
│  └──────────────┘   │  • Twitter HTML scrapers               │   │
│                     │  • UK news (Google News + 8 RSS feeds) │   │
│                     │  • Google Autocomplete                   │   │
│                     │  • Random fallback (if API fails)      │   │
│                     └──────────────────────────────────────┘   │
│                                                                 │
│  SCORING LAYERS:                                                │
│    viral_score → content_score → opportunity_gap                │
│                                                                 │
│  OUTPUT: results.json + results.txt (runtime only, not committed)│
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│           EXTERNAL: patriot-radar-dashboard repo                │
│           Consumes results.json for live dashboard UI           │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Complete File Inventory

| File | Lines / Size | Role | In Production? |
|------|-------------|------|----------------|
| `trends.py` | ~1,293 lines | Core scanner engine | **Yes** |
| `.github/workflows/trends.yml` | 59 lines | CI/CD pipeline | **Yes** |
| `requirements.txt` | 3 deps | Python dependencies | **Yes** |
| `last-run.txt` | 1 line | Heartbeat timestamp (CI-written) | **Yes** |
| `.gitignore` | 1 line | Ignores `__pycache__/` | **Yes** |
| `patriot trends scanner` | 28 lines | Stale workflow copy | **No** |
| `index.html` | 180 lines | Orphaned Supabase auth UI | **No** |
| `README.md` | 1 line | Stub title only | **No functional role** |

**Runtime outputs (generated, not committed):**

| File | Producer | Consumer |
|------|----------|----------|
| `results.json` | `save_results()` in `trends.py` | CI → dashboard repo + GitHub artifacts |
| `results.txt` | `save_results()` in `trends.py` | GitHub artifacts only |

### 1.3 Internal Pipeline Phases (`trends.py`)

The scanner runs through these phases in order inside `main()`:

| Phase | Key Functions | Description |
|-------|---------------|-------------|
| **1. Core scoring** | `analyse_keywords()` | Queries Google Trends for shuffled content keywords (20 of ~50) and product keywords (5 of ~20). Computes viral scores from interest-over-time data. |
| **2. Fallback supplement** | `fallback_results()` | If fewer than 5 live results, injects random synthetic scores from the keyword pool. |
| **3. Emerging discovery** | `discover_related_keywords()`, `discover_trending_searches()`, `scan_reddit()`, `scan_twitter_trends()`, `scan_uk_news()`, `scan_autocomplete()` | Aggregates topics from 6 external sources, deduplicates, and cross-platform boosts. |
| **4. Emerging scoring** | `make_emerging_hooks()`, `score_discovered_keyword()` | Generates debate hooks and scores top 10 discovered keywords via Google Trends. |
| **5. Content scoring** | `score_content_potential()` | Scores all items on 4 dimensions: Fresh, British, Emotion, Debate (0–100 each, total 0–100). |
| **6. Opportunity gap** | `check_tiktok_competition()`, `score_opportunity_gap()` | Estimates demand vs TikTok competition for top 15 items. |
| **7. Output** | `save_results()` | Writes `results.txt` (human-readable) and `results.json` (structured). |

### 1.4 Data Configuration (Constants in `trends.py`)

| Constant | Count | Purpose |
|----------|-------|---------|
| `CONTENT_KEYWORDS` | ~50 | Core patriotic content topics |
| `PRODUCT_KEYWORDS` | ~20 | Affiliate product trend topics |
| `PATRIOTIC_FILTER_WORDS` | ~40 | Relevance filter for discovered queries |
| `BLOCKED_WORDS` | ~30 | Exclusion filter (sports, celebrities, etc.) |
| `STRONG_PATRIOTIC_WORDS` | ~20 | High-confidence patriotic signal words |
| `QUESTIONS` | ~80+ entries (with duplicates) | Pre-written debate questions per keyword |
| `EMERGING_HOOK_TEMPLATES` | 7 groups × 5 templates | Dynamic hook generation for emerging topics |
| `EMOTIONAL_TRIGGERS` | ~50 | Content emotion scoring |
| `DEBATE_TRIGGERS` | ~25 | Content debate-ability scoring |

### 1.5 External Dependencies

| Dependency | Used By | Purpose |
|------------|---------|---------|
| `pytrends` | `analyse_keywords()`, `discover_*()`, `score_discovered_keyword()` | Google Trends API |
| `pandas` | (transitive via pytrends) | DataFrame handling for trend data |
| `requests` | `scan_reddit()`, `scan_twitter_trends()`, `scan_uk_news()`, `scan_autocomplete()`, `check_tiktok_competition()` | HTTP scraping of RSS/HTML/autocomplete |
| `DASHBOARD_TOKEN` (GitHub secret) | CI workflow | Push `results.json` to dashboard repo |

---

## 2. Entry Point

### Primary Entry Point

```
trends.py → main() → if __name__ == "__main__"
```

**Invocation:**

```bash
python trends.py
```

This is the **only** executable entry point in the repository. There are no other `.py` files, shell scripts, Makefiles, or Dockerfiles.

### How It Gets Triggered

| Trigger | Source | Schedule |
|---------|--------|----------|
| Scheduled | `.github/workflows/trends.yml` cron | `0 */4 * * *` (every 4 hours) |
| Manual | `.github/workflows/trends.yml` `workflow_dispatch` | On demand |

### What `main()` Does (Execution Order)

1. Initialize `TrendReq(hl="en-GB", tz=0)` (Google Trends client)
2. Shuffle and scan 20 content keywords + 5 product keywords
3. Supplement with fallback data if live results < 5
4. Run all 6 discovery subsystems in sequence
5. Deduplicate and cross-platform boost discovered topics
6. Score top 10 emerging topics via Google Trends
7. Apply content scoring to all results
8. Check TikTok competition for top 15 items
9. Sort by content score, save to `results.json` and `results.txt`

---

## 3. Active vs Experimental Systems

### 3.1 Active (Production) Systems

| System | File | Evidence |
|--------|------|----------|
| **Scanner engine** | `trends.py` | Called by CI: `run: python trends.py` |
| **CI/CD pipeline** | `.github/workflows/trends.yml` | Only workflow in `.github/workflows/`; GitHub Actions reads exclusively from this directory |
| **Dependency manifest** | `requirements.txt` | Installed by CI before scanner runs |
| **Heartbeat** | `last-run.txt` | Updated and committed by CI every run; recent git history is almost entirely `Update scanner timestamp` commits |
| **Dashboard feed** | External `patriot-radar-dashboard` repo | CI clones, copies `results.json`, pushes |

### 3.2 Experimental / Orphaned Systems

#### `patriot trends scanner` (root-level file)

| Attribute | Detail |
|-----------|--------|
| **Status** | Dead artifact — not executed |
| **Why orphaned** | GitHub Actions only runs workflows from `.github/workflows/*.yml`. This file sits at repo root with no extension. |
| **What it contains** | Incomplete copy of an older workflow version |
| **Key differences from active workflow** | 30-minute cron (`*/30 * * * *`) vs 4-hour; no artifact upload; no dashboard push; no `last-run.txt` commit; no `permissions: contents: write` |
| **Origin** | Created in commit `694109d` ("Create patriot trends scanner"); first line is literally `.github/workflows/trends.yml` (copy-paste error) |
| **Risk** | Confusion about which schedule is live |

#### `index.html` (root-level file)

| Attribute | Detail |
|-----------|--------|
| **Status** | Orphaned prototype — not deployed or referenced |
| **Why orphaned** | Production dashboard lives in separate `patriot-radar-dashboard` repo; CI pushes `results.json` there, not here |
| **What it contains** | Supabase auth UI with hardcoded static content |
| **Problems** | Does not load `results.json`; shows static placeholder data ("British Army", "UK Politics"); broken JavaScript syntax on line 82 (`const SUPABASE_URL = "const SUPABASE_URL = "https://...";"`); auth redirects point to `patriotradar.github.io/patriot-radar-dashboard/` |
| **Origin** | Created in commit `2892f04` ("Create index.html"); last updated in commit `07561c5` |
| **Risk** | Misleading — looks like the dashboard but is disconnected and broken |

#### `README.md`

| Attribute | Detail |
|-----------|--------|
| **Status** | Stub |
| **Content** | Single line: `# patriot-radar` |
| **Risk** | No onboarding documentation for the actual architecture |

### 3.3 Summary Table

| Component | Active | Experimental | Notes |
|-----------|--------|-------------|-------|
| `trends.py` | ✅ | | Sole engine |
| `.github/workflows/trends.yml` | ✅ | | Sole CI pipeline |
| `requirements.txt` | ✅ | | |
| `last-run.txt` | ✅ | | CI heartbeat |
| `patriot trends scanner` | | ✅ | Stale workflow copy |
| `index.html` | | ✅ | Broken orphaned UI |
| `README.md` | | ✅ | Empty stub |
| `patriot-radar-dashboard` (external) | ✅ | | Real consumer UI |

---

## 4. Duplicate Logic

### 4.1 Duplicate Files (Not Duplicate Engines)

There is **one core engine** (`trends.py`). The duplicates are **files**, not competing runtime systems:

| Duplicate | Canonical Version | Impact |
|-----------|-------------------|--------|
| `patriot trends scanner` | `.github/workflows/trends.yml` | None at runtime (root file is inert); causes human confusion |

### 4.2 Duplicate Keys in `QUESTIONS` Dict

Python silently keeps the **last** value when dict keys are duplicated. The following keys appear more than once in `QUESTIONS` (lines 67–158):

| Duplicate Key | Occurrences | Notes |
|---------------|-------------|-------|
| `national service` | 2 | Lines 101 and 120 |
| `buckingham palace` | 2 | Lines 110 and 122 |
| `rule britannia` | 2 | Lines 111 and 123 |
| `keep calm and carry on` | 2 | Lines 112 and 124 |
| `british bulldog` | 2 | Lines 113, 125, and 155 (3×) |
| `poppy` | 2 | Lines 86 and 130 |
| `armed forces day` | 2 | Lines 109 and 131 |
| `war memorial` | 2 | Lines 108 and 128 |
| `cenotaph` | 2 | Lines 107 and 129 |
| `dunkirk spirit` | 2 | Lines 96 and 133 |
| `tradition` | 2 | Lines 144 and 103 |
| `heritage` | 2 | Lines 145 and 102 |
| `freedom` | 2 | Lines 146 and 105 |
| `democracy` | 2 | Lines 147 and 106 |
| `sacrifice` | 2 | Lines 104 and 142 |
| `london` | 2 | Lines 80 and 138 |
| `great britain` | 2 | Lines 81 and 157 |
| `the few` | 2 | Lines 135 and 150 |

**Impact:** Later entries silently override earlier ones. No runtime crash, but some intended questions are never used.

### 4.3 Overlapping Discovery Logic

Six discovery functions share common patterns but are **not duplicates of each other** — they query different sources:

| Function | Source | Shared Pattern |
|----------|--------|----------------|
| `discover_related_keywords()` | Google Trends related queries | `is_patriotic_relevant()` filter |
| `discover_trending_searches()` | Google Trends UK trending | `is_patriotic_relevant()` filter |
| `scan_reddit()` | Reddit RSS feeds | `is_patriotic_relevant()` filter |
| `scan_twitter_trends()` | trends24.in / getdaytrends.com | `is_patriotic_relevant()` filter |
| `scan_uk_news()` | Google News RSS + 8 news feeds | `is_patriotic_relevant()` filter |
| `scan_autocomplete()` | Google suggestqueries API | `is_patriotic_relevant()` + blocklist filter |

All six produce the same output shape (`keyword`, `source_keyword`, `rise_value`, `discovery_type`) and are merged in `main()`. This is **intentional multi-source aggregation**, not competing engines.

### 4.4 Overlapping Scoring Logic

Three scoring functions operate on the same item dicts sequentially:

| Function | Dimensions | Range |
|----------|-----------|-------|
| `analyse_keywords()` → `viral_score` | Latest + momentum + consistency | 0–100 |
| `score_content_potential()` | Fresh + British + Emotion + Debate | 0–100 |
| `score_opportunity_gap()` | Demand + competition | 0–10, labeled |

These are **complementary scoring layers**, not duplicates. Final sort uses `content_score`.

### 4.5 Fallback vs Live Data

`fallback_results()` generates **random synthetic scores** when live Google Trends data returns fewer than 5 results. These are indistinguishable from real results in the output JSON — no `"source": "fallback"` flag is set.

**Impact:** The dashboard may display fabricated trend data during rate-limit or API failure events.

---

## 5. GitHub Actions Flow

### 5.1 Active Workflow: `.github/workflows/trends.yml`

```yaml
name: Patriot Trends Scanner

on:
  schedule:
    - cron: "0 */4 * * *"      # Every 4 hours
  workflow_dispatch:            # Manual trigger

permissions:
  contents: write               # Required for last-run.txt commit
```

### 5.2 Step-by-Step Execution

```
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Get repository code                             │
│   actions/checkout@v4                                   │
├─────────────────────────────────────────────────────────┤
│ STEP 2: Set up Python 3.11                              │
│   actions/setup-python@v5                               │
├─────────────────────────────────────────────────────────┤
│ STEP 3: Install requirements                            │
│   pip install -r requirements.txt                       │
│   (installs: pytrends, pandas, requests)                │
├─────────────────────────────────────────────────────────┤
│ STEP 4: Run trends scanner                              │
│   python trends.py                                      │
│   → produces results.json + results.txt                 │
├─────────────────────────────────────────────────────────┤
│ STEP 5: Upload Results (artifact)                       │
│   actions/upload-artifact@v4                            │
│   → patriot-radar-results (results.txt, results.json) │
├─────────────────────────────────────────────────────────┤
│ STEP 6: Push results to dashboard website               │
│   git clone patriot-radar-dashboard (via DASHBOARD_TOKEN)│
│   cp results.json → dashboard/results.json              │
│   git commit + push dashboard repo                      │
├─────────────────────────────────────────────────────────┤
│ STEP 7: Keep workflow active (heartbeat)                │
│   date > last-run.txt                                   │
│   git commit + push to THIS repo                        │
└─────────────────────────────────────────────────────────┘
```

### 5.3 Schedule History

| Commit | Change | Cron |
|--------|--------|------|
| `ff7576c` | Reduce to stay within free tier | `*/30 * * * *` (every 30 min) |
| `35c01df` | Avoid Google Trends rate limits | `0 */4 * * *` (every 4 hours) |

**Current schedule: every 4 hours.** The stale `patriot trends scanner` file still references the old 30-minute schedule.

### 5.4 Secrets Required

| Secret | Used In | Purpose |
|--------|---------|---------|
| `GITHUB_TOKEN` | Steps 1, 5, 7 (automatic) | Checkout, artifact upload |
| `DASHBOARD_TOKEN` | Step 6 | Clone and push to `patriot-radar-dashboard` repo |

### 5.5 Error Handling

| Step | Failure Behavior |
|------|-----------------|
| Scanner run | Workflow fails (no subsequent steps) |
| Dashboard push | `|| echo "Dashboard push failed"` — silently continues |
| Heartbeat push | `|| echo "Push failed - will retry next cycle"` — silently continues |

### 5.6 What Gets Committed to This Repo

| File | Committed? | By Whom |
|------|-----------|---------|
| `last-run.txt` | ✅ Every run | CI Step 7 |
| `results.json` | ❌ Never | Only pushed to dashboard repo |
| `results.txt` | ❌ Never | Only stored as GitHub artifact |
| `trends.py` | Only on manual edits | Developer |

Recent git log confirms this: the last ~15 commits are all `Update scanner timestamp`.

### 5.7 Is the Correct Pipeline Running?

**Yes.** GitHub Actions exclusively executes workflows from `.github/workflows/`. The file at repo root named `patriot trends scanner` is **never executed** by GitHub Actions regardless of its contents.

---

## 6. Cleanup Recommendations

Ordered by risk level — safest actions first.

### Phase 1: Zero-Risk Deletions

| # | Action | Rationale | Precondition |
|---|--------|-----------|--------------|
| 1 | **Delete `patriot trends scanner`** | Not executed by GitHub Actions. Incomplete stale copy of old workflow. First line is a copy-paste error. Causes confusion about cron schedule. | None — safe immediately |
| 2 | **Verify `patriot-radar-dashboard` repo** has a working UI that reads `results.json` | Confirms `index.html` in this repo is truly redundant before removal | Check external repo |

### Phase 2: Low-Risk Consolidation

| # | Action | Rationale | Precondition |
|---|--------|-----------|--------------|
| 3 | **Delete `index.html`** from this repo | Orphaned, broken JS, static hardcoded data, not wired to `results.json`, not deployed | Dashboard repo confirmed working (step 2) |
| 4 | **Write proper `README.md`** | Document entry point, CI schedule, output flow, external dashboard dependency | None |

### Phase 3: Engine Hardening (No Deletions)

| # | Action | Rationale | Risk |
|---|--------|-----------|------|
| 5 | **Deduplicate `QUESTIONS` dict keys** | ~18 keys silently overwritten; later entries win | Low — behavior change only for overridden questions |
| 6 | **Add `"source": "fallback"` flag** to `fallback_results()` output | Dashboard can filter synthetic data | Low — additive JSON field |
| 7 | **Add `"source": "live"` flag** to real `analyse_keywords()` output | Enables filtering on dashboard side | Low — additive JSON field |
| 8 | **Surface CI push failures** instead of `|| echo` swallowing | Dashboard may serve stale data silently | Low — workflow logging only |

### Phase 4: Structural Refactor (Future, Optional)

| # | Action | Rationale | Risk |
|---|--------|-----------|------|
| 9 | **Extract discovery modules** into separate files (e.g. `discovery/reddit.py`, `discovery/news.py`) | ~1,300-line monolith is hard to test and maintain | Medium — organizational only |
| 10 | **Extract scoring modules** (e.g. `scoring/content.py`, `scoring/opportunity.py`) | Same reason | Medium |
| 11 | **Add integration tests** with mocked HTTP responses | Fragile scrapers (Reddit, Twitter, news RSS) break silently | Medium |

### What NOT to Do

| Action | Why Not |
|--------|---------|
| Create a second scanner script | No competing engine exists; would add confusion |
| Change cron back to 30 minutes | Commit `35c01df` moved to 4 hours specifically to avoid Google Trends rate limits |
| Merge `index.html` into this repo's CI | Production already pushes JSON to external dashboard repo |
| Delete `trends.py` | Sole production engine |
| Delete `.github/workflows/trends.yml` | Sole CI pipeline |
| Delete `last-run.txt` | CI heartbeat; regenerated each run but file should remain tracked |

### Recommended Cleanup Order

```
1. Delete "patriot trends scanner"          ← do now, zero risk
2. Verify dashboard repo works              ← confirm before step 3
3. Delete index.html                        ← after step 2
4. Write README.md                          ← document real architecture
5. Deduplicate QUESTIONS dict               ← safe code cleanup
6. Add source flags to fallback results     ← data quality improvement
7. (Future) Extract modules from monolith   ← when ready to refactor
```

---

## Appendix: Git History Timeline (Key Events)

| Commit | Event |
|--------|-------|
| `d6466f0` | Initial commit |
| `694109d` | Create `patriot trends scanner` (stale workflow copy) |
| `cc726de` | Create `.github/workflows/trends.yml` |
| `2892f04` | Create `index.html` (dashboard prototype) |
| `5aa2f8a` | Level 3: Reddit, Twitter, UK News scanning |
| `5fa153b` | Add Google Autocomplete scanning |
| `ff7576c` | Reduce scan frequency to every 30 minutes |
| `284c65d` | Implement push results to dashboard job |
| `35c01df` | Reduce scan frequency to every 4 hours (rate limits) |
| `4e5adf3` | Add content scoring (Fresh + British + Emotion + Debate) |
| `a8bc4b4` | Add Opportunity Gap scoring (latest) |

---

*End of analysis report.*
