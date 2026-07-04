/**
 * TikTok live state client — single API consumption for the dashboard.
 * Frontend MUST only use /api/tiktok-live-state (never individual subsystem APIs).
 */
(function (global) {
  "use strict";

  var MOUNT_ID = "tiktokLiveStateDashboard";
  var REFRESH_MS = 60000;
  var _cache = null;
  var _cacheTs = 0;

  function emptyContract() {
    return {
      today_flow: { step: "trend → product → content → queue", next_action: "unknown", status: "unknown" },
      trends: [],
      products: [],
      inventory_gaps: [],
      inventory_prevention: [],
      content_queue: [],
      approvals: [],
      performance: {},
      alerts: [],
      primary_action: { label: "unknown", action: "unknown", context_id: "unknown" },
      system_health: "unknown",
    };
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
    return "var(--yellow,#ffaa00)";
  }

  function getAccountId() {
    try {
      if (global.USER_TIKTOK_HANDLE) return String(global.USER_TIKTOK_HANDLE).trim();
      if (global.USER_NICHE) return String(global.USER_NICHE).trim();
      return "default";
    } catch (e) {
      return "default";
    }
  }

  async function fetchLiveState(accountId) {
    var url = "/api/tiktok-live-state?account_id=" + encodeURIComponent(accountId || "");
    try {
      var resp = await fetch(url, { method: "GET", credentials: "same-origin" });
      if (!resp.ok) return emptyContract();
      var data = await resp.json();
      return data && typeof data === "object" ? data : emptyContract();
    } catch (e) {
      return emptyContract();
    }
  }

  function renderList(items, labelKey) {
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

  function render(state) {
    var s = state && typeof state === "object" ? state : emptyContract();
    var flow = s.today_flow || {};
    var action = s.primary_action || {};
    var html =
      '<div class="card" style="margin-bottom:12px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
      '<h3 style="margin:0;font-size:14px">Live State</h3>' +
      '<span style="font-size:11px;color:' + healthColor(s.system_health) + '">' + esc(s.system_health) + "</span>" +
      "</div>" +
      '<p style="font-size:11px;color:var(--muted);margin:0 0 8px">' + esc(flow.step) + "</p>" +
      '<p style="font-size:12px;margin:0 0 4px"><strong>Next:</strong> ' + esc(flow.next_action) + "</p>" +
      '<p style="font-size:12px;margin:0 0 12px"><strong>Status:</strong> ' + esc(flow.status) + "</p>" +
      '<button type="button" id="tiktokLiveStatePrimaryBtn" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid var(--green);background:rgba(0,255,136,.1);color:var(--green);cursor:pointer">' +
      esc(action.label) +
      "</button>" +
      "</div>";

    html +=
      '<div class="card" style="margin-bottom:12px"><h4 style="margin:0 0 8px;font-size:13px">Trends</h4>' +
      renderList(s.trends, "summary") +
      "</div>";
    html +=
      '<div class="card" style="margin-bottom:12px"><h4 style="margin:0 0 8px;font-size:13px">Products</h4>' +
      renderList(s.products, "name") +
      "</div>";
    html +=
      '<div class="card" style="margin-bottom:12px"><h4 style="margin:0 0 8px;font-size:13px">Content Queue</h4>' +
      renderList(s.content_queue, "caption") +
      "</div>";
    html +=
      '<div class="card" style="margin-bottom:12px"><h4 style="margin:0 0 8px;font-size:13px">Approvals</h4>' +
      renderList(s.approvals, "caption") +
      "</div>";

    var alerts = Array.isArray(s.alerts) ? s.alerts : [];
    if (alerts.length) {
      html +=
        '<div class="card"><h4 style="margin:0 0 8px;font-size:13px">Alerts</h4>' +
        alerts
          .map(function (a) {
            return '<div style="font-size:11px;padding:4px 0;color:var(--amber)">⚠ ' + esc(a.message) + "</div>";
          })
          .join("") +
        "</div>";
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
    fetchLiveState: fetchLiveState,
    refresh: refresh,
    mount: mount,
    getCached: function () {
      return _cache || emptyContract();
    },
  };
})(typeof window !== "undefined" ? window : global);
