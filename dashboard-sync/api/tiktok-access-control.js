/**
 * Role-based access control (Node) — mirrors tiktok_access_control.py.
 * Read-only visibility layer; never grants privileges from client input.
 */

const fs = require("fs");
const path = require("path");

const VALID_ROLES = new Set(["admin", "creator", "viewer", "test"]);
const DEFAULT_ROLE = "creator";

const ALL_MODULES = [
  "trends",
  "products",
  "inventory_system",
  "prediction_engine",
  "analytics",
  "system_health",
  "raw_logs",
  "hidden_alerts",
];

const COMMERCE_GATED_MODULES = new Set(["products", "inventory_system"]);

function loadFeatureFlags() {
  try {
    const flagPath = path.join(__dirname, "..", "data", "feature_flags.json");
    const raw = JSON.parse(fs.readFileSync(flagPath, "utf8"));
    const flags = {};
    for (const [k, v] of Object.entries(raw || {})) flags[k] = Boolean(v);
    return flags;
  } catch {
    return {};
  }
}

function adminEmails() {
  const raw = process.env.TIKTOK_ADMIN_EMAILS || process.env.ADMIN_EMAILS || "";
  return new Set(
    raw
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean)
  );
}

function normalizeRole(value) {
  if (value == null) return null;
  const role = String(value).trim().toLowerCase();
  return VALID_ROLES.has(role) ? role : null;
}

function getUserRole(accountId, userRecord) {
  const user = userRecord && typeof userRecord === "object" ? userRecord : {};
  const metadata =
    user.user_metadata && typeof user.user_metadata === "object" ? user.user_metadata : {};

  const email = String(user.email || metadata.email || "")
    .trim()
    .toLowerCase();
  if (email && adminEmails().has(email)) return "admin";

  const metaRole = normalizeRole(metadata.role || metadata.user_role);
  if (metaRole === "admin") return "admin";
  if (metaRole) return metaRole;

  const envRole = normalizeRole(process.env[`TIKTOK_ROLE_${accountId}`]);
  if (envRole) return envRole;

  return DEFAULT_ROLE;
}

function getAdminOverride(userRole) {
  return userRole === "admin";
}

function resolveVisibleModules(userRole, featureFlags, commerceMode) {
  const flags = { ...loadFeatureFlags(), ...(featureFlags || {}) };
  let commerceEnabled = Boolean(flags.commerce_mode);
  if (commerceMode != null) commerceEnabled = Boolean(commerceMode);

  if (getAdminOverride(userRole)) return [...ALL_MODULES];

  const visible = [];
  for (const module of ALL_MODULES) {
    if (!flags[module]) continue;
    if (COMMERCE_GATED_MODULES.has(module) && !commerceEnabled) continue;
    visible.push(module);
  }
  return visible;
}

function buildAccessContext(accountId, userRecord, featureFlags, commerceMode) {
  const userRole = getUserRole(accountId, userRecord);
  const adminOverride = getAdminOverride(userRole);
  const flags = { ...loadFeatureFlags(), ...(featureFlags || {}) };
  const commerceEnabled = commerceMode != null ? Boolean(commerceMode) : Boolean(flags.commerce_mode);
  const visibleModules = resolveVisibleModules(userRole, featureFlags, commerceEnabled);
  return {
    role: userRole,
    admin_override: adminOverride,
    visible_modules: visibleModules,
    commerce_access: adminOverride || commerceEnabled,
  };
}

function emptyLiveStateContract() {
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
    prediction: {},
    alerts: [],
    hidden_alerts: [],
    raw_logs: [],
    primary_action: {
      label: "unknown",
      action: "unknown",
      context_id: "unknown",
    },
    system_health: "unknown",
    access: {
      role: DEFAULT_ROLE,
      admin_override: false,
      visible_modules: [],
      commerce_access: false,
    },
  };
}

function asDict(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeLiveStateShape(state, access) {
  const base = emptyLiveStateContract();
  if (!state || typeof state !== "object") {
    if (access) base.access = { ...base.access, ...asDict(access) };
    return base;
  }

  const normalized = emptyLiveStateContract();
  normalized.today_flow = { ...base.today_flow, ...asDict(state.today_flow) };
  normalized.primary_action = { ...base.primary_action, ...asDict(state.primary_action) };
  normalized.access = { ...base.access, ...asDict(state.access) };
  if (access) normalized.access = { ...normalized.access, ...asDict(access) };

  normalized.trends = asList(state.trends);
  normalized.products = asList(state.products);
  normalized.inventory_gaps = asList(state.inventory_gaps);
  normalized.inventory_prevention = asList(state.inventory_prevention);
  normalized.content_queue = asList(state.content_queue);
  normalized.approvals = asList(state.approvals);
  normalized.alerts = asList(state.alerts);
  normalized.hidden_alerts = asList(state.hidden_alerts);
  normalized.raw_logs = asList(state.raw_logs);
  normalized.performance = asDict(state.performance);
  normalized.prediction = asDict(state.prediction);

  const health = state.system_health;
  normalized.system_health =
    health != null && String(health).trim() ? String(health).trim() : base.system_health;

  return normalized;
}

function filterLiveStateForAccess(state, access) {
  const accessCtx = asDict(access);
  const normalized = normalizeLiveStateShape(state, accessCtx);

  if (accessCtx.admin_override) return normalized;

  const visible = new Set(accessCtx.visible_modules || []);

  if (!visible.has("trends")) normalized.trends = [];
  if (!visible.has("products")) normalized.products = [];
  if (!visible.has("inventory_system")) {
    normalized.inventory_gaps = [];
    normalized.inventory_prevention = [];
  }
  if (!visible.has("prediction_engine")) normalized.prediction = {};
  if (!visible.has("analytics")) {
    normalized.performance = {};
    normalized.content_queue = [];
    normalized.approvals = [];
  }
  if (!visible.has("system_health")) normalized.system_health = "restricted";
  if (!visible.has("raw_logs")) normalized.raw_logs = [];
  if (!visible.has("hidden_alerts")) {
    normalized.hidden_alerts = [];
    normalized.alerts = normalized.alerts.filter((a) => a && a.level !== "hidden");
  }

  return normalized;
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

async function resolveUserFromAuthHeader(req) {
  const auth = (req.headers && (req.headers.authorization || req.headers.Authorization)) || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!token) return null;

  const { url, key } = getSupabaseConfig();
  if (!url || !key) return null;

  try {
    const resp = await fetch(`${url}/auth/v1/user`, {
      headers: {
        apikey: key,
        Authorization: `Bearer ${token}`,
      },
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

module.exports = {
  VALID_ROLES,
  DEFAULT_ROLE,
  ALL_MODULES,
  loadFeatureFlags,
  getUserRole,
  getAdminOverride,
  resolveVisibleModules,
  buildAccessContext,
  emptyLiveStateContract,
  normalizeLiveStateShape,
  filterLiveStateForAccess,
  resolveUserFromAuthHeader,
};
