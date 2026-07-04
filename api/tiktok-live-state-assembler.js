/**
 * Live state assembler (Node) — mirrors tiktok_live_state_assembler.py contract.
 * Safe UI contract builder only; never throws.
 */

const DEFAULT_FEED_TABLE = "trend_intelligence_feed";
const DEFAULT_QUEUE_TABLE = "content_queue";
const DEFAULT_PERFORMANCE_TABLE = "content_performance";
const DEFAULT_CACHE_TABLE = "tiktok_insights_cache";

function emptyContract() {
  return {
    today_flow: {
      step: "trend → product → content → queue",
      next_action: "unknown",
      status: "unknown",
    },
    trends: [],
    products: [],
    inventory_gaps: [],
    inventory_prevention: [],
    content_queue: [],
    approvals: [],
    performance: {},
    alerts: [],
    primary_action: {
      label: "unknown",
      action: "unknown",
      context_id: "unknown",
    },
    system_health: "unknown",
  };
}

function getSupabaseConfig() {
  const url = (process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    "";
  return { url, key };
}

async function supabaseRequest(path, options) {
  const { url, key } = getSupabaseConfig();
  if (!url || !key) return null;
  try {
    const resp = await fetch(`${url}/rest/v1/${path}`, {
      ...options,
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        Prefer: options?.prefer || "return=representation",
        ...(options?.headers || {}),
      },
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function asDict(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function asString(value, fallback) {
  if (value == null) return fallback || "unknown";
  const text = String(value).trim();
  return text || fallback || "unknown";
}

function asNumber(value) {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

async function fetchTrends() {
  const rows = await supabaseRequest(
    `${DEFAULT_FEED_TABLE}?source=eq.tiktok&select=timestamp,type,signal_strength,virality_score,trend_state,summary,dedupe_key&order=timestamp.desc&limit=50`,
    { method: "GET" }
  );
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => ({
    id: asString(row.dedupe_key || row.summary),
    type: asString(row.type),
    signal_strength: row.signal_strength || 0,
    virality_score: row.virality_score || 0,
    trend_state: asString(row.trend_state),
    summary: asString(row.summary),
    timestamp: asString(row.timestamp),
  }));
}

async function fetchCachedProducts(accountId, key) {
  let path = `${DEFAULT_CACHE_TABLE}?select=payload&order=updated_at.desc&limit=1`;
  if (accountId) path += `&account_id=eq.${encodeURIComponent(accountId)}`;
  const rows = await supabaseRequest(path, { method: "GET" });
  if (!Array.isArray(rows) || !rows.length) return [];
  let payload = rows[0].payload || {};
  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload);
    } catch {
      payload = {};
    }
  }
  const products = asList(payload[key]);
  return products
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      name: asString(item.product || item.name),
      signal_strength: item.signal_strength || item.score || 0,
      source: key === "emerging_products" ? "emerging" : "trending",
      confidence: item.confidence || 0,
      evidence: asList(item.evidence),
    }));
}

function mergeProducts(emerging, trending) {
  const merged = [];
  const seen = new Set();
  for (const item of [...emerging, ...trending]) {
    const key = asString(item.name, "").toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged;
}

async function fetchContentQueue(accountId) {
  if (!accountId) return [];
  const rows = await supabaseRequest(
    `${DEFAULT_QUEUE_TABLE}?account_id=eq.${encodeURIComponent(accountId)}&select=id,account_id,caption,hashtags,hook,product_name,status,scheduled_time,created_at&order=created_at.desc&limit=50`,
    { method: "GET" }
  );
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => ({
    id: asString(row.id, ""),
    account_id: asString(row.account_id, ""),
    caption: asString(row.caption),
    hashtags: asList(row.hashtags),
    hook: asString(row.hook),
    product_name: asString(row.product_name),
    status: asString(row.status),
    scheduled_time: asString(row.scheduled_time),
    created_at: asString(row.created_at),
  }));
}

async function fetchApprovals(accountId) {
  if (!accountId) return [];
  const rows = await supabaseRequest(
    `${DEFAULT_QUEUE_TABLE}?account_id=eq.${encodeURIComponent(accountId)}&status=in.(pending,queued)&select=id,caption,product_name,status,created_at&order=created_at.desc&limit=25`,
    { method: "GET" }
  );
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => ({
    content_id: asString(row.id, ""),
    caption: asString(row.caption),
    product_name: asString(row.product_name),
    status: asString(row.status),
    created_at: asString(row.created_at),
  }));
}

async function fetchPerformance(accountId) {
  if (!accountId) return {};
  const rows = await supabaseRequest(
    `${DEFAULT_PERFORMANCE_TABLE}?account_id=eq.${encodeURIComponent(accountId)}&select=content_id,performance_metrics,timestamp&order=timestamp.desc&limit=25`,
    { method: "GET" }
  );
  if (!Array.isArray(rows)) return {};
  let totalViews = 0;
  let totalEngagement = 0;
  const snapshots = rows.map((row) => {
    const metrics = asDict(row.performance_metrics);
    totalViews += asNumber(metrics.views);
    totalEngagement += asNumber(metrics.engagement_rate);
    return {
      content_id: asString(row.content_id, ""),
      metrics,
      timestamp: asString(row.timestamp),
    };
  });
  const count = snapshots.length;
  return {
    snapshot_count: count,
    total_views: totalViews,
    avg_engagement_rate: count ? Math.round((totalEngagement / count) * 10000) / 10000 : 0,
    snapshots,
  };
}

async function computeSystemHealth() {
  const rows = await supabaseRequest(`${DEFAULT_QUEUE_TABLE}?select=id&limit=1`, { method: "GET" });
  if (!Array.isArray(rows)) return "failing";
  return "degraded";
}

function buildAlerts(inventoryGaps, systemHealth) {
  const alerts = [];
  for (const gap of inventoryGaps) {
    alerts.push({
      level: "warning",
      code: "inventory_gap",
      message: `Inventory gap: ${asString(gap.product_name)}`,
    });
  }
  if (systemHealth === "failing") {
    alerts.push({ level: "error", code: "system_health", message: "System health is failing" });
  } else if (systemHealth === "degraded") {
    alerts.push({ level: "warning", code: "system_health", message: "System health is degraded" });
  }
  return alerts;
}

function deriveFlowAndAction(trends, products, contentQueue, approvals, inventoryGaps, systemHealth) {
  const todayFlow = {
    step: "trend → product → content → queue",
    next_action: "unknown",
    status: "unknown",
  };
  const primaryAction = { label: "unknown", action: "unknown", context_id: "unknown" };

  if (inventoryGaps.length) {
    todayFlow.next_action = "Resolve inventory gaps before attaching products";
    todayFlow.status = "blocked";
    primaryAction.label = "Fix inventory gap";
    primaryAction.action = "resolve_inventory_gap";
    primaryAction.context_id = asString(inventoryGaps[0].product_name);
    return { todayFlow, primaryAction };
  }
  if (approvals.length) {
    todayFlow.next_action = "Review pending content approvals";
    todayFlow.status = "awaiting_approval";
    primaryAction.label = "Approve content";
    primaryAction.action = "approve_content";
    primaryAction.context_id = asString(approvals[0].content_id);
    return { todayFlow, primaryAction };
  }
  if (!contentQueue.length && products.length) {
    todayFlow.next_action = "Generate content from detected products";
    todayFlow.status = "ready_for_content";
    primaryAction.label = "Generate content";
    primaryAction.action = "generate_content";
    primaryAction.context_id = asString(products[0].name);
    return { todayFlow, primaryAction };
  }
  if (!products.length && trends.length) {
    todayFlow.next_action = "Match products to active trends";
    todayFlow.status = "trend_detected";
    primaryAction.label = "Match products";
    primaryAction.action = "match_products";
    primaryAction.context_id = asString(trends[0].id || trends[0].summary);
    return { todayFlow, primaryAction };
  }
  if (contentQueue.length) {
    todayFlow.next_action = "Monitor queued content pipeline";
    todayFlow.status = "in_queue";
    primaryAction.label = "View queue";
    primaryAction.action = "view_queue";
    primaryAction.context_id = asString(contentQueue[0].id);
    return { todayFlow, primaryAction };
  }
  todayFlow.status = systemHealth;
  todayFlow.next_action = "Run trend scan to refresh signals";
  primaryAction.label = "Refresh trends";
  primaryAction.action = "run_trend_scan";
  primaryAction.context_id = "unknown";
  return { todayFlow, primaryAction };
}

async function assembleLiveState(accountId) {
  const state = emptyContract();
  const account = asString(accountId, "").trim();

  try {
    const [trends, emerging, trending, contentQueue, approvals, performance, systemHealth] =
      await Promise.all([
        fetchTrends(),
        fetchCachedProducts(account, "emerging_products"),
        fetchCachedProducts(account, "trending_products"),
        fetchContentQueue(account),
        fetchApprovals(account),
        fetchPerformance(account),
        computeSystemHealth(),
      ]);

    const products = mergeProducts(emerging, trending);
    const inventoryGaps = [];
    const inventoryPrevention = [];
    const { todayFlow, primaryAction } = deriveFlowAndAction(
      trends,
      products,
      contentQueue,
      approvals,
      inventoryGaps,
      systemHealth
    );

    state.today_flow = todayFlow;
    state.trends = trends;
    state.products = products;
    state.inventory_gaps = inventoryGaps;
    state.inventory_prevention = inventoryPrevention;
    state.content_queue = contentQueue;
    state.approvals = approvals;
    state.performance = performance;
    state.alerts = buildAlerts(inventoryGaps, systemHealth);
    state.primary_action = primaryAction;
    state.system_health = systemHealth;
    return state;
  } catch {
    return state;
  }
}

module.exports = { emptyContract, assembleLiveState };
