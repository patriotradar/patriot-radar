/**
 * TikTok Live State client — single frontend data source for dashboard modules.
 * Fetches /api/tiktok-live-state and provides safe fallbacks for all fields.
 */
(function () {
  "use strict";

  var CACHE_TTL_MS = 60000;
  var cache = null;
  var cacheNiche = "";
  var cacheTs = 0;
  var inflight = null;

  function isDebugMode() {
    try {
      if (typeof window !== "undefined" && window.location) {
        if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
          return true;
        }
        if (window.location.search.indexOf("debug=1") !== -1) return true;
      }
    } catch (e) {}
    return false;
  }

  function debugLog(label, payload) {
    if (!isDebugMode()) return;
    if (payload === undefined) {
      console.log("[TikTokLiveState]", label);
    } else {
      console.log("[TikTokLiveState]", label, payload);
    }
  }

  function emptyState(niche) {
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
      insights: [],
      recommended_posts: [],
      trend_scores: [],
      trending_products: [],
      videos: [],
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

  function normalizeState(raw, niche) {
    var base = emptyState(niche);
    if (!raw || typeof raw !== "object") return base;

    var kw = raw.niche_keywords || {};
    var virality = raw.virality || {};

    return {
      updated_at: raw.updated_at || base.updated_at,
      niche: raw.niche || niche || base.niche,
      trend_intelligence_feed: Array.isArray(raw.trend_intelligence_feed)
        ? raw.trend_intelligence_feed
        : [],
      niche_comment_raw: Array.isArray(raw.niche_comment_raw) ? raw.niche_comment_raw : [],
      niche_keywords: {
        results: Array.isArray(kw.results) ? kw.results : [],
        emerging: Array.isArray(kw.emerging) ? kw.emerging : [],
        product_trends: Array.isArray(kw.product_trends) ? kw.product_trends : [],
        creator_insights: Array.isArray(kw.creator_insights) ? kw.creator_insights : [],
      },
      insights: Array.isArray(raw.insights) ? raw.insights : [],
      recommended_posts: Array.isArray(raw.recommended_posts) ? raw.recommended_posts : [],
      trend_scores: Array.isArray(raw.trend_scores) ? raw.trend_scores : [],
      trending_products: Array.isArray(raw.trending_products) ? raw.trending_products : [],
      videos: Array.isArray(raw.videos) ? raw.videos : [],
      virality: {
        calibration: Array.isArray(virality.calibration) ? virality.calibration : [],
        explanations: Array.isArray(virality.explanations) ? virality.explanations : [],
      },
      shop_catalog: Array.isArray(raw.shop_catalog) ? raw.shop_catalog : [],
      inventory_gaps: Array.isArray(raw.inventory_gaps) ? raw.inventory_gaps : [],
      trend_history:
        raw.trend_history && typeof raw.trend_history === "object" ? raw.trend_history : {},
      breaking_news: Array.isArray(raw.breaking_news) ? raw.breaking_news : [],
      errors: Array.isArray(raw.errors) ? raw.errors : [],
      success: raw.success !== false,
    };
  }

  function warnMissingFields(state) {
    if (!isDebugMode() || !state) return;
    var checks = [
      ["trend_intelligence_feed", state.trend_intelligence_feed],
      ["niche_comment_raw", state.niche_comment_raw],
      ["niche_keywords.results", state.niche_keywords && state.niche_keywords.results],
      ["insights", state.insights],
      ["virality.calibration", state.virality && state.virality.calibration],
      ["shop_catalog", state.shop_catalog],
    ];
    checks.forEach(function (pair) {
      if (!pair[1] || !pair[1].length) {
        console.warn("[TikTokLiveState] missing or empty field:", pair[0]);
      }
    });
    if (state.errors && state.errors.length) {
      console.warn("[TikTokLiveState] API errors:", state.errors);
    }
  }

  async function getAuthHeaders() {
    var headers = { Accept: "application/json" };
    try {
      if (typeof supabaseClient !== "undefined" && supabaseClient && supabaseClient.auth) {
        var session = await supabaseClient.auth.getSession();
        var token =
          session &&
          session.data &&
          session.data.session &&
          session.data.session.access_token;
        if (token) headers.Authorization = "Bearer " + token;
      }
    } catch (e) {
      debugLog("auth header skipped", e);
    }
    return headers;
  }

  async function fetchLiveState(niche, options) {
    var opts = options || {};
    var resolvedNiche = String(niche || (typeof USER_NICHE !== "undefined" ? USER_NICHE : "") || "general");
    var force = !!opts.force;

    if (
      !force &&
      cache &&
      cacheNiche === resolvedNiche &&
      Date.now() - cacheTs < CACHE_TTL_MS
    ) {
      debugLog("cache hit", { niche: resolvedNiche, age_ms: Date.now() - cacheTs });
      return cache;
    }

    if (inflight && !force) {
      return inflight;
    }

    inflight = (async function () {
      var url = "/api/tiktok-live-state?niche=" + encodeURIComponent(resolvedNiche);
      debugLog("fetch start", url);

      try {
        var headers = await getAuthHeaders();
        var resp = await fetch(url, { headers: headers, cache: "no-store" });
        var raw = null;
        try {
          raw = await resp.json();
        } catch (parseErr) {
          debugLog("json parse error", parseErr);
          raw = null;
        }

        var state = normalizeState(raw, resolvedNiche);
        if (!resp.ok) {
          state.errors = (state.errors || []).concat(["http_" + resp.status]);
          state.success = false;
        }

        cache = state;
        cacheNiche = resolvedNiche;
        cacheTs = Date.now();

        debugLog("fetch complete", {
          niche: state.niche,
          feed: state.trend_intelligence_feed.length,
          comments: state.niche_comment_raw.length,
          keywords: state.niche_keywords.results.length,
          insights: state.insights.length,
        });
        warnMissingFields(state);

        return state;
      } catch (err) {
        debugLog("fetch failed", err);
        var fallback = normalizeState(null, resolvedNiche);
        fallback.errors = [String(err && err.message ? err.message : err)];
        fallback.success = false;
        return fallback;
      } finally {
        inflight = null;
      }
    })();

    return inflight;
  }

  window.TikTokLiveState = {
    fetch: fetchLiveState,
    getCache: function () {
      return cache;
    },
    empty: emptyState,
    isDebug: isDebugMode,
  };
})();
