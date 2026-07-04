/**
 * TikTok live state client — includes features.commerce_mode in live state object.
 */
(function (global) {
  "use strict";

  var MOUNT_ID = "tiktokLiveStateMount";
  var REFRESH_MS = 60000;
  var _cache = null;

  function emptyContract() {
    var commerceMode = global.CommerceMode && global.CommerceMode.isCommerceMode();
    return {
      features: { commerce_mode: !!commerceMode },
      today_flow: {
        step: commerceMode ? "trend → product → content → queue" : "trend → content → plan → insights",
        next_action: "Run trend scan",
        status: "ready",
      },
      trends: [],
      products: [],
      inventory_gaps: [],
      content_queue: [],
      alerts: [],
      revenue_suggestions: [],
      primary_action: { label: "View content plan", action: "view_plan", context_id: "plan" },
      system_health: "unknown",
    };
  }

  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function getAccountId() {
    try {
      if (global.USER_NICHE) return String(global.USER_NICHE).trim();
      return "default";
    } catch (e) {
      return "default";
    }
  }

  async function fetchLiveState() {
    var commerceMode = global.CommerceMode && global.CommerceMode.isCommerceMode();
    var url =
      "/api/tiktok-live-state?account_id=" +
      encodeURIComponent(getAccountId()) +
      "&commerce_mode=" +
      (commerceMode ? "true" : "false");
    try {
      var resp = await fetch(url, { method: "GET", credentials: "same-origin" });
      if (!resp.ok) return emptyContract();
      var data = await resp.json();
      if (global.CommerceMode && typeof global.CommerceMode.mergeLiveStateFeatures === "function") {
        data = global.CommerceMode.mergeLiveStateFeatures(data);
      }
      return data && typeof data === "object" ? data : emptyContract();
    } catch (e) {
      return emptyContract();
    }
  }

  function render(state) {
    if (!global.CommerceMode || !global.CommerceMode.isCommerceMode()) return "";
    var s = state && typeof state === "object" ? state : emptyContract();
    var flow = s.today_flow || {};
    var html =
      '<div class="card" style="margin-bottom:12px" data-commerce-panel>' +
      '<h4 style="margin:0 0 8px;font-size:13px">Live Commerce State</h4>' +
      '<p style="font-size:11px;color:var(--muted);margin:0 0 4px">' +
      esc(flow.step) +
      "</p>" +
      '<p style="font-size:11px;margin:0"><strong>Next:</strong> ' +
      esc(flow.next_action) +
      "</p>" +
      '<p style="font-size:10px;color:var(--muted);margin-top:6px">commerce_mode: ' +
      (s.features && s.features.commerce_mode ? "ON" : "OFF") +
      "</p>" +
      "</div>";
    return html;
  }

  async function refresh() {
    var state = await fetchLiveState();
    _cache = state;
    global.TIKTOK_LIVE_STATE = state;

    var mount = document.getElementById(MOUNT_ID);
    if (mount && global.CommerceMode && global.CommerceMode.isCommerceMode()) {
      mount.innerHTML = render(state);
      mount.style.display = "";
    } else if (mount) {
      mount.innerHTML = "";
      mount.style.display = "none";
    }

    if (global.CommerceDashboard && typeof global.CommerceDashboard.update === "function") {
      global.CommerceDashboard.update({
        products: state.products || [],
        inventory_gaps: state.inventory_gaps || [],
        revenue_suggestions: state.revenue_suggestions || [],
      });
    }

    return state;
  }

  function mount() {
    if (!global.CommerceMode || !global.CommerceMode.isCommerceMode()) return;
    var trendsPanel = document.getElementById("tab-trends");
    if (!trendsPanel) return;
    if (!document.getElementById(MOUNT_ID)) {
      var wrapper = document.createElement("div");
      wrapper.id = MOUNT_ID;
      wrapper.setAttribute("data-commerce-panel", "1");
      trendsPanel.insertBefore(wrapper, trendsPanel.firstChild);
    }
    refresh();
    if (!global._tiktokLiveStateInterval) {
      global._tiktokLiveStateInterval = setInterval(refresh, REFRESH_MS);
    }
  }

  global.TiktokLiveStateClient = {
    emptyContract: emptyContract,
    fetchLiveState: fetchLiveState,
    refresh: refresh,
    mount: mount,
    getCached: function () {
      return _cache || emptyContract();
    },
  };
})(typeof window !== "undefined" ? window : global);
