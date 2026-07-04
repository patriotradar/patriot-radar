import {
  scrapeTikTokComments,
  searchTikTokByNiche,
  selectTopViralVideos,
} from "./apify";
import { storeTikTokResults } from "./supabase";

export type ScanPipelineResult = {
  success: boolean;
  niche: string;
  searchResultCount: number;
  viralVideoCount: number;
  videoUrls: string[];
  viralVideos: {
    url: string;
    views: number;
    caption?: string;
    author?: string;
  }[];
  comments: Record<string, unknown>[];
  stored: {
    id: string;
    created_at: string;
  } | null;
  error?: string;
};

function extractCaption(item: Record<string, unknown>): string {
  const text = item.text ?? item.desc ?? item.description ?? item.title ?? "";
  return typeof text === "string" ? text.trim() : "";
}

function extractAuthor(item: Record<string, unknown>): string {
  const authorMeta = item.authorMeta as Record<string, unknown> | undefined;
  const author = item.author ?? authorMeta?.name ?? authorMeta?.nickName ?? "";
  return typeof author === "string" ? author.trim() : "";
}

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
    stored: null,
  };

  if (!trimmedNiche) {
    return { ...base, error: "Niche is required" };
  }

  const searchResults = await searchTikTokByNiche(trimmedNiche);
  base.searchResultCount = searchResults.length;

  if (searchResults.length === 0) {
    return {
      ...base,
      error: "Apify search returned no videos for this niche",
    };
  }

  const viralVideos = selectTopViralVideos(searchResults, 10, 20);
  base.viralVideoCount = viralVideos.length;
  base.videoUrls = viralVideos.map((v) => v.url);
  base.viralVideos = viralVideos.map((v) => ({
    url: v.url,
    views: v.views,
    caption: extractCaption(v.item),
    author: extractAuthor(v.item),
  }));

  if (viralVideos.length === 0) {
    return {
      ...base,
      error: "No video URLs could be extracted from search results",
    };
  }

  const comments = await scrapeTikTokComments(base.videoUrls);
  base.comments = comments;

  const payload = {
    viralVideos: base.viralVideos,
    comments,
    meta: {
      searchResultCount: base.searchResultCount,
      viralVideoCount: base.viralVideoCount,
      scrapedAt: new Date().toISOString(),
    },
  };

  const stored = await storeTikTokResults(trimmedNiche, payload);

  return {
    ...base,
    success: true,
    stored: {
      id: stored.id,
      created_at: stored.created_at,
    },
  };
}
