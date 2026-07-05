/**
 * Multi-source Trend Intelligence API
 * GET /api/trend-intelligence?niche=general — status + cached results
 * GET /api/trend-intelligence?action=scan&niche=general — trigger scan (reads cache; full scan via CI)
 */

const fs = require("fs");
const path = require("path");

const CACHE_PATH = path.join(__dirname, "..", "data", "trend_intelligence_cache.json");
const DATA_DIR = path.join(__dirname, "..", "data");

function getSupabaseConfig() {
  return {
    url: (process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, ""),
    key:
      process.env.SUPABASE_SERVICE_ROLE_KEY ||
      process.env.SUPABASE_ANON_KEY ||
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
      "",
  };
}

async function supabaseRequest(tablePath) {
  const { url, key } = getSupabaseConfig();
  if (!url || !key) return null;
  try {
    const resp = await fetch(`${url}/rest/v1/${tablePath}`, {
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

function readCache() {
  try {
    if (fs.existsSync(CACHE_PATH)) {
      return JSON.parse(fs.readFileSync(CACHE_PATH, "utf8"));
    }
  } catch {
    /* ignore */
  }
  return null;
}

function emptyResponse(niche) {
  return {
    success: true,
    niche: niche || "general",
    timestamp: new Date().toISOString(),
    system_status: "awaiting_scan",
    health_status: "unknown",
    providers_online: [],
    providers_offline: [],
    warnings: ["No trend intelligence scan has run yet"],
    last_scan_time: null,
    trends: [],
    opportunities: [],
    emerging_keywords: [],
    buying_intent_opportunities: [],
    recommendations: {},
    content_queue: [],
    recent_discoveries: [],
  };
}

function providerAvailability() {
  const online = [];
  const offline = [];
  const checks = [
    { name: "tiktok_apify", label: "TikTok (Apify)", ok: !!(process.env.APIFY_API_TOKEN || process.env.APIFY_TOKEN) },
    { name: "google_trends", label: "Google Trends", ok: true },
    { name: "reddit", label: "Reddit", ok: true },
    { name: "youtube", label: "YouTube Search", ok: true },
    { name: "news", label: "News Sources", ok: true },
    { name: "blogs", label: "Blogs & Niche Sites", ok: true },
    { name: "forums", label: "Public Forums", ok: true },
    { name: "social", label: "Social Platforms", ok: true },
    {
      name: "historical",
      label: "CreatorRadar History",
      ok: !!(process.env.SUPABASE_URL && (process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY)),
    },
  ];
  for (const c of checks) {
    if (c.ok) online.push(c.name);
    else offline.push(c.name);
  }
  return { online, offline, checks };
}

function mapHistoryRow(row) {
  const raw = row.raw_data || {};
  const ci = row.content_intelligence || raw.content_intelligence || {};
  const opp = row.opportunity_scores || raw.opportunity || {};
  return {
    trend: row.trend || row.keyword || row.summary || "",
    keyword: row.keyword || row.trend || "",
    source: row.source || "unknown",
    timestamp: row.created_at || row.scanned_at,
    popularity: row.popularity || row.signal_strength || 0,
    buying_intent: row.buying_intent || 0,
    competition: row.competition || 50,
    opportunity_score: row.opportunity_score || opp.opportunity_score || 0,
    category: row.category || "general",
    content_intelligence: ci,
    hook: ci.hook || row.summary || "",
  };
}

async function buildTrendIntelligenceState(niche) {
  const nicheVal = (niche || "general").trim() || "general";
  const state = emptyResponse(nicheVal);
  const warnings = [];
  const availability = providerAvailability();

  state.providers_online = availability.online;
  state.providers_offline = availability.offline;
  state.provider_details = availability.checks;

  const latestScan = await supabaseRequest(
    `trend_intelligence_scans?select=*&order=scanned_at.desc&limit=1`
  );
  if (Array.isArray(latestScan) && latestScan.length) {
    const scan = latestScan[0];
    state.last_scan_time = scan.scanned_at;
    state.providers_online = scan.providers_online || state.providers_online;
    state.providers_offline = scan.providers_offline || state.providers_offline;
    state.health_status = scan.health_status || "healthy";
    state.system_status = scan.health_status === "healthy" ? "operational" : "degraded";
    if (Array.isArray(scan.warnings)) warnings.push(...scan.warnings);
  }

  let history = await supabaseRequest(
    `trend_intelligence_history?select=*&order=created_at.desc&limit=50`
  );
  if (!Array.isArray(history) || !history.length) {
    history = await supabaseRequest(
      `trend_intelligence_feed?select=*&order=created_at.desc&limit=50`
    );
  }

  const cache = readCache();
  if ((!Array.isArray(history) || !history.length) && cache) {
    state.trends = cache.trends || [];
    state.opportunities = cache.opportunities || [];
    state.recommendations = cache.recommendations || {};
    state.last_scan_time = state.last_scan_time || cache.timestamp;
    state.from_cache = true;
    if (Array.isArray(cache.warnings)) warnings.push(...cache.warnings);
  } else if (Array.isArray(history)) {
    const mapped = history.map(mapHistoryRow);
    state.trends = mapped.slice(0, 30);
    state.opportunities = mapped
      .filter((r) => (r.opportunity_score || 0) >= 35 || (r.buying_intent || 0) >= 40)
      .slice(0, 20);
    state.recent_discoveries = mapped.slice(0, 10);
  }

  const recs = await supabaseRequest(
    `trend_recommendations?select=recommendations,created_at&order=created_at.desc&limit=1`
  );
  if (Array.isArray(recs) && recs.length && recs[0].recommendations) {
    state.recommendations = recs[0].recommendations;
  } else if (cache && cache.recommendations) {
    state.recommendations = cache.recommendations;
  }

  state.emerging_keywords = (state.trends || [])
    .filter((t) => (t.popularity || 0) >= 40)
    .slice(0, 15)
    .map((t) => ({
      keyword: t.keyword,
      source: t.source,
      popularity: t.popularity,
    }));

  state.buying_intent_opportunities = (state.opportunities || [])
    .sort((a, b) => (b.opportunity_score || 0) - (a.opportunity_score || 0))
    .slice(0, 12);

  const queue = await supabaseRequest(
    `content_queue?select=id,caption,hook,status,created_at&order=created_at.desc&limit=10`
  );
  state.content_queue = Array.isArray(queue) ? queue : [];

  for (const name of state.providers_offline) {
    warnings.push(`Provider offline: ${name} — using remaining sources`);
  }
  state.warnings = [...new Set(warnings)];

  if (!state.last_scan_time) {
    state.system_status = state.providers_online.length ? "ready" : "degraded";
    state.health_status = state.providers_online.length ? "degraded" : "offline";
  }

  state.success = true;
  state.timestamp = new Date().toISOString();
  state.niche = nicheVal;
  return state;
}

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Access-Control-Allow-Origin", process.env.ALLOWED_ORIGIN || "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "GET") {
    return res.status(405).json({ success: false, error: "method_not_allowed" });
  }

  const niche = (req.query && req.query.niche) || "general";

  try {
    const state = await buildTrendIntelligenceState(niche);
    return res.status(200).json(state);
  } catch (err) {
    const fallback = emptyResponse(niche);
    fallback.warnings.push(String(err?.message || err));
    fallback.health_status = "degraded";
    return res.status(200).json(fallback);
  }
};

module.exports.buildTrendIntelligenceState = buildTrendIntelligenceState;
