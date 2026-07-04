# TikTok Insights Engine

Full-stack Next.js app that turns TikTok niche research into client-ready business insights.

## Pipeline

1. **Search** — Apify actor `GdWCkxBtKWOsKjdch` searches TikTok for the niche keyword
2. **Viral scoring** — Top 10–20 videos ranked by trend_score
3. **Comment scrape** — Apify actor `BDec00yAmCm1QbMEI` scrapes comments for those URLs
4. **Insights generation** — Extracts pain points, questions, opportunities, hooks, buying signals, and a plain-English summary
5. **Store** — Saves to Supabase `tiktok_results` (`videos`, `comments`, `insights`, `trend_scores`)
6. **Display** — Dashboard shows rising videos, insights, and summary

## Setup

### 1. Environment variables

Copy `.env.example` to `.env.local` and fill in:

```bash
APIFY_TOKEN=your_apify_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_or_anon_key

# Optional — richer insights via OpenAI (falls back to keyword analysis)
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
```

### 2. Supabase table

Run the SQL migration in your Supabase SQL editor:

```bash
sql/tiktok_results.sql
```

### 3. Install and run

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), enter a niche (e.g. `fitness coaching`), and click **Run Scan**.

## API

`POST /api/run-scan`

```json
{ "niche": "fitness coaching" }
```

Returns viral videos, trend scores, structured insights, comments, and the Supabase row id on success.

## Insights output

```json
{
  "pain_points": [],
  "questions": [],
  "content_opportunities": [],
  "hooks": [],
  "buying_signals": [],
  "summary": ""
}
```

If OpenAI is not configured or the LLM call fails, insights fall back to keyword/pattern analysis without breaking the pipeline.
