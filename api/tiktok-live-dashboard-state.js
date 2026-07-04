/**
 * Live dashboard state for TikTok orchestration — derived from Supabase.
 * Safe defaults on all failures; never throws.
 */

const DEFAULT_MODE = "queue_only";
const VALID_MODES = new Set(["queue_only", "approval_required", "auto_post"]);

function emptyLiveState() {
  return {
    automation_mode: DEFAULT_MODE,
    pending_posts: [],
    queued_posts: [],
    approved_posts: [],
    blocked_posts: [],
    last_learning_update: null,
    system_health: "degraded",
  };
}

function getSupabaseConfig() {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "";
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    "";
  return { url: url.replace(/\/$/, ""), key };
}

function isAutoPostEnabled() {
  const v = String(process.env.AUTO_POST || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

async function supabaseRequest(path, options) {
  const { url, key } = getSupabaseConfig();
  if (!url || !key) return null;
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
  try {
    return await resp.json();
  } catch {
    return null;
  }
}

function serializeQueueRow(row) {
  if (!row || typeof row !== "object") return null;
  return {
    id: row.id || "",
    account_id: row.account_id || "",
    caption: row.caption || "",
    hashtags: Array.isArray(row.hashtags) ? row.hashtags : [],
    hook: row.hook || "",
    product_name: row.product_name || "",
    status: row.status || "",
    scheduled_time: row.scheduled_time || null,
    created_at: row.created_at || null,
    metadata: row.metadata || {},
  };
}

async function fetchQueueByStatus(accountId, statuses) {
  const statusFilter = statuses.map((s) => `"${s}"`).join(",");
  const path =
    `content_queue?account_id=eq.${encodeURIComponent(accountId)}` +
    `&status=in.(${statusFilter})` +
    `&select=id,account_id,caption,hashtags,hook,product_name,status,scheduled_time,created_at,metadata` +
    `&order=created_at.desc&limit=50`;
  const rows = await supabaseRequest(path, { method: "GET" });
  if (!Array.isArray(rows)) return [];
  return rows.map(serializeQueueRow).filter(Boolean);
}

async function fetchAutomationMode(accountId) {
  const rows = await supabaseRequest(
    `automation_settings?account_id=eq.${encodeURIComponent(accountId)}&select=mode&limit=1`,
    { method: "GET" }
  );
  if (!Array.isArray(rows) || !rows.length) return DEFAULT_MODE;
  const mode = String(rows[0].mode || DEFAULT_MODE);
  if (!VALID_MODES.has(mode)) return DEFAULT_MODE;
  if (mode === "auto_post" && !isAutoPostEnabled()) return DEFAULT_MODE;
  return mode;
}

async function fetchLastLearningUpdate(accountId) {
  const strategy = await supabaseRequest(
    `content_strategy_weights?account_id=eq.${encodeURIComponent(accountId)}&select=updated_at&limit=1`,
    { method: "GET" }
  );
  if (Array.isArray(strategy) && strategy[0]?.updated_at) {
    return strategy[0].updated_at;
  }
  const calibration = await supabaseRequest(
    "virality_calibration_logs?select=created_at&order=created_at.desc&limit=1",
    { method: "GET" }
  );
  if (Array.isArray(calibration) && calibration[0]?.created_at) {
    return calibration[0].created_at;
  }
  return null;
}

async function checkSupabaseAvailable() {
  const rows = await supabaseRequest("content_queue?select=id&limit=1", { method: "GET" });
  return Array.isArray(rows);
}

function computeSystemHealth({ supabaseOk, apifyFeedback, queueResult, learningResult }) {
  if (!supabaseOk) return "failing";

  let apifyRate = 1.0;
  if (apifyFeedback) {
    if (apifyFeedback.success === true) apifyRate = 1.0;
    else if (apifyFeedback.success === false) {
      apifyRate = apifyFeedback.source === "sample_fallback" ? 0.7 : 0.0;
    }
  }

  let queueFailRate = 0.0;
  if (queueResult?.error) queueFailRate = 0.5;

  let learningRate = 1.0;
  if (learningResult?.error) learningRate = 0.0;

  if (apifyRate < 0.3 || queueFailRate > 0.5 || learningRate < 0.3) return "failing";
  if (apifyRate < 0.8 || queueFailRate > 0.2 || learningRate < 0.8) return "degraded";
  return "healthy";
}

async function buildLiveState(accountId, context) {
  const state = emptyLiveState();
  const account = String(accountId || "").trim();
  if (!account) return state;

  const ctx = context || {};
  try {
    state.automation_mode = await fetchAutomationMode(account);
  } catch {
    /* keep default */
  }

  try {
    const supabaseOk = await checkSupabaseAvailable();
    if (!supabaseOk) {
      state.system_health = computeSystemHealth({
        supabaseOk: false,
        apifyFeedback: ctx.apifyFeedback,
        queueResult: ctx.queueResult,
        learningResult: ctx.learningResult,
      });
      return state;
    }

    const [pending, queued, approved, blocked, lastUpdate] = await Promise.all([
      fetchQueueByStatus(account, ["pending"]),
      fetchQueueByStatus(account, ["queued"]),
      fetchQueueByStatus(account, ["approved"]),
      fetchQueueByStatus(account, ["blocked"]),
      fetchLastLearningUpdate(account),
    ]);

    state.pending_posts = pending;
    state.queued_posts = queued;
    state.approved_posts = approved;
    state.blocked_posts = blocked;
    state.last_learning_update = lastUpdate;
    state.system_health = computeSystemHealth({
      supabaseOk: true,
      apifyFeedback: ctx.apifyFeedback,
      queueResult: ctx.queueResult,
      learningResult: ctx.learningResult,
    });
    return state;
  } catch {
    state.system_health = computeSystemHealth({
      supabaseOk: false,
      apifyFeedback: ctx.apifyFeedback,
      queueResult: ctx.queueResult,
      learningResult: ctx.learningResult,
    });
    return state;
  }
}

async function approveQueuedContent(contentId, decision) {
  const result = {
    success: false,
    content_id: String(contentId || ""),
    decision: String(decision || "").toLowerCase(),
    status: "",
    error: null,
  };

  const valid = new Set(["approve", "reject", "queue"]);
  if (!result.content_id) {
    result.error = "missing_content_id";
    return result;
  }
  if (!valid.has(result.decision)) {
    result.error = "invalid_decision";
    return result;
  }
  if (result.decision === "queue") {
    result.success = true;
    result.status = "unchanged";
    return result;
  }

  const newStatus = result.decision === "approve" ? "approved" : "blocked";
  result.status = newStatus;

  const rows = await supabaseRequest(
    `content_queue?id=eq.${encodeURIComponent(result.content_id)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus }),
      prefer: "return=representation",
    }
  );

  if (!Array.isArray(rows) || !rows.length) {
    result.error = "content_not_found";
    return result;
  }

  result.success = true;
  result.status = rows[0].status || newStatus;
  return result;
}

module.exports = {
  emptyLiveState,
  buildLiveState,
  approveQueuedContent,
  fetchAutomationMode,
  computeSystemHealth,
};
