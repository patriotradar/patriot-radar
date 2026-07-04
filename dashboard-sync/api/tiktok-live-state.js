/**
 * Unified TikTok live state API — single source of truth for dashboard data.
 * GET /api/tiktok-live-state?niche=patriotic — dashboard module data (feed, keywords, comments)
 * GET /api/tiktok-live-state?account_id=... — RBAC orchestration contract via assembler
 * Optional header: Authorization: Bearer <supabase_jwt>
 */

const fs = require("fs");
const path = require("path");
const { runPipeline, emptyResponse } = require("./tiktok-insights");
const { assembleLiveState, emptyContract } = require("./tiktok-live-state-assembler");
const { resolveUserFromAuthHeader } = require("./tiktok-access-control");

const DATA_DIR = path.join(__dirname, "..", "..", "data");

function getSupabaseConfig() {
  return {
    url: (
      process.env.SUPABASE_URL ||
      process.env.NEXT_PUBLIC_SUPABASE_URL ||
      "https://kdwqnlgdanzigpdwyqbh.supabase.co"
    ).replace(/\/$/, ""),
    serviceKey: process.env.SUPABASE_SERVICE_ROLE_KEY || "",
    anonKey:
      process.env.SUPABASE_ANON_KEY ||
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
      "sb_publishable_7WtTtv9S4dl5jO-YE9QXRg_Ldy3gU_G",
  };
}

function emptyLiveState(niche) {
  const insights = emptyResponse();
  return {
    updated_at: new Date().toISOString(),
    niche: niche || "general",
    trend_intelligence_feed: [],
    niche_comment_raw: [],
    niche_keywords: {
      results: [],
      emerging: [],
      product_trends: [],
      creator_insights: [],
    },
    insights: insights.insights,
    recommended_posts: insights.recommended_posts,
    trend_scores: insights.trend_scores,
    trending_products: insights.trending_products,
    videos: insights.videos,
    virality: {
      calibration: [],
      explanations: [],
    },
    shop_catalog: [],
    inventory_gaps: [],
    trend_history: {},
    breaking_news: [],
    errors: [],
    success: true,
  };
}

function readJsonFile(filename, fallback) {
  try {
    const raw = fs.readFileSync(path.join(DATA_DIR, filename), "utf8");
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

async function supabaseQuery(table, queryParts, authToken) {
  const cfg = getSupabaseConfig();
  const bearer = authToken || cfg.serviceKey || cfg.anonKey;
  const query = (queryParts || []).join("&");
  const url = cfg.url + "/rest/v1/" + table + (query ? "?" + query : "");

  const resp = await fetch(url, {
    headers: {
      apikey: cfg.anonKey,
      Authorization: "Bearer " + bearer,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(table + " fetch failed (" + resp.status + "): " + text.slice(0, 200));
  }

  return resp.json();
}

function rawCommentsToVideos(rows) {
  const byVideo = {};
  for (const row of rows || []) {
    const vid = String(row.video_id || row.video_url || "unknown");
    if (!byVideo[vid]) {
      byVideo[vid] = {
        video_id: row.video_id || "",
        url: row.video_url || "",
        caption: row.video_caption || "",
        author: row.video_author || "",
        comments: [],
      };
    }
    byVideo[vid].comments.push({
      text: row.comment_text || "",
      author: row.comment_author || "",
      like_count: row.comment_like_count || 0,
      create_time: row.commented_at || null,
    });
  }
  return Object.values(byVideo);
}

function feedRowsToKeywords(feedRows, niche) {
  const results = [];
  const seen = {};

  for (const row of feedRows || []) {
    const raw = row.raw_data || {};
    const signal = raw.signal || {};
    let keyword = "";

    if (row.type === "keyword_cluster" && raw.cluster_name) {
      keyword = raw.cluster_name;
    } else if (row.type === "topic" && raw.topic) {
      keyword = raw.topic;
    } else if (signal.hook_text) {
      keyword = String(signal.hook_text).slice(0, 80);
    } else if (row.summary) {
      keyword = String(row.summary).slice(0, 80);
    }

    keyword = keyword.trim();
    if (!keyword) continue;
    const key = keyword.toLowerCase();
    if (seen[key]) continue;
    seen[key] = true;

    const strength = Number(row.signal_strength) || 0;
    const virality = Number(row.virality_score) || strength;
    results.push({
      keyword: keyword.charAt(0).toUpperCase() + keyword.slice(1),
      viral_score: Math.min(95, Math.max(0, virality || strength)),
      rise_percent: Math.min(99, Math.max(0, strength - 20)),
      search_volume: Math.min(99, Math.max(10, strength + 5)),
      source: "TikTok Live State",
      content_score: Math.min(95, Math.max(0, strength)),
      fresh: Math.min(95, Math.max(20, strength)),
      emotion: Math.min(95, Math.max(20, Math.round(strength * 0.7))),
      debate: Math.min(95, Math.max(15, Math.round(strength * 0.5))),
      product: raw.product_name || raw.product || "",
      trend_state: row.trend_state || "emerging",
      niche: niche || "general",
    });
  }

  results.sort(function (a, b) {
    return (b.viral_score || 0) - (a.viral_score || 0);
  });

  const emerging = results.slice(5, 10).map(function (r) {
    return {
      keyword: r.keyword,
      source: "TikTok Live State",
      description: "Emerging signal in " + (niche || "your niche"),
    };
  });

  const productTrends = results
    .filter(function (r) {
      return r.product;
    })
    .slice(0, 8)
    .map(function (r) {
      return {
        keyword: r.keyword,
        product: r.product,
        viral_score: r.viral_score,
        rise_percent: r.rise_percent,
        category: "product",
      };
    });

  return {
    results: results.slice(0, 20),
    emerging: emerging,
    product_trends: productTrends,
    creator_insights: [],
  };
}

function loadFallbackFeed() {
  return readJsonFile("tiktok_scan_feed_rows.json", []);
}

function loadFallbackComments() {
  const sample = readJsonFile("tiktok_comment_sample.json", []);
  const rows = [];
  let idx = 0;
  for (const video of sample) {
    const videoId = String(video.url || "").split("/").pop() || "vid_" + idx;
    for (const comment of video.comments || []) {
      rows.push({
        video_id: videoId,
        video_url: video.url || "",
        video_caption: video.caption || "",
        video_author: video.author || "",
        comment_text: comment.text || "",
        comment_author: comment.author || "",
        comment_like_count: comment.like_count || 0,
        commented_at: comment.create_time
          ? new Date(comment.create_time * 1000).toISOString()
          : null,
        ingested_at: new Date().toISOString(),
      });
      idx++;
    }
  }
  return rows;
}

function loadFallbackKeywords(niche) {
  const trends = readJsonFile("tiktok_shop_sample_trends.json", {
    results: [],
    emerging: [],
    product_trends: [],
  });
  return {
    results: trends.results || [],
    emerging: trends.emerging || [],
    product_trends: trends.product_trends || [],
    creator_insights: trends.creator_insights || [],
    niche: niche || "general",
  };
}

function loadFallbackCatalog() {
  return readJsonFile("tiktok_shop_sample_catalog.json", []);
}

function loadFallbackInventoryGaps() {
  const state = readJsonFile("tiktok_shop_inventory_state.json", { accounts: {} });
  const gaps = [];
  const accounts = state.accounts || {};
  Object.keys(accounts).forEach(function (accountId) {
    const paused = (accounts[accountId] && accounts[accountId].paused_attachments) || [];
    paused.forEach(function (p) {
      gaps.push({
        account_id: accountId,
        content_id: p.content_id || "",
        product_name: p.product_name || "No data",
        category: (p.inventory_gap_event && p.inventory_gap_event.category) || "general",
        message: (p.inventory_gap_event && p.inventory_gap_event.message) || "No data",
        status: p.status || "waiting_user_action",
      });
    });
  });
  return gaps;
}

async function buildLiveState(niche, authToken) {
  const state = emptyLiveState(niche);
  const errors = [];

  let feed = [];
  let comments = [];
  let calibration = [];
  let explanations = [];

  try {
    feed = await supabaseQuery(
      "trend_intelligence_feed",
      ["select=*", "source=eq.tiktok", "order=timestamp.desc", "limit=200"],
      authToken
    );
  } catch (err) {
    errors.push(String(err.message || err));
    feed = loadFallbackFeed();
  }

  try {
    comments = await supabaseQuery(
      "niche_comment_raw",
      ["select=*", "order=ingested_at.desc", "limit=3000"],
      authToken
    );
  } catch (err) {
    errors.push(String(err.message || err));
    comments = loadFallbackComments();
  }

  try {
    calibration = await supabaseQuery(
      "virality_calibration_logs",
      ["select=*", "order=calibrated_at.desc", "limit=30"],
      authToken
    );
  } catch (err) {
    errors.push(String(err.message || err));
    calibration = [];
  }

  try {
    explanations = await supabaseQuery(
      "virality_explanations",
      ["select=*", "order=created_at.desc", "limit=20"],
      authToken
    );
  } catch (err) {
    errors.push(String(err.message || err));
    explanations = [];
  }

  state.trend_intelligence_feed = Array.isArray(feed) ? feed : [];
  state.niche_comment_raw = Array.isArray(comments) ? comments : [];
  state.virality.calibration = Array.isArray(calibration) ? calibration : [];
  state.virality.explanations = Array.isArray(explanations) ? explanations : [];

  let keywords = feedRowsToKeywords(state.trend_intelligence_feed, niche);
  if (!keywords.results.length) {
    const fallbackKw = loadFallbackKeywords(niche);
    keywords = {
      results: fallbackKw.results || [],
      emerging: fallbackKw.emerging || [],
      product_trends: fallbackKw.product_trends || [],
      creator_insights: fallbackKw.creator_insights || [],
    };
  }
  state.niche_keywords = keywords;

  state.shop_catalog = loadFallbackCatalog();
  state.inventory_gaps = loadFallbackInventoryGaps();

  try {
    const videos = rawCommentsToVideos(state.niche_comment_raw);
    if (videos.length) {
      const pipeline = runPipeline(videos, niche);
      state.insights = pipeline.insights || [];
      state.recommended_posts = pipeline.recommended_posts || [];
      state.trend_scores = pipeline.trend_scores || [];
      state.trending_products = pipeline.trending_products || [];
      state.videos = pipeline.videos || [];
      if (pipeline.errors && pipeline.errors.length) {
        errors.push.apply(errors, pipeline.errors);
      }
    }
  } catch (err) {
    errors.push("insights_pipeline: " + String(err.message || err));
  }

  state.errors = errors;
  state.success = true;
  state.updated_at = new Date().toISOString();
  return state;
}

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    return res.status(204).end();
  }

  if (req.method !== "GET") {
    return res.status(405).json({ ...emptyLiveState(), errors: ["method_not_allowed"], success: false });
  }

  const hasAccountId =
    (req.query && req.query.account_id != null && String(req.query.account_id).trim() !== "") ||
    (req.body && req.body.account_id != null && String(req.body.account_id).trim() !== "");
  const hasNiche = req.query && req.query.niche != null && String(req.query.niche).trim() !== "";

  if (hasAccountId || !hasNiche) {
    const accountId =
      (req.query && req.query.account_id) || (req.body && req.body.account_id) || "";

    try {
      const userRecord = await resolveUserFromAuthHeader(req);
      const resolvedAccountId = String(accountId || (userRecord && userRecord.id) || "");
      const state = await assembleLiveState(resolvedAccountId, userRecord);
      return res.status(200).json(state);
    } catch {
      return res.status(200).json(emptyContract());
    }
  }

  const niche = String(req.query.niche).trim() || "general";
  const authHeader = req.headers.authorization || "";
  const authToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";

  try {
    const state = await buildLiveState(niche, authToken || null);
    state.niche = niche;
    return res.status(200).json(state);
  } catch (err) {
    const fallback = emptyLiveState(niche);
    fallback.errors = [String(err?.message || err)];
    fallback.success = false;
    return res.status(200).json(fallback);
  }
};
