/**
 * TikTok RBAC client — consumes server-derived access from live state API.
 * NEVER grants admin privileges from frontend input.
 */
(function (global) {
  "use strict";

  var MODULE_DOM_MAP = {
    trends: [
      "#intelligenceFeed",
      "#tiktokTrendIntelligence",
      "#liveFeed",
      "#topOpportunities",
      "#aiTrendInsights",
      "#themeAnalysis",
      "#scoringGuide",
    ],
    products: ["#primaryTarget", "#contentFunnel"],
    inventory_system: ["#inventorySystemPanel"],
    prediction_engine: [
      "#nicheCommentViralityPrediction",
      "#viralityIntelligenceExtension",
      "#nicheCommentIntelligence",
    ],
    analytics: ["#tab-mystats", '[data-tab="mystats"]'],
    system_health: ["#rbacSystemHealthPanel"],
    raw_logs: ["#rbacRawLogsPanel"],
    hidden_alerts: ["#rbacHiddenAlertsPanel"],
  };

  var _access = {
    role: "creator",
    admin_override: false,
    visible_modules: ["trends", "prediction_engine", "analytics"],
    commerce_access: false,
  };

  function setAccess(access) {
    if (!access || typeof access !== "object") return;
    _access = {
      role: access.role || "creator",
      admin_override: Boolean(access.admin_override),
      visible_modules: Array.isArray(access.visible_modules) ? access.visible_modules.slice() : [],
      commerce_access: Boolean(access.commerce_access),
    };
    global.TIKTOK_ACCESS = _access;
    global.isAdminUser = _access.admin_override;
    global.USER_ROLE = _access.role;
    global.ADMIN_OVERRIDE = _access.admin_override;
  }

  function getAccess() {
    return {
      role: _access.role,
      admin_override: _access.admin_override,
      visible_modules: _access.visible_modules.slice(),
      commerce_access: _access.commerce_access,
    };
  }

  function isModuleVisible(module) {
    if (_access.admin_override) return true;
    return _access.visible_modules.indexOf(module) !== -1;
  }

  function canAccessCommerce() {
    return _access.admin_override || _access.commerce_access;
  }

  var ADMIN_ONLY_MODULES = {
    system_health: true,
    raw_logs: true,
    hidden_alerts: true,
  };

  function showElement(selector) {
    var nodes = document.querySelectorAll(selector);
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].style.display = "";
      nodes[i].classList.remove("rbac-hidden");
      nodes[i].classList.remove("rbac-restricted");
      nodes[i].removeAttribute("data-rbac-restricted");
    }
  }

  function hideElement(selector) {
    var nodes = document.querySelectorAll(selector);
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].style.display = "none";
      nodes[i].classList.add("rbac-hidden");
    }
  }

  function restrictElement(selector) {
    var nodes = document.querySelectorAll(selector);
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].style.display = "";
      nodes[i].classList.remove("rbac-hidden");
      nodes[i].classList.add("rbac-restricted");
      nodes[i].setAttribute("data-rbac-restricted", "true");
    }
  }

  function ensureAdminPanels() {
    var trendsTab = document.getElementById("tab-trends");
    if (!trendsTab) return;

    if (!document.getElementById("rbacSystemHealthPanel")) {
      var health = document.createElement("div");
      health.id = "rbacSystemHealthPanel";
      health.className = "card rbac-admin-only";
      health.style.cssText = "margin-bottom:12px;display:none";
      health.innerHTML =
        '<h4 style="margin:0 0 8px;font-size:13px;color:var(--amber)">System Health (Admin)</h4>' +
        '<div id="rbacSystemHealthContent" style="font-size:11px;color:var(--muted)">Loading...</div>';
      trendsTab.appendChild(health);
    }

    if (!document.getElementById("rbacRawLogsPanel")) {
      var logs = document.createElement("div");
      logs.id = "rbacRawLogsPanel";
      logs.className = "card rbac-admin-only";
      logs.style.cssText = "margin-bottom:12px;display:none";
      logs.innerHTML =
        '<h4 style="margin:0 0 8px;font-size:13px;color:var(--amber)">Raw Logs (Admin)</h4>' +
        '<pre id="rbacRawLogsContent" style="font-size:10px;max-height:160px;overflow:auto;margin:0;color:var(--muted)"></pre>';
      trendsTab.appendChild(logs);
    }

    if (!document.getElementById("rbacHiddenAlertsPanel")) {
      var hidden = document.createElement("div");
      hidden.id = "rbacHiddenAlertsPanel";
      hidden.className = "card rbac-admin-only";
      hidden.style.cssText = "margin-bottom:12px;display:none";
      hidden.innerHTML =
        '<h4 style="margin:0 0 8px;font-size:13px;color:var(--red,#ff4444)">Hidden Alerts (Admin)</h4>' +
        '<div id="rbacHiddenAlertsContent" style="font-size:11px;color:var(--muted)"></div>';
      trendsTab.appendChild(hidden);
    }

    if (!document.getElementById("inventorySystemPanel")) {
      var inv = document.createElement("div");
      inv.id = "inventorySystemPanel";
      inv.className = "card";
      inv.style.cssText = "margin-bottom:12px;display:none";
      inv.innerHTML =
        '<h4 style="margin:0 0 8px;font-size:13px">Inventory System</h4>' +
        '<div id="inventorySystemContent" style="font-size:11px;color:var(--muted)">No inventory data</div>';
      trendsTab.appendChild(inv);
    }
  }

  function renderAdminDebugPanels(liveState) {
    var state = liveState || {};
    var healthEl = document.getElementById("rbacSystemHealthContent");
    if (healthEl) {
      healthEl.textContent = "Status: " + (state.system_health || "unknown");
    }
    var logsEl = document.getElementById("rbacRawLogsContent");
    if (logsEl) {
      try {
        logsEl.textContent = JSON.stringify(state.raw_logs || [], null, 2);
      } catch (e) {
        logsEl.textContent = "[]";
      }
    }
    var hiddenEl = document.getElementById("rbacHiddenAlertsContent");
    if (hiddenEl) {
      var alerts = state.hidden_alerts || [];
      if (!alerts.length) {
        hiddenEl.textContent = "No hidden alerts";
      } else {
        hiddenEl.innerHTML = alerts
          .map(function (a) {
            return "<div>• " + (a.message || a.code || "alert") + "</div>";
          })
          .join("");
      }
    }
    var invEl = document.getElementById("inventorySystemContent");
    if (invEl) {
      var gaps = state.inventory_gaps || [];
      var prev = state.inventory_prevention || [];
      invEl.textContent =
        gaps.length || prev.length
          ? gaps.length + " gap(s), " + prev.length + " prevention rule(s)"
          : "No inventory data";
    }
  }

  function applyModuleVisibility(liveState) {
    ensureAdminPanels();
    var visibleSet = {};
    var modules = _access.visible_modules || [];
    for (var i = 0; i < modules.length; i++) visibleSet[modules[i]] = true;

    if (_access.admin_override) {
      for (var mod in MODULE_DOM_MAP) visibleSet[mod] = true;
    }

    for (var moduleName in MODULE_DOM_MAP) {
      var selectors = MODULE_DOM_MAP[moduleName];
      var show = Boolean(visibleSet[moduleName]);
      var adminOnly = Boolean(ADMIN_ONLY_MODULES[moduleName]);
      for (var j = 0; j < selectors.length; j++) {
        if (show) {
          showElement(selectors[j]);
        } else if (adminOnly) {
          hideElement(selectors[j]);
        } else {
          restrictElement(selectors[j]);
        }
      }
    }

    var adminBtn = document.getElementById("adminTabBtn");
    if (adminBtn) {
      if (_access.admin_override) adminBtn.style.display = "";
      else if (!global.isAmbassador) adminBtn.style.display = "none";
    }

    if (_access.admin_override) {
      renderAdminDebugPanels(liveState);
      document.body.classList.add("rbac-admin-view");
    } else {
      document.body.classList.remove("rbac-admin-view");
    }
  }

  async function fetchAccessFromLiveState(accountId, authToken) {
    var url = "/api/tiktok-live-state?account_id=" + encodeURIComponent(accountId || "");
    var headers = {};
    if (authToken) headers.Authorization = "Bearer " + authToken;
    try {
      var resp = await fetch(url, { method: "GET", credentials: "same-origin", headers: headers });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (e) {
      return null;
    }
  }

  async function initFromSession(supabaseClient, accountId) {
    var token = null;
    try {
      var session = await supabaseClient.auth.getSession();
      token = session.data && session.data.session ? session.data.session.access_token : null;
    } catch (e) {}

    var liveState = await fetchAccessFromLiveState(accountId, token);
    if (liveState && liveState.access) {
      setAccess(liveState.access);
      applyModuleVisibility(liveState);
      global.TIKTOK_LIVE_STATE = liveState;
      return liveState;
    }

    setAccess({
      role: "creator",
      admin_override: false,
      visible_modules: ["trends", "prediction_engine", "analytics"],
      commerce_access: false,
    });
    applyModuleVisibility(null);
    return null;
  }

  global.TiktokAccessControl = {
    setAccess: setAccess,
    getAccess: getAccess,
    isModuleVisible: isModuleVisible,
    canAccessCommerce: canAccessCommerce,
    applyModuleVisibility: applyModuleVisibility,
    initFromSession: initFromSession,
    renderAdminDebugPanels: renderAdminDebugPanels,
  };
})(typeof window !== "undefined" ? window : global);
