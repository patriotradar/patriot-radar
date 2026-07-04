# TikTok Viral Research Dashboard

Full-stack Next.js app that runs an end-to-end TikTok research pipeline from a single niche input.

## Pipeline

1. **Search** — Apify actor `GdWCkxBtKWOsKjdch` searches TikTok for the niche keyword
2. **Viral filter** — Results are sorted by view count; top 10–20 videos are selected
3. **Comment scrape** — Apify actor `BDec00yAmCm1QbMEI` scrapes comments for those video URLs
4. **Store** — Final payload is saved to Supabase table `tiktok_results`
5. **Display** — JSON response is shown on the homepage

## Setup

### 1. Environment variables

Copy `.env.example` to `.env.local` and fill in:

```bash
APIFY_TOKEN=your_apify_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_or_anon_key
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

Returns viral video metadata, scraped comments, and the Supabase row id on success.
