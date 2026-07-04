/**
 * TikTok live state client — single API consumption for the dashboard.
 * Frontend MUST only use /api/tiktok-live-state (never individual subsystem APIs).
 * All roles receive the same JSON schema; visibility is content-level only.
 */
(function (global) {
  "use strict";

  var MOUNT_ID = "tiktokLiveStateDashboard";
  var REFRESH_MS = 60000;
  var _cache = null;
  var _cacheTs = 0;

  function resolveCommerceMode(state) {
    if (state && state.features && typeof state.features.commerce_mode === "boolean") {
      return state.features.commerce_mode;
    }
    if (state && typeof state.commerce_mode === "boolean") {
      return state.commerce_mode;
    }
    return !!(global.CommerceMode && global.CommerceMode.isCommerceMode());
  }

  function emptyContract() {
    var commerceMode = !!(global.CommerceMode && global.CommerceMode.isCommerceMode());
    return {
      features: { commerce_mode: commerceMode },
      today_flow: {
        step: commerceMode ? "trend → product → content → queue" : "trend → content → plan → insights",
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
      primary_action: { label: "unknown", action: "unknown", context_id: "unknown" },
      system_health: "unknown",
      access: { role: "creator", admin_override: false, visible_modules: ["trends", "tiktok", "prediction_engine", "analytics"], commerce_access: false },
    };
  }

  function asList(value) {
    return Array.isArray(value) ? value : [];
  }

  function asDict(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function normalizeLiveStateShape(state, access) {
    var base = emptyContract();
    if (!state || typeof state !== "object") {
      if (access) base.access = Object.assign({}, base.access, asDict(access));
      return base;
    }

    var normalized = emptyContract();
    normalized.today_flow = Object.assign({}, base.today_flow, asDict(state.today_flow));
    normalized.primary_action = Object.assign({}, base.primary_action, asDict(state.primary_action));
    normalized.access = Object.assign({}, base.access, asDict(state.access));
    if (access) normalized.access = Object.assign({}, normalized.access, asDict(access));

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
    normalized.system_health =
      state.system_health != null && String(state.system_health).trim()
        ? String(state.system_health).trim()
        : base.system_health;
    normalized.features = {
      commerce_mode: resolveCommerceMode(state),
    };

    return normalized;
  }

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function healthColor(health) {
    if (health === "healthy") return "var(--green)";
    if (health === "failing") return "var(--red,#ff4444)";
    if (health === "restricted" || health === "hidden") return "var(--muted)";
    return "var(--yellow,#ffaa00)";
  }

  function getAccountId() {
    try {
      if (global.currentUser && global.currentUser.id) return String(global.currentUser.id);
      if (global.USER_TIKTOK_HANDLE) return String(global.USER_TIKTOK_HANDLE).trim();
      if (global.USER_NICHE) return String(global.USER_NICHE).trim();
      return "default";
    } catch (e) {
      return "default";
    }
  }

  async function fetchLiveState(accountId) {
    var url = "/api/tiktok-live-state?account_id=" + encodeURIComponent(accountId || "");
    var headers = {};
    try {
      if (global.supabaseClient) {
        var session = await global.supabaseClient.auth.getSession();
        var token = session.data && session.data.session ? session.data.session.access_token : null;
        if (token) headers.Authorization = "Bearer " + token;
      }
    } catch (e) {}
    try {
      var resp = await fetch(url, { method: "GET", credentials: "same-origin", headers: headers });
      if (!resp.ok) return emptyContract();
      var data = await resp.json();
      return normalizeLiveStateShape(data && typeof data === "object" ? data : null);
    } catch (e) {
      return emptyContract();
    }
  }

  function renderList(items, labelKey, restricted) {
    if (restricted) {
      return '<p style="font-size:11px;color:var(--muted)">Restricted</p>';
    }
    var list = Array.isArray(items) ? items : [];
    if (!list.length) return '<p style="font-size:11px;color:var(--muted)">None</p>';
    return list
      .slice(0, 8)
      .map(function (item) {
        var label = esc((item && (item[labelKey] || item.name || item.summary || item.caption)) || "unknown");
        return '<div style="font-size:12px;padding:4px 0;border-bottom:1px solid var(--border)">• ' + label + "</div>";
      })
      .join("");
  }

  function isModuleVisible(access, module) {
    if (!access) return false;
    if (access.admin_override) return true;
    var visible = access.visible_modules || [];
    if (module === "tiktok" && visible.indexOf("trends") !== -1) return true;
    return visible.indexOf(module) !== -1;
  }

  function renderSection(title, bodyHtml, restricted) {
    var badge = restricted
      ? ' <span style="font-size:9px;color:var(--muted);font-weight:400">(restricted)</span>'
      : "";
    return (
      '<div class="card" style="margin-bottom:12px" data-rbac-section="' +
      esc(title) +
      '">' +
      '<h4 style="margin:0 0 8px;font-size:13px">' +
      esc(title) +
      badge +
      "</h4>" +
      bodyHtml +
      "</div>"
    );
  }

  function render(state) {
    var s = normalizeLiveStateShape(state);
    var access = s.access || {};
    var flow = s.today_flow || {};
    var action = s.primary_action || {};

    var healthRestricted = !isModuleVisible(access, "system_health");
    var healthLabel = healthRestricted ? "restricted" : s.system_health;

    var html =
      '<div class="card" style="margin-bottom:12px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
      '<h3 style="margin:0;font-size:14px">Live State</h3>' +
      '<span style="font-size:10px;color:var(--muted)">' +
      esc(access.role || "creator") +
      (access.admin_override ? " · ADMIN" : "") +
      "</span>" +
      "</div>" +
      '<span style="font-size:11px;color:' +
      healthColor(healthLabel) +
      '">System: ' +
      esc(healthLabel) +
      "</span>" +
      '<p style="font-size:11px;color:var(--muted);margin:8px 0">' +
      esc(flow.step) +
      "</p>" +
      '<p style="font-size:12px;margin:0 0 4px"><strong>Next:</strong> ' +
      esc(flow.next_action) +
      "</p>" +
      '<p style="font-size:12px;margin:0 0 12px"><strong>Status:</strong> ' +
      esc(flow.status) +
      "</p>" +
      '<button type="button" id="tiktokLiveStatePrimaryBtn" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid var(--green);background:rgba(0,255,136,.1);color:var(--green);cursor:pointer">' +
      esc(action.label) +
      "</button>" +
      "</div>";

    html += renderSection(
      "Trends",
      renderList(s.trends, "summary", !isModuleVisible(access, "tiktok")),
      !isModuleVisible(access, "tiktok")
    );
    html += renderSection(
      "Products",
      renderList(s.products, "name", !isModuleVisible(access, "products")),
      !isModuleVisible(access, "products")
    );
    html += renderSection(
      "Inventory Gaps",
      renderList(s.inventory_gaps, "product_name", !isModuleVisible(access, "inventory_system")),
      !isModuleVisible(access, "inventory_system")
    );
    html += renderSection(
      "Content Queue",
      renderList(s.content_queue, "caption", !isModuleVisible(access, "analytics")),
      !isModuleVisible(access, "analytics")
    );
    html += renderSection(
      "Approvals",
      renderList(s.approvals, "caption", !isModuleVisible(access, "analytics")),
      !isModuleVisible(access, "analytics")
    );

    var alerts = Array.isArray(s.alerts) ? s.alerts : [];
    var alertsBody =
      alerts.length > 0
        ? alerts
            .map(function (a) {
              return '<div style="font-size:11px;padding:4px 0;color:var(--amber)">⚠ ' + esc(a.message) + "</div>";
            })
            .join("")
        : '<p style="font-size:11px;color:var(--muted)">None</p>';
    html += renderSection("Alerts", alertsBody, false);

    if (access.admin_override) {
      html += renderSection(
        "Hidden Alerts",
        renderList(s.hidden_alerts, "message", false),
        false
      );
      html += renderSection(
        "Raw Logs",
        '<pre style="font-size:10px;max-height:120px;overflow:auto;margin:0;color:var(--muted)">' +
          esc(JSON.stringify(s.raw_logs || [], null, 2)) +
          "</pre>",
        false
      );
    }

    return html;
  }

  async function refresh() {
    var mount = document.getElementById(MOUNT_ID);
    if (!mount) return null;

    mount.innerHTML = '<p style="font-size:12px;color:var(--muted);padding:12px 0">Loading live state...</p>';
    var accountId = getAccountId();
    var state = await fetchLiveState(accountId);
    _cache = state;
    _cacheTs = Date.now();
    mount.innerHTML = render(state);
    global.TIKTOK_LIVE_STATE = state;

    if (global.TiktokLiveStateIntegration && typeof global.TiktokLiveStateIntegration.apply === "function") {
      global.TiktokLiveStateIntegration.apply(state);
    }

    if (global.TiktokAccessControl) {
      if (state.access) global.TiktokAccessControl.setAccess(state.access);
      global.TiktokAccessControl.applyModuleVisibility(state);
    }

    if (resolveCommerceMode(state) && global.CommerceDashboard && typeof global.CommerceDashboard.update === "function") {
      global.CommerceDashboard.update({
        products: state.products || [],
        inventory_gaps: state.inventory_gaps || [],
        revenue_suggestions: state.revenue_suggestions || [],
      });
    }

    return state;
  }

  function mount() {
    var trendsPanel = document.getElementById("tiktokTrendIntelligence");
    if (!trendsPanel) return;
    if (!document.getElementById(MOUNT_ID)) {
      var wrapper = document.createElement("div");
      wrapper.id = MOUNT_ID;
      wrapper.style.marginBottom = "16px";
      trendsPanel.parentNode.insertBefore(wrapper, trendsPanel);
    }
    refresh();
    if (!global._tiktokLiveStateInterval) {
      global._tiktokLiveStateInterval = setInterval(refresh, REFRESH_MS);
    }
  }

  global.TiktokLiveState = {
    emptyContract: emptyContract,
    normalizeLiveStateShape: normalizeLiveStateShape,
    fetchLiveState: fetchLiveState,
    refresh: refresh,
    mount: mount,
    getCached: function () {
      return _cache ? normalizeLiveStateShape(_cache) : emptyContract();
    },
  };
  global.TiktokLiveStateClient = global.TiktokLiveState;
})(typeof window !== "undefined" ? window : global);
