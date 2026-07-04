"use client";

import { useState } from "react";

type Insights = {
  pain_points: string[];
  questions: string[];
  content_opportunities: string[];
  hooks: string[];
  buying_signals: string[];
  summary: string;
};

type ViralVideo = {
  caption?: string;
  trendScore: number;
  url?: string;
};

type ScanResponse = {
  success?: boolean;
  error?: string;
  viralVideos?: ViralVideo[];
  insights?: Insights;
};

function InsightList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return (
      <div>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">{title}</h3>
        <p className="text-sm text-zinc-500">Nothing strong enough to surface yet.</p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-zinc-200">{title}</h3>
      <ul className="list-disc space-y-2 pl-5 text-sm text-zinc-300">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function Home() {
  const [niche, setNiche] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResponse | null>(null);

  async function handleRunScan() {
    const trimmed = niche.trim();
    if (!trimmed) {
      setError("Enter a niche to scan");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/run-scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ niche: trimmed }),
      });

      const data = (await res.json()) as ScanResponse;

      if (!res.ok) {
        setError(data.error || `Scan failed (${res.status})`);
        setResult(data);
        return;
      }

      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const insights = result?.insights;
  const videos = result?.viralVideos ?? [];

  return (
    <div className="min-h-full bg-zinc-950 text-zinc-100">
      <main className="mx-auto flex min-h-full max-w-3xl flex-col gap-8 px-6 py-16">
        <header className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-widest text-pink-400">
            TikTok Insights Engine
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Niche intelligence dashboard
          </h1>
          <p className="max-w-xl text-zinc-400">
            Enter a niche to discover what is trending, what customers are saying,
            and what content to create next.
          </p>
        </header>

        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-xl">
          <label htmlFor="niche" className="mb-2 block text-sm font-medium text-zinc-300">
            Niche
          </label>
          <input
            id="niche"
            type="text"
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !loading) {
                void handleRunScan();
              }
            }}
            placeholder='e.g. "fitness coaching", "real estate", "crypto"'
            disabled={loading}
            className="mb-4 w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-zinc-100 placeholder:text-zinc-500 outline-none ring-pink-500/0 transition focus:border-pink-500 focus:ring-2 focus:ring-pink-500/30 disabled:opacity-60"
          />

          <button
            type="button"
            onClick={() => void handleRunScan()}
            disabled={loading || !niche.trim()}
            className="inline-flex items-center justify-center rounded-xl bg-pink-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-pink-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
          >
            {loading ? (
              <>
                <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Running scan…
              </>
            ) : (
              "Run Scan"
            )}
          </button>

          {loading && (
            <p className="mt-4 text-sm text-zinc-400">
              Pipeline running: search → viral scoring → comment scrape → insights
              generation → Supabase store. This can take a few minutes.
            </p>
          )}

          {error && (
            <p className="mt-4 rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {error}
            </p>
          )}
        </section>

        {result?.success && (
          <div className="flex flex-col gap-6">
            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
              <h2 className="mb-4 text-lg font-medium text-pink-300">Rising Videos</h2>
              {videos.length === 0 ? (
                <p className="text-sm text-zinc-500">No rising videos found.</p>
              ) : (
                <ul className="space-y-3">
                  {videos.map((video) => (
                    <li
                      key={video.url ?? video.caption}
                      className="rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-3"
                    >
                      <p className="text-sm text-zinc-200">
                        {video.caption?.trim() || "Untitled video"}
                      </p>
                      <p className="mt-1 text-xs text-pink-400">
                        Trend score: {video.trendScore.toFixed(2)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {insights && (
              <section className="rounded-2xl border border-pink-900/40 bg-zinc-900/60 p-6">
                <h2 className="mb-4 text-lg font-medium text-pink-300">Insights</h2>
                <div className="grid gap-6 sm:grid-cols-2">
                  <InsightList title="Pain points" items={insights.pain_points} />
                  <InsightList title="Questions" items={insights.questions} />
                  <InsightList
                    title="Content opportunities"
                    items={insights.content_opportunities}
                  />
                  <InsightList title="Hooks" items={insights.hooks} />
                  <InsightList title="Buying signals" items={insights.buying_signals} />
                </div>
              </section>
            )}

            {insights?.summary && (
              <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h2 className="mb-3 text-lg font-medium text-pink-300">Summary</h2>
                <p className="text-sm leading-relaxed text-zinc-300">{insights.summary}</p>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
