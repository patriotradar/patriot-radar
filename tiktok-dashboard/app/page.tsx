"use client";

import { useEffect, useState } from "react";

// ---- types ---------------------------------------------------------------

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
  views?: number;
  likes?: number;
  comments?: number;
  ageHours?: number;
  lowConfidence?: boolean;
};

type ScanResponse = {
  success?: boolean;
  error?: string;
  viralVideos?: ViralVideo[];
  insights?: Insights;
};

type ProgressStep =
  | "searching"
  | "scoring"
  | "scraping_comments"
  | "generating_insights"
  | "storing"
  | "done";

type ProgressEvent = {
  step: ProgressStep;
  message: string;
};

type RecentScan = {
  id: string;
  niche: string;
  created_at: string;
  video_count: number;
  insight_summary: string;
};

// ---- helpers -------------------------------------------------------------

const STEP_EMOJI: Record<ProgressStep, string> = {
  searching: "🔍",
  scoring: "🏆",
  scraping_comments: "💬",
  generating_insights: "🧠",
  storing: "💾",
  done: "✅",
};

function formatAge(ageHours: number): string {
  if (ageHours < 24) {
    return `${Math.round(ageHours)}h ago`;
  }
  return `${Math.round(ageHours / 24)}d ago`;
}

function formatCount(n: number): string {
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`;
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(1)}K`;
  }
  return String(n);
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

// ---- sub-components ------------------------------------------------------

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

function ProgressLog({ steps }: { steps: ProgressEvent[] }) {
  if (steps.length === 0) return null;
  return (
    <ul className="space-y-1.5">
      {steps.map((s, i) => (
        <li key={i} className="flex items-start gap-2 text-sm">
          <span aria-hidden="true">{STEP_EMOJI[s.step]}</span>
          <span className={s.step === "done" ? "text-green-300" : "text-pink-200"}>
            {s.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ScanHistoryPanel({ scans }: { scans: RecentScan[] | null }) {
  const [open, setOpen] = useState(false);
  const loading = scans === null;

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 text-left"
        aria-expanded={open}
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-300">
          Scan History
        </h2>
        <span className="text-xs text-zinc-500">{open ? "▲ hide" : "▼ show"}</span>
      </button>

      {open && (
        <div className="mt-4">
          {loading && <p className="text-sm text-zinc-500">Loading history…</p>}
          {!loading && (scans ?? []).length === 0 && (
            <p className="text-sm text-zinc-500">No scans yet. Run your first scan above.</p>
          )}
          {!loading && (scans ?? []).length > 0 && (
            <ul className="space-y-3">
              {(scans ?? []).map((scan) => (
                <li
                  key={scan.id}
                  className="rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-zinc-200 capitalize">
                      {scan.niche}
                    </span>
                    <span className="shrink-0 text-xs text-zinc-500">
                      {timeAgo(scan.created_at)}
                      {scan.video_count > 0 && (
                        <> · {scan.video_count} video{scan.video_count !== 1 ? "s" : ""}</>
                      )}
                    </span>
                  </div>
                  {scan.insight_summary && (
                    <p className="mt-1 text-xs leading-relaxed text-zinc-400 line-clamp-2">
                      {scan.insight_summary}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

// ---- main page -----------------------------------------------------------

export default function Home() {
  const [niche, setNiche] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [progressSteps, setProgressSteps] = useState<ProgressEvent[]>([]);
  const [history, setHistory] = useState<RecentScan[] | null>(null);

  async function fetchHistory(): Promise<RecentScan[]> {
    try {
      const res = await fetch("/api/scan-history");
      if (!res.ok) return [];
      const data = (await res.json()) as { scans: RecentScan[] };
      return data.scans ?? [];
    } catch {
      return [];
    }
  }

  // Load history on mount — setState must be in a .then() callback to satisfy
  // the react-hooks/set-state-in-effect rule (no synchronous setState in effect body).
  useEffect(() => {
    void fetchHistory().then(setHistory);
  }, []);

  async function handleRunScan() {
    const trimmed = niche.trim();
    if (!trimmed) {
      setError("Enter a niche to scan");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setProgressSteps([]);

    try {
      const res = await fetch("/api/run-scan", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ niche: trimmed }),
      });

      if (!res.ok || !res.body) {
        // Fallback: parse as JSON (non-streaming error response)
        const data = (await res.json()) as ScanResponse;
        setError(data.error ?? `Scan failed (${res.status})`);
        setResult(data);
        return;
      }

      // Consume SSE stream
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse complete SSE messages
        const messages = buffer.split("\n\n");
        buffer = messages.pop() ?? "";

        for (const message of messages) {
          const eventMatch = message.match(/^event: (\w+)/m);
          const dataMatch = message.match(/^data: (.+)$/m);
          if (!eventMatch || !dataMatch) continue;

          const eventType = eventMatch[1];
          let parsed: unknown;
          try {
            parsed = JSON.parse(dataMatch[1]);
          } catch {
            continue;
          }

          if (eventType === "progress") {
            const evt = parsed as ProgressEvent;
            setProgressSteps((prev) => [...prev, evt]);
          } else if (eventType === "result") {
            setResult(parsed as ScanResponse);
          } else if (eventType === "error") {
            const errData = parsed as ScanResponse;
            setError(errData.error ?? "Scan failed");
            setResult(errData);
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
      // Refresh history after scan completes
      void fetchHistory().then(setHistory);
    }
  }

  const insights = result?.insights;
  const videos = result?.viralVideos ?? [];
  const hasResults = Boolean(result?.success && insights);

  return (
    <div className="min-h-full bg-zinc-950 text-zinc-100">
      <main className="mx-auto flex min-h-full max-w-4xl flex-col px-6 py-10">
        <header className="mb-8 space-y-2">
          <p className="text-sm font-medium uppercase tracking-widest text-pink-400">
            TikTok Insights Engine
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Niche intelligence dashboard
          </h1>
          <p className="max-w-2xl text-zinc-400">
            Discover what is trending, what customers care about, and what to post next.
          </p>
        </header>

        {/* SECTION 1: Control Panel — always visible */}
        <section
          aria-label="Trend detection control panel"
          className="sticky top-0 z-10 rounded-2xl border border-zinc-700/80 bg-zinc-900/95 p-6 shadow-2xl shadow-black/40 backdrop-blur"
        >
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-300">
              Control Panel
            </h2>
            <span className="rounded-full border border-zinc-700 px-2.5 py-0.5 text-xs text-zinc-500">
              Always available
            </span>
          </div>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="flex-1">
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
                placeholder="Enter niche (e.g. fitness coaching)"
                disabled={loading}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-zinc-100 placeholder:text-zinc-500 outline-none transition focus:border-pink-500 focus:ring-2 focus:ring-pink-500/30 disabled:opacity-60"
              />
            </div>

            <button
              type="button"
              onClick={() => void handleRunScan()}
              disabled={loading}
              aria-label="Detect TikTok trends for niche"
              className="inline-flex h-[46px] shrink-0 items-center justify-center rounded-xl bg-pink-500 px-6 text-sm font-semibold text-white transition hover:bg-pink-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
            >
              {loading ? "Detecting..." : "Detect Trends"}
            </button>
          </div>

          {error && !loading && (
            <p
              role="alert"
              className="mt-4 rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-300"
            >
              {error}
            </p>
          )}
        </section>

        {/* SECTION 2: Live pipeline progress */}
        {(loading || progressSteps.length > 0) && (
          <section
            aria-live="polite"
            aria-busy={loading}
            className="mt-6 rounded-2xl border border-pink-900/40 bg-pink-950/20 px-6 py-5"
          >
            <div className="mb-3 flex items-center gap-3">
              {loading && (
                <span
                  className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-pink-400/30 border-t-pink-400"
                  aria-hidden="true"
                />
              )}
              <p className="text-sm font-medium text-pink-200">
                {loading ? "Automation running…" : "Automation complete"}
              </p>
            </div>
            <ProgressLog steps={progressSteps} />
          </section>
        )}

        {/* SECTION 3: Results Area */}
        {hasResults && insights && (
          <div className="mt-8 flex flex-col gap-6">
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
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
                        <span className="text-pink-400">
                          Trend score: {video.trendScore.toFixed(2)}
                        </span>
                        {typeof video.views === "number" && video.views > 0 && (
                          <span>👁 {formatCount(video.views)} views</span>
                        )}
                        {typeof video.likes === "number" && video.likes > 0 && (
                          <span>❤️ {formatCount(video.likes)} likes</span>
                        )}
                        {typeof video.comments === "number" && video.comments > 0 && (
                          <span>💬 {formatCount(video.comments)} comments</span>
                        )}
                        {typeof video.ageHours === "number" && (
                          <span className={video.lowConfidence ? "opacity-50" : ""}>
                            🕒 {formatAge(video.ageHours)}
                            {video.lowConfidence ? " (est.)" : ""}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-2xl border border-pink-900/40 bg-zinc-900/60 p-6">
              <h2 className="mb-4 text-lg font-medium text-pink-300">Insights</h2>
              <div className="grid gap-6 sm:grid-cols-2">
                <InsightList title="Pain points" items={insights.pain_points} />
                <InsightList title="Questions" items={insights.questions} />
                <InsightList title="Buying signals" items={insights.buying_signals} />
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
              <h2 className="mb-4 text-lg font-medium text-pink-300">
                What You Should Post Next
              </h2>
              {insights.summary && (
                <p className="mb-5 text-sm leading-relaxed text-zinc-300">{insights.summary}</p>
              )}
              <div className="grid gap-6 sm:grid-cols-2">
                <InsightList
                  title="Content opportunities"
                  items={insights.content_opportunities}
                />
                <InsightList title="Hooks" items={insights.hooks} />
              </div>
            </section>
          </div>
        )}

        {/* SECTION 4: Scan History */}
        <div className="mt-8">
          <ScanHistoryPanel scans={history} />
        </div>
      </main>
    </div>
  );
}
