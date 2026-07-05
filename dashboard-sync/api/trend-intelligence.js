/**
 * Trend Intelligence API — live server-side aggregation for CreatorRadar.
 * GET /api/trend-intelligence?niche=patriotic
 *
 * Aggregates Google Trends snapshot, Google Suggest, Reddit RSS, News RSS,
 * and TikTok signals (Supabase trend_intelligence_feed via live-state builder).
 * Compatible with hourly cron refresh (Cache-Control + optional CRON_SECRET).
 */

const { buildLiveState } = require("./tiktok-live-state");
const {
  fetchGoogleTrendsSnapshot,
  fetchGoogleSuggestTrends,
  fetchRedditTrends,
  fetchBreakingNews,
  fetchNewsTrendKeywords,
  fetchApifyTikTokPreview,
  mergeProviderKeywords,
} = require("./trend-intelligence-providers");

const HOURLY_CACHE_SECONDS = 3600;

function emptyResponse(niche) {
  return {
    updated_at: new Date().toISOString(),
    niche: niche || "general",
    results: [],
    emerging: [],
    product_trends: [],
    creator_insights: [],
    breaking_news: [],
    trend_intelligence_feed: [],
    niche_keywords: {
      results: [],
      emerging: [],
      product_trends: [],
      creator_insights: [],
    },
    insights: [],
    recommended_posts: [],
    trend_scores: [],
    trending_products: [],
    videos: [],
    virality: { calibration: [], explanations: [] },
    shop_catalog: [],
    inventory_gaps: [],
    trend_history: {},
    sources: {
      google_trends: { ok: false },
      google_suggest: { ok: false },
      reddit: { ok: false },
      news: { ok: false },
      tiktok: { ok: false },
      apify: { ok: false, skipped: true },
    },
    errors: [],
    success: true,
  };
}

function isCronAuthorized(req) {
  const secret = process.env.CRON_SECRET || process.env.TREND_INTELLIGENCE_CRON_SECRET || "";
  if (!secret) return false;
  const auth = req.headers.authorization || "";
  if (auth === "Bearer " + secret) return true;
  const cronHeader = req.headers["x-cron-secret"] || req.headers["x-vercel-cron-secret"] || "";
  return cronHeader === secret;
}

async function buildTrendIntelligence(niche, authToken, options) {
  const opts = options || {};
  const errors = [];
  const sources = {
    google_trends: { ok: false },
    google_suggest: { ok: false },
    reddit: { ok: false },
    news: { ok: false },
    tiktok: { ok: false },
    apify: { ok: false, skipped: true },
  };

  const liveStatePromise = buildLiveState(niche, authToken || null);

  const providerPromises = [
    fetchGoogleTrendsSnapshot().then(function (r) {
      sources.google_trends = {
        ok: !!r.ok,
        last_updated: r.last_updated || null,
        result_count: (r.results || []).length,
        emerging_count: (r.emerging || []).length,
        error: r.error || null,
      };
      if (r.error) errors.push("google_trends: " + r.error);
      return { source: "Google Trends", results: r.results || [], emerging: r.emerging || [] };
    }),
    fetchGoogleSuggestTrends(niche, "GB").then(function (r) {
      sources.google_suggest = {
        ok: !!r.ok,
        result_count: (r.results || []).length,
        error: r.error || null,
      };
      if (r.error && r.error !== "no_suggestions") errors.push("google_suggest: " + r.error);
      return { source: "Google Suggest", results: r.results || [] };
    }),
    fetchRedditTrends().then(function (r) {
      sources.reddit = {
        ok: !!r.ok,
        result_count: (r.results || []).length,
        error: r.error || null,
      };
      if (r.error) errors.push("reddit: " + r.error);
      return { source: "Reddit", results: r.results || [] };
    }),
    fetchNewsTrendKeywords(niche).then(function (r) {
      sources.news = {
        ok: !!r.ok,
        result_count: (r.results || []).length,
        error: r.error || null,
      };
      if (r.error && r.error !== "no_news") errors.push("news_keywords: " + r.error);
      return { source: "News RSS", results: r.results || [] };
    }),
    fetchBreakingNews(niche).then(function (r) {
      sources.news_feed = {
        ok: !!r.ok,
        item_count: (r.items || []).length,
        error: r.error || null,
      };
      return r.items || [];
    }),
  ];

  let apifyPreview = null;
  if (opts.refreshApify) {
    apifyPreview = await fetchApifyTikTokPreview();
    sources.apify = {
      ok: !!apifyPreview.ok,
      skipped: !!apifyPreview.skipped,
      video_count: (apifyPreview.videos || []).length,
      error: apifyPreview.error || null,
    };
    if (apifyPreview.error && !apifyPreview.skipped) {
      errors.push("apify: " + apifyPreview.error);
    }
  }

  const liveState = await liveStatePromise;
  const providerResults = await Promise.all(providerPromises);
  const breakingNews = providerResults.pop() || [];

  const tiktokKeywords = (liveState && liveState.niche_keywords) || {
    results: [],
    emerging: [],
    product_trends: [],
  };

  sources.tiktok = {
    ok: !!(liveState && liveState.trend_intelligence_feed && liveState.trend_intelligence_feed.length),
    feed_row_count: (liveState && liveState.trend_intelligence_feed && liveState.trend_intelligence_feed.length) || 0,
    keyword_count: (tiktokKeywords.results || []).length,
  };

  const providerBatches = providerResults.concat([
    { source: "TikTok", results: tiktokKeywords.results || [] },
  ]);

  const mergedKeywords = mergeProviderKeywords(providerBatches, niche);

  if (!mergedKeywords.results.length && tiktokKeywords.results && tiktokKeywords.results.length) {
    mergedKeywords.results = tiktokKeywords.results;
    mergedKeywords.emerging = tiktokKeywords.emerging || [];
    mergedKeywords.product_trends = tiktokKeywords.product_trends || [];
  }

  if (!mergedKeywords.emerging.length) {
    const trendsEmerging = providerResults[0] && providerResults[0].emerging;
    if (Array.isArray(trendsEmerging) && trendsEmerging.length) {
      mergedKeywords.emerging = trendsEmerging.slice(0, 10);
    }
  }

  if (!mergedKeywords.product_trends.length && tiktokKeywords.product_trends) {
    mergedKeywords.product_trends = tiktokKeywords.product_trends;
  }

  const response = {
    ...emptyResponse(niche),
    ...(liveState || {}),
    niche: niche,
    updated_at: new Date().toISOString(),
    results: mergedKeywords.results,
    emerging: mergedKeywords.emerging,
    product_trends: mergedKeywords.product_trends,
    creator_insights: mergedKeywords.creator_insights,
    niche_keywords: mergedKeywords,
    breaking_news: breakingNews,
    sources: sources,
    errors: (liveState && liveState.errors ? liveState.errors.slice() : []).concat(errors),
    success: true,
  };

  if (apifyPreview && apifyPreview.videos && apifyPreview.videos.length) {
    response.apify_preview = {
      video_count: apifyPreview.videos.length,
      fetched_at: new Date().toISOString(),
    };
  }

  return response;
}

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Cron-Secret");

  const cronMode = isCronAuthorized(req);
  const cacheSeconds = cronMode ? 0 : HOURLY_CACHE_SECONDS;
  res.setHeader(
    "Cache-Control",
    cacheSeconds > 0 ? "public, s-maxage=" + cacheSeconds + ", stale-while-revalidate=600" : "no-store"
  );
  res.setHeader("X-Trend-Intelligence-Cache-TTL", String(cacheSeconds));

  if (req.method === "OPTIONS") {
    return res.status(204).end();
  }

  if (req.method !== "GET") {
    return res.status(405).json({ ...emptyResponse(), errors: ["method_not_allowed"], success: false });
  }

  const niche = String((req.query && req.query.niche) || "general").trim() || "general";
  const authHeader = req.headers.authorization || "";
  const authToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
  const refreshApify =
    cronMode ||
    (req.query && (req.query.refresh_apify === "1" || req.query.refresh === "1"));

  try {
    const state = await buildTrendIntelligence(niche, authToken || null, { refreshApify: refreshApify });
    return res.status(200).json(state);
  } catch (err) {
    const fallback = emptyResponse(niche);
    fallback.errors = [String(err && err.message ? err.message : err)];
    fallback.success = false;
    return res.status(200).json(fallback);
  }
};

module.exports.buildTrendIntelligence = buildTrendIntelligence;
module.exports.emptyResponse = emptyResponse;
