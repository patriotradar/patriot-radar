const APIFY_BASE = "https://api.apify.com/v2";

export const TIKTOK_SEARCH_ACTOR_ID = "GdWCkxBtKWOsKjdch";
export const TIKTOK_COMMENTS_ACTOR_ID = "BDec00yAmCm1QbMEI";

const POLL_INTERVAL_MS = 3000;
const MAX_WAIT_MS = 5 * 60 * 1000;

type ApifyRun = {
  id: string;
  status: string;
  defaultDatasetId?: string;
};

function getApifyToken(): string {
  const token = process.env.APIFY_TOKEN;
  if (!token) {
    throw new Error("APIFY_TOKEN is not configured");
  }
  return token;
}

async function apifyFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = getApifyToken();
  const url = `${APIFY_BASE}${path}${path.includes("?") ? "&" : "?"}token=${token}`;
  return fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
}

async function waitForRun(runId: string): Promise<ApifyRun> {
  const started = Date.now();

  while (Date.now() - started < MAX_WAIT_MS) {
    const res = await apifyFetch(`/actor-runs/${runId}`);
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Failed to poll Apify run ${runId}: ${res.status} ${body}`);
    }

    const json = (await res.json()) as { data: ApifyRun };
    const run = json.data;
    const terminal = ["SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"];

    if (terminal.includes(run.status)) {
      if (run.status !== "SUCCEEDED") {
        throw new Error(`Apify run ${runId} ended with status ${run.status}`);
      }
      return run;
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  throw new Error(`Apify run ${runId} timed out after ${MAX_WAIT_MS / 1000}s`);
}

export async function runApifyActor<T extends Record<string, unknown>>(
  actorId: string,
  input: T,
): Promise<Record<string, unknown>[]> {
  const startRes = await apifyFetch(`/acts/${actorId}/runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });

  if (!startRes.ok) {
    const body = await startRes.text();
    throw new Error(`Failed to start Apify actor ${actorId}: ${startRes.status} ${body}`);
  }

  const startJson = (await startRes.json()) as { data: ApifyRun };
  const run = await waitForRun(startJson.data.id);

  if (!run.defaultDatasetId) {
    return [];
  }

  const itemsRes = await apifyFetch(
    `/datasets/${run.defaultDatasetId}/items?format=json&clean=true`,
  );

  if (!itemsRes.ok) {
    const body = await itemsRes.text();
    throw new Error(`Failed to fetch Apify dataset: ${itemsRes.status} ${body}`);
  }

  const items = (await itemsRes.json()) as unknown;
  if (!Array.isArray(items)) {
    return [];
  }

  return items.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
}

export function extractViewCount(item: Record<string, unknown>): number {
  const stats = item.stats as Record<string, unknown> | undefined;
  const raw =
    item.playCount ??
    item.play_count ??
    stats?.playCount ??
    stats?.play_count ??
    item.views ??
    0;

  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function extractVideoUrl(item: Record<string, unknown>): string {
  const url = item.webVideoUrl ?? item.videoUrl ?? item.url ?? "";
  return typeof url === "string" ? url.trim() : "";
}

export function selectTopViralVideos(
  items: Record<string, unknown>[],
  minCount = 10,
  maxCount = 20,
): { url: string; views: number; item: Record<string, unknown> }[] {
  const withViews = items
    .map((item) => ({
      url: extractVideoUrl(item),
      views: extractViewCount(item),
      item,
    }))
    .filter((entry) => entry.url.length > 0);

  withViews.sort((a, b) => b.views - a.views);

  if (withViews.length === 0) {
    return [];
  }

  const target = Math.min(Math.max(minCount, 1), maxCount, withViews.length);
  return withViews.slice(0, target);
}

export async function searchTikTokByNiche(niche: string): Promise<Record<string, unknown>[]> {
  return runApifyActor(TIKTOK_SEARCH_ACTOR_ID, {
    searchQueries: [niche],
    searchSection: "/video",
    resultsPerPage: 50,
    shouldDownloadVideos: false,
    shouldDownloadCovers: false,
    shouldDownloadSubtitles: false,
  });
}

export async function scrapeTikTokComments(
  videoUrls: string[],
  maxComments = 200,
): Promise<Record<string, unknown>[]> {
  if (videoUrls.length === 0) {
    return [];
  }

  return runApifyActor(TIKTOK_COMMENTS_ACTOR_ID, {
    videoUrls,
    maxComments,
    headless: true,
  });
}
