import { scrapeTikTokComments, searchTikTokByNiche, selectTopViralVideos } from "./apify";
import { generateInsights, type InsightsResult } from "./insights";
import { storeTikTokResults } from "./supabase";

export type PipelineStep =
  | "invalid_input"
  | "config_missing"
  | "search_failed"
  | "dataset_missing"
  | "search_empty"
  | "viral_selection_failed"
  | "comment_fetch_failed"
  | "supabase_failed";

export type ViralVideoResult = {
  url: string;
  views: number;
  likes: number;
  comments: number;
  ageHours: number;
  lowConfidence: boolean;
  trendScore: number;
  caption?: string;
  author?: string;
};

export type ScanPipelineResult = {
  success: boolean;
  niche: string;
  step?: PipelineStep;
  searchResultCount: number;
  viralVideoCount: number;
  videoUrls: string[];
  viralVideos: ViralVideoResult[];
  comments: Record<string, unknown>[];
  insights: InsightsResult;
  trend_scores: { url: string; trendScore: number; caption?: string }[];
  stored: {
    id: string;
    created_at: string;
  } | null;
  error?: string;
  apify?: {
    searchRunId?: string;
    commentRunId?: string;
  };
};

function extractCaption(item: Record<string, unknown>): string {
  const text = item.text ?? item.desc ?? item.description ?? item.title ?? "";
  return typeof text === "string" ? text.trim() : "";
}

function extractAuthor(item: Record<string, unknown>): string {
  const authorMeta =
    typeof item.authorMeta === "object" && item.authorMeta !== null
      ? (item.authorMeta as Record<string, unknown>)
      : undefined;
  const author = item.author ?? authorMeta?.name ?? authorMeta?.nickName ?? "";
  return typeof author === "string" ? author.trim() : "";
}

function fail(
  base: ScanPipelineResult,
  step: PipelineStep,
  error: string,
  extra?: Partial<ScanPipelineResult>,
): ScanPipelineResult {
  return {
    ...base,
    success: false,
    step,
    error,
    ...extra,
  };
}

function hasRequiredConfig(): string | null {
  if (!process.env.APIFY_TOKEN) {
    return "APIFY_TOKEN is not configured";
  }
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_KEY) {
    return "SUPABASE_URL and SUPABASE_KEY must be configured";
  }
  return null;
}

const EMPTY_INSIGHTS: InsightsResult = {
  pain_points: [],
  questions: [],
  content_opportunities: [],
  hooks: [],
  buying_signals: [],
  summary: "",
};

export async function runScanPipeline(niche: string): Promise<ScanPipelineResult> {
  const trimmedNiche = niche.trim();

  const base: ScanPipelineResult = {
    success: false,
    niche: trimmedNiche,
    searchResultCount: 0,
    viralVideoCount: 0,
    videoUrls: [],
    viralVideos: [],
    comments: [],
    insights: { ...EMPTY_INSIGHTS },
    trend_scores: [],
    stored: null,
    apify: {},
  };

  if (!trimmedNiche) {
    return fail(base, "invalid_input", "Niche is required");
  }

  const configError = hasRequiredConfig();
  if (configError) {
    return fail(base, "config_missing", configError);
  }

  const searchOutcome = await searchTikTokByNiche(trimmedNiche);
  if (!searchOutcome.ok) {
    const step: PipelineStep = searchOutcome.message.includes("defaultDatasetId")
      ? "dataset_missing"
      : "search_failed";

    return fail(base, step, searchOutcome.message, {
      apify: { searchRunId: searchOutcome.runId },
    });
  }

  base.apify = { searchRunId: searchOutcome.runId };
  base.searchResultCount = searchOutcome.items.length;

  if (searchOutcome.items.length === 0) {
    return fail(base, "search_empty", "Apify search returned no videos for this niche", {
      apify: { searchRunId: searchOutcome.runId },
    });
  }

  const viralVideos = selectTopViralVideos(searchOutcome.items, 10, 20);
  base.viralVideoCount = viralVideos.length;
  base.videoUrls = viralVideos.map((video) => video.url);
  base.viralVideos = viralVideos.map((video) => ({
    url: video.url,
    views: video.views,
    likes: video.likes,
    comments: video.comments,
    ageHours: video.ageHours,
    lowConfidence: video.lowConfidence,
    trendScore: video.trendScore,
    caption: extractCaption(video.item),
    author: extractAuthor(video.item),
  }));
  base.trend_scores = base.viralVideos.map((video) => ({
    url: video.url,
    trendScore: video.trendScore,
    caption: video.caption,
  }));

  if (viralVideos.length === 0) {
    return fail(
      base,
      "viral_selection_failed",
      "No video URLs could be extracted from search results",
      { apify: { searchRunId: searchOutcome.runId } },
    );
  }

  const commentOutcome = await scrapeTikTokComments(base.videoUrls);
  if (!commentOutcome.ok) {
    const step: PipelineStep = commentOutcome.message.includes("defaultDatasetId")
      ? "dataset_missing"
      : "comment_fetch_failed";

    return fail(base, step, commentOutcome.message, {
      apify: {
        searchRunId: searchOutcome.runId,
        commentRunId: commentOutcome.runId,
      },
    });
  }

  base.apify = {
    searchRunId: searchOutcome.runId,
    commentRunId: commentOutcome.runId,
  };
  base.comments = commentOutcome.items;

  try {
    base.insights = await generateInsights({
      comments: base.comments,
      niche: trimmedNiche,
      videoCaptions: base.viralVideos.map((video) => video.caption ?? "").filter(Boolean),
    });
  } catch {
    base.insights = { ...EMPTY_INSIGHTS };
  }

  const payload = {
    videos: base.viralVideos,
    comments: base.comments,
    insights: base.insights,
    trend_scores: base.trend_scores,
    meta: {
      searchResultCount: base.searchResultCount,
      viralVideoCount: base.viralVideoCount,
      scrapedAt: new Date().toISOString(),
      apify: base.apify,
    },
  };

  try {
    const stored = await storeTikTokResults(trimmedNiche, payload);
    return {
      ...base,
      success: true,
      stored: {
        id: stored.id,
        created_at: stored.created_at,
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Supabase insert failed";
    return fail(base, "supabase_failed", message, {
      apify: {
        searchRunId: searchOutcome.runId,
        commentRunId: commentOutcome.runId,
      },
    });
  }
}
