const APIFY_BASE = "https://api.apify.com/v2";

export const TIKTOK_SEARCH_ACTOR_ID = "GdWCkxBtKWOsKjdch";
export const TIKTOK_COMMENTS_ACTOR_ID = "BDec00yAmCm1QbMEI";

const POLL_INTERVAL_MS = 3000;
const MAX_WAIT_MS = 5 * 60 * 1000;
const DATASET_FETCH_RETRIES = 4;
const DATASET_FETCH_RETRY_MS = 2000;

const TERMINAL_STATUSES = new Set(["SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"]);
const RUNNING_STATUSES = new Set(["READY", "RUNNING", "ABORTING"]);

type ApifyRun = {
  id: string;
  status: string;
  defaultDatasetId?: string;
};

export type ApifyActorRunOutcome =
  | {
      ok: true;
      runId: string;
      datasetId: string;
      items: Record<string, unknown>[];
    }
  | {
      ok: false;
      runId?: string;
      message: string;
    };

function getApifyToken(): string | null {
  return process.env.APIFY_TOKEN ?? null;
}

function apifyTokenQuery(): string {
  const token = getApifyToken();
  if (!token) {
    throw new Error("APIFY_TOKEN is not configured");
  }
  return `token=${encodeURIComponent(token)}`;
}

async function apifyFetch(path: string, init?: RequestInit): Promise<Response> {
  const separator = path.includes("?") ? "&" : "?";
  const url = `${APIFY_BASE}${path}${separator}${apifyTokenQuery()}`;
  return fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
}

function safeNumber(value: unknown, fallback = 0): number {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : undefined;
}

export function extractViewCount(item: Record<string, unknown>): number {
  const stats = asRecord(item.stats);
  return safeNumber(
    item.playCount ??
      item.play_count ??
      stats?.playCount ??
      stats?.play_count ??
      item.views,
  );
}

export function extractLikeCount(item: Record<string, unknown>): number {
  const stats = asRecord(item.stats);
  return safeNumber(
    item.diggCount ??
      item.digg_count ??
      item.likes ??
      stats?.diggCount ??
      stats?.digg_count ??
      stats?.likes,
  );
}

export function extractCommentCount(item: Record<string, unknown>): number {
  const stats = asRecord(item.stats);
  return safeNumber(
    item.commentCount ??
      item.comment_count ??
      stats?.commentCount ??
      stats?.comment_count ??
      stats?.comments,
  );
}

export function extractCreateTimeSeconds(item: Record<string, unknown>): number | null {
  const videoMeta = asRecord(item.videoMeta);
  const raw =
    item.createTime ??
    item.create_time ??
    item.timestamp ??
    videoMeta?.createTime ??
    videoMeta?.create_time;

  if (raw === null || raw === undefined || raw === "") {
    return null;
  }

  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }

  // Apify TikTok items typically use unix seconds; tolerate millisecond values.
  return parsed > 1_000_000_000_000 ? Math.floor(parsed / 1000) : Math.floor(parsed);
}

export function computeAgeHours(createTimeSeconds: number | null): {
  ageHours: number;
  lowConfidence: boolean;
} {
  if (createTimeSeconds === null) {
    // Missing timestamp: include video with conservative age assumption.
    return { ageHours: 168, lowConfidence: true };
  }

  const nowSeconds = Date.now() / 1000;
  const ageHours = Math.max((nowSeconds - createTimeSeconds) / 3600, 0);
  return { ageHours, lowConfidence: false };
}

export function computeTrendScore(
  views: number,
  likes: number,
  comments: number,
  ageHours: number,
): number {
  const safeAge = Math.max(ageHours, 1);
  return views / safeAge + 0.5 * (likes / safeAge) + 0.5 * (comments / safeAge);
}

export function extractVideoUrl(item: Record<string, unknown>): string {
  const url = item.webVideoUrl ?? item.videoUrl ?? item.url ?? "";
  return typeof url === "string" ? url.trim() : "";
}

export type ScoredVideo = {
  url: string;
  views: number;
  likes: number;
  comments: number;
  ageHours: number;
  lowConfidence: boolean;
  trendScore: number;
  item: Record<string, unknown>;
};

export function scoreAndRankVideos(items: Record<string, unknown>[]): ScoredVideo[] {
  const scored = items
    .map((item) => {
      const url = extractVideoUrl(item);
      if (!url) {
        return null;
      }

      const views = extractViewCount(item);
      const likes = extractLikeCount(item);
      const comments = extractCommentCount(item);
      const { ageHours, lowConfidence } = computeAgeHours(extractCreateTimeSeconds(item));
      const trendScore = computeTrendScore(views, likes, comments, ageHours);

      return {
        url,
        views,
        likes,
        comments,
        ageHours,
        lowConfidence,
        trendScore,
        item,
      };
    })
    .filter((entry): entry is ScoredVideo => entry !== null);

  scored.sort((a, b) => b.trendScore - a.trendScore);
  return scored;
}

export function selectTopViralVideos(
  items: Record<string, unknown>[],
  minCount = 10,
  maxCount = 20,
): ScoredVideo[] {
  const ranked = scoreAndRankVideos(items);
  if (ranked.length === 0) {
    return [];
  }

  const target =
    ranked.length >= minCount ? Math.min(maxCount, ranked.length) : ranked.length;

  return ranked.slice(0, target);
}

async function startActorRun(
  actorId: string,
  input: Record<string, unknown>,
): Promise<{ ok: true; runId: string } | { ok: false; message: string }> {
  const startRes = await apifyFetch(`/acts/${actorId}/runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });

  if (!startRes.ok) {
    const body = await startRes.text();
    return {
      ok: false,
      message: `Failed to start Apify actor ${actorId}: ${startRes.status} ${body}`,
    };
  }

  const startJson = (await startRes.json()) as { data?: ApifyRun };
  const runId = startJson.data?.id;

  if (!runId) {
    return {
      ok: false,
      message: `Apify actor ${actorId} started but no run id was returned`,
    };
  }

  return { ok: true, runId };
}

async function waitForRunCompletion(
  runId: string,
): Promise<{ ok: true; run: ApifyRun } | { ok: false; message: string }> {
  const started = Date.now();

  while (Date.now() - started < MAX_WAIT_MS) {
    const res = await apifyFetch(`/actor-runs/${runId}`);
    if (!res.ok) {
      const body = await res.text();
      return {
        ok: false,
        message: `Failed to poll Apify run ${runId}: ${res.status} ${body}`,
      };
    }

    const json = (await res.json()) as { data?: ApifyRun };
    const run = json.data;

    if (!run?.status) {
      return {
        ok: false,
        message: `Apify run ${runId} returned an invalid status payload`,
      };
    }

    if (TERMINAL_STATUSES.has(run.status)) {
      if (run.status !== "SUCCEEDED") {
        return {
          ok: false,
          message: `Apify run ${runId} ended with status ${run.status}`,
        };
      }
      return { ok: true, run };
    }

    if (!RUNNING_STATUSES.has(run.status)) {
      return {
        ok: false,
        message: `Apify run ${runId} entered unexpected status ${run.status}`,
      };
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  return {
    ok: false,
    message: `Apify run ${runId} timed out after ${MAX_WAIT_MS / 1000}s`,
  };
}

async function fetchDatasetItems(
  datasetId: string,
): Promise<{ ok: true; items: Record<string, unknown>[] } | { ok: false; message: string }> {
  let lastError = "Unknown dataset fetch error";

  for (let attempt = 1; attempt <= DATASET_FETCH_RETRIES; attempt += 1) {
    const itemsRes = await apifyFetch(
      `/datasets/${datasetId}/items?format=json&clean=true`,
    );

    if (!itemsRes.ok) {
      lastError = `Failed to fetch Apify dataset ${datasetId}: ${itemsRes.status} ${await itemsRes.text()}`;
    } else {
      const items = (await itemsRes.json()) as unknown;
      if (!Array.isArray(items)) {
        return { ok: true, items: [] };
      }

      const normalized = items.filter(
        (item): item is Record<string, unknown> =>
          typeof item === "object" && item !== null,
      );

      return { ok: true, items: normalized };
    }

    if (attempt < DATASET_FETCH_RETRIES) {
      await new Promise((resolve) => setTimeout(resolve, DATASET_FETCH_RETRY_MS * attempt));
    }
  }

  return { ok: false, message: lastError };
}

export async function runApifyActor(
  actorId: string,
  input: Record<string, unknown>,
): Promise<ApifyActorRunOutcome> {
  if (!getApifyToken()) {
    return { ok: false, message: "APIFY_TOKEN is not configured" };
  }

  const started = await startActorRun(actorId, input);
  if (!started.ok) {
    return { ok: false, message: started.message };
  }

  const completed = await waitForRunCompletion(started.runId);
  if (!completed.ok) {
    return { ok: false, runId: started.runId, message: completed.message };
  }

  const datasetId = completed.run.defaultDatasetId;
  if (!datasetId) {
    return {
      ok: false,
      runId: started.runId,
      message: `Apify run ${started.runId} succeeded but defaultDatasetId is missing`,
    };
  }

  const dataset = await fetchDatasetItems(datasetId);
  if (!dataset.ok) {
    return { ok: false, runId: started.runId, message: dataset.message };
  }

  return {
    ok: true,
    runId: started.runId,
    datasetId,
    items: dataset.items,
  };
}

export async function searchTikTokByNiche(niche: string): Promise<ApifyActorRunOutcome> {
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
): Promise<ApifyActorRunOutcome> {
  if (videoUrls.length === 0) {
    return { ok: false, message: "No video URLs provided for comment scrape" };
  }

  return runApifyActor(TIKTOK_COMMENTS_ACTOR_ID, {
    videoUrls,
    maxComments,
    headless: true,
  });
}
