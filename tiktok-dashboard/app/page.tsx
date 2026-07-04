"use client";

import { useState } from "react";

type ScanResponse = Record<string, unknown>;

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
        setError((data.error as string) || `Scan failed (${res.status})`);
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

  return (
    <div className="min-h-full bg-zinc-950 text-zinc-100">
      <main className="mx-auto flex min-h-full max-w-3xl flex-col gap-8 px-6 py-16">
        <header className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-widest text-pink-400">
            TikTok Viral Research
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Niche comment intelligence dashboard
          </h1>
          <p className="max-w-xl text-zinc-400">
            Enter a niche to search TikTok, filter the top viral videos by views,
            scrape comments, and store results in Supabase.
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
              Pipeline running: search → viral filter → comment scrape → Supabase
              store. This can take a few minutes.
            </p>
          )}

          {error && (
            <p className="mt-4 rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {error}
            </p>
          )}
        </section>

        {result && (
          <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
            <h2 className="mb-3 text-lg font-medium">Results</h2>
            <pre className="max-h-[32rem] overflow-auto rounded-xl bg-zinc-950 p-4 text-xs leading-relaxed text-zinc-300">
              {JSON.stringify(result, null, 2)}
            </pre>
          </section>
        )}
      </main>
    </div>
  );
}
