/**
 * Live state assembler (Node) — mirrors tiktok_live_state_assembler.py contract.
 * Safe UI contract builder only; never throws.
 */

const {
  buildAccessContext,
  emptyLiveStateContract,
  filterLiveStateForAccess,
  loadFeatureFlags,
} = require("./tiktok-access-control");

const DEFAULT_FEED_TABLE = "trend_intelligence_feed";
const DEFAULT_QUEUE_TABLE = "content_queue";
const DEFAULT_PERFORMANCE_TABLE = "content_performance";
const DEFAULT_CACHE_TABLE = "tiktok_insights_cache";
const DEFAULT_INVENTORY_GAPS_TABLE = "tiktok_shop_inventory_gaps";
const DEFAULT_VIRALITY_SNAPSHOTS_TABLE = "virality_snapshots";
const DEFAULT_VIRALITY_CALIBRATION_TABLE = "virality_calibration_logs";

function emptyContract() {
  return emptyLiveStateContract();
}

function getSupabaseConfig() {
  const url = (process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(
    /\/$/,
    ""
  );
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

async function fetchInventoryGaps(accountId) {
  if (!accountId) return [];
  const rows = await supabaseRequest(
    `${DEFAULT_INVENTORY_GAPS_TABLE}?account_id=eq.${encodeURIComponent(accountId)}&select=content_id,product_name,category,status,inventory_gap_event,created_at&order=created_at.desc&limit=25`,
    { method: "GET" }
  );
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => ({
    content_id: asString(row.content_id, ""),
    product_name: asString(row.product_name),
    category: asString(row.category, "general"),
    status: asString(row.status),
    message: asString(
      (row.inventory_gap_event && row.inventory_gap_event.message) || "",
      "Inventory gap detected"
    ),
    created_at: asString(row.created_at),
  }));
}

async function fetchInventoryPrevention(accountId) {
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
  const prevention = asList(payload.inventory_prevention || payload.inventory_prevention_events);
  return prevention
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      product_name: asString(item.product_name || item.name),
      category: asString(item.category, "general"),
      available: item.available !== false,
      demand_score: asNumber(item.demand_score),
      message: asString(item.message, "Inventory prevention alert"),
      priority: asString(item.priority, "medium"),
    }));
}

async function fetchPrediction(accountId) {
  const snapshots = await supabaseRequest(
    `${DEFAULT_VIRALITY_SNAPSHOTS_TABLE}?select=video_id,virality_score,comment_velocity,acceleration,niche,snapshot_at&order=snapshot_at.desc&limit=10`,
    { method: "GET" }
  );
  const calibrationRows = await supabaseRequest(
    `${DEFAULT_VIRALITY_CALIBRATION_TABLE}?select=calibrated_at,accuracy_after,new_weights,outcomes_processed&order=calibrated_at.desc&limit=1`,
    { method: "GET" }
  );

  const snapshotList = Array.isArray(snapshots)
    ? snapshots.map((row) => ({
        video_id: asString(row.video_id, ""),
        virality_score: asNumber(row.virality_score),
        comment_velocity: asNumber(row.comment_velocity),
        acceleration: asNumber(row.acceleration),
        niche: asString(row.niche),
        snapshot_at: asString(row.snapshot_at),
      }))
    : [];

  const calibration =
    Array.isArray(calibrationRows) && calibrationRows.length
      ? {
          calibrated_at: asString(calibrationRows[0].calibrated_at),
          accuracy_after: calibrationRows[0].accuracy_after != null ? asNumber(calibrationRows[0].accuracy_after) : null,
          outcomes_processed: asNumber(calibrationRows[0].outcomes_processed),
          weights: asDict(calibrationRows[0].new_weights),
        }
      : {};

  if (!snapshotList.length && !Object.keys(calibration).length) return {};

  return {
    snapshot_count: snapshotList.length,
    top_predictions: snapshotList.slice(0, 5),
    calibration,
    account_id: asString(accountId, ""),
  };
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

function buildAlerts(inventoryGaps, systemHealth, partialFailures) {
  const alerts = [];
  const hiddenAlerts = [];

  for (const gap of inventoryGaps) {
    alerts.push({
      level: "warning",
      code: "inventory_gap",
      message: `Inventory gap: ${asString(gap.product_name)}`,
    });
  }

  if (systemHealth === "failing") {
    hiddenAlerts.push({ level: "hidden", code: "system_health", message: "System health is failing" });
    alerts.push({ level: "error", code: "system_health", message: "System health is failing" });
  } else if (systemHealth === "degraded") {
    hiddenAlerts.push({
      level: "hidden",
      code: "system_health_degraded",
      message: "System health is degraded",
    });
    alerts.push({ level: "warning", code: "system_health", message: "System health is degraded" });
  }

  for (const mod of partialFailures) {
    hiddenAlerts.push({
      level: "hidden",
      code: "module_partial_failure",
      message: `Module unavailable: ${mod}`,
    });
  }

  return { alerts, hiddenAlerts };
}

function deriveFlowAndAction(trends, products, contentQueue, approvals, inventoryGaps, systemHealth) {
  const todayFlow = {
    step: "trend → product → content → queue",
    next_action: "unknown",
    status: "unknown",
  };
  const primaryAction = { label: "unknown", action: "unknown", context_id: "unknown" };

  if (approvals.length) {
    todayFlow.next_action = "Review pending content approvals";
    todayFlow.status = "approval_pending";
    primaryAction.label = "Review approval";
    primaryAction.action = "review_approval";
    primaryAction.context_id = asString(approvals[0].content_id, "unknown");
    return { todayFlow, primaryAction };
  }

  if (inventoryGaps.length) {
    todayFlow.next_action = "Address inventory gaps before posting";
    todayFlow.status = "inventory_gap";
    primaryAction.label = "Fix inventory gap";
    primaryAction.action = "fix_inventory";
    primaryAction.context_id = asString(inventoryGaps[0].product_name, "unknown");
    return { todayFlow, primaryAction };
  }

  if (products.length && trends.length) {
    todayFlow.next_action = "Create content for top product-trend match";
    todayFlow.status = "ready_to_create";
    primaryAction.label = "Create content";
    primaryAction.action = "create_content";
    primaryAction.context_id = asString(products[0].name, "unknown");
    return { todayFlow, primaryAction };
  }

  if (!products.length && trends.length) {
    todayFlow.next_action = "Match products to active trends";
    todayFlow.status = "trend_detected";
    primaryAction.label = "Match products";
    primaryAction.action = "match_products";
    primaryAction.context_id = asString(trends[0].id || trends[0].summary, "unknown");
    return { todayFlow, primaryAction };
  }

  if (contentQueue.length) {
    todayFlow.next_action = "Monitor queued content pipeline";
    todayFlow.status = "in_queue";
    primaryAction.label = "View queue";
    primaryAction.action = "view_queue";
    primaryAction.context_id = asString(contentQueue[0].id, "unknown");
    return { todayFlow, primaryAction };
  }

  if (["healthy", "degraded", "failing"].includes(systemHealth)) {
    todayFlow.status = systemHealth;
    todayFlow.next_action = "Run trend scan to refresh signals";
    primaryAction.label = "Refresh trends";
    primaryAction.action = "run_trend_scan";
    primaryAction.context_id = "unknown";
  }

  return { todayFlow, primaryAction };
}

async function assembleLiveState(accountId, userRecord) {
  const state = emptyContract();
  const partialFailures = [];
  const resolvedAccountId = String(accountId || "");

  let trends = [];
  try {
    trends = await fetchTrends();
  } catch {
    partialFailures.push("trend_detection_engine");
  }

  let emerging = [];
  let trending = [];
  try {
    emerging = await fetchCachedProducts(resolvedAccountId, "emerging_products");
    trending = await fetchCachedProducts(resolvedAccountId, "trending_products");
  } catch {
    partialFailures.push("products_engine");
  }
  const products = mergeProducts(emerging, trending);

  let contentQueue = [];
  let approvals = [];
  let performance = {};
  let inventoryGaps = [];
  let inventoryPrevention = [];
  let prediction = {};
  try {
    contentQueue = await fetchContentQueue(resolvedAccountId);
    approvals = await fetchApprovals(resolvedAccountId);
    performance = await fetchPerformance(resolvedAccountId);
  } catch {
    partialFailures.push("content_pipeline");
  }

  try {
    inventoryGaps = await fetchInventoryGaps(resolvedAccountId);
  } catch {
    partialFailures.push("inventory_gap_system");
  }

  try {
    inventoryPrevention = await fetchInventoryPrevention(resolvedAccountId);
  } catch {
    partialFailures.push("inventory_prevention_system");
  }

  try {
    prediction = await fetchPrediction(resolvedAccountId);
  } catch {
    partialFailures.push("learning_engine");
  }

  const systemHealth = partialFailures.length ? "degraded" : "healthy";
  const { alerts, hiddenAlerts } = buildAlerts(inventoryGaps, systemHealth, partialFailures);
  const { todayFlow, primaryAction } = deriveFlowAndAction(
    trends,
    products,
    contentQueue,
    approvals,
    inventoryGaps,
    systemHealth
  );

  const flags = loadFeatureFlags();
  const access = buildAccessContext(
    resolvedAccountId || (userRecord && userRecord.id) || "",
    userRecord,
    flags,
    flags.commerce_mode
  );

  state.today_flow = todayFlow;
  state.trends = trends;
  state.products = products;
  state.inventory_gaps = inventoryGaps;
  state.inventory_prevention = inventoryPrevention;
  state.content_queue = contentQueue;
  state.approvals = approvals;
  state.performance = performance;
  state.prediction = prediction;
  state.alerts = alerts;
  state.hidden_alerts = hiddenAlerts;
  state.raw_logs = partialFailures.map((m) => ({ module: m, status: "unavailable" }));
  state.primary_action = primaryAction;
  state.system_health = systemHealth;
  state.access = access;

  return filterLiveStateForAccess(state, access);
}

module.exports = {
  emptyContract,
  assembleLiveState,
};
