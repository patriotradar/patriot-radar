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

function filterLiveStateForAccess(state, access) {
  if (!state || typeof state !== "object") return {};
  if (access.admin_override) return { ...state };

  const visible = new Set(access.visible_modules || []);
  const filtered = { ...state };

  if (!visible.has("system_health")) filtered.system_health = "restricted";
  if (!visible.has("raw_logs")) filtered.raw_logs = [];
  if (!visible.has("hidden_alerts")) {
    filtered.hidden_alerts = [];
    filtered.alerts = (filtered.alerts || []).filter((a) => a && a.level !== "hidden");
  }
  if (!visible.has("products")) filtered.products = [];
  if (!visible.has("inventory_system")) {
    filtered.inventory_gaps = [];
    filtered.inventory_prevention = [];
  }
  if (!visible.has("prediction_engine")) filtered.prediction = {};
  if (!visible.has("analytics")) filtered.performance = {};

  return filtered;
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
  filterLiveStateForAccess,
  resolveUserFromAuthHeader,
};
