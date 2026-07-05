/**
 * Multi-source Trend Intelligence Dashboard panel.
 * Fetches /api/trend-intelligence and renders live provider status + opportunities.
 */
(function (global) {
  "use strict";

  var MOUNT_ID = "trendIntelligenceDashboard";
  var REFRESH_MS = 60000;
  var _cache = null;

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function healthColor(status) {
    if (status === "healthy" || status === "operational") return "var(--green)";
    if (status === "offline" || status === "failing") return "var(--red,#ff4444)";
    return "var(--yellow,#ffaa00)";
  }

  function formatTime(iso) {
    if (!iso) return "No scan yet";
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return "No scan yet";
      return d.toLocaleString();
    } catch (e) {
      return "No scan yet";
    }
  }

  function emptyState() {
    return {
      system_status: "initializing",
      health_status: "unknown",
      providers_online: [],
      providers_offline: [],
      warnings: [],
      trends: [],
      opportunities: [],
      emerging_keywords: [],
      buying_intent_opportunities: [],
      recommendations: {},
      content_queue: [],
      recent_discoveries: [],
      last_scan_time: null,
    };
  }

  async function fetchState(niche) {
    var n = niche || (global.USER_NICHE ? String(global.USER_NICHE) : "general");
    try {
      var resp = await fetch("/api/trend-intelligence?niche=" + encodeURIComponent(n), {
        credentials: "same-origin",
      });
      if (!resp.ok) return emptyState();
      return await resp.json();
    } catch (e) {
      return emptyState();
    }
  }

  function renderProviderPills(online, offline) {
    var html = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0">';
    (online || []).forEach(function (p) {
      html +=
        '<span style="font-size:10px;padding:3px 8px;border-radius:12px;background:rgba(0,255,136,.12);color:var(--green);border:1px solid rgba(0,255,136,.3)">' +
        esc(p) +
        " online</span>";
    });
    (offline || []).forEach(function (p) {
      html +=
        '<span style="font-size:10px;padding:3px 8px;border-radius:12px;background:rgba(255,170,0,.1);color:var(--yellow,#ffaa00);border:1px solid rgba(255,170,0,.3)" title="Provider unavailable — other sources still active">' +
        esc(p) +
        " offline</span>";
    });
    if (!online.length && !offline.length) {
      html += '<span style="font-size:10px;color:var(--muted)">Checking providers...</span>';
    }
    html += "</div>";
    return html;
  }

  function renderList(items, labelFn, emptyMsg) {
    if (!items || !items.length) {
      return '<p style="font-size:11px;color:var(--muted);margin:0">' + esc(emptyMsg) + "</p>";
    }
    return items
      .slice(0, 8)
      .map(function (item) {
        return (
          '<div style="font-size:12px;padding:5px 0;border-bottom:1px solid var(--border)">• ' +
          esc(labelFn(item)) +
          "</div>"
        );
      })
      .join("");
  }

  function renderOpportunities(opps) {
    if (!opps || !opps.length) {
      return '<p style="font-size:11px;color:var(--muted);margin:0">Scanning for buying-intent opportunities...</p>';
    }
    return opps
      .slice(0, 8)
      .map(function (o) {
        var score = o.opportunity_score != null ? o.opportunity_score : 0;
        var hook = o.hook || o.keyword || o.trend || "";
        return (
          '<div style="font-size:12px;padding:6px 0;border-bottom:1px solid var(--border)">' +
          '<div style="display:flex;justify-content:space-between;gap:8px">' +
          '<span>' +
          esc(hook) +
          "</span>" +
          '<span style="font-size:10px;color:var(--green);white-space:nowrap">Score ' +
          esc(score) +
          "</span>" +
          "</div>" +
          '<div style="font-size:10px;color:var(--muted);margin-top:2px">' +
          esc(o.source || "multi-source") +
          (o.buying_intent ? " · intent " + o.buying_intent : "") +
          "</div></div>"
        );
      })
      .join("");
  }

  function renderRecommendations(rec) {
    rec = rec || {};
    var primary = rec.primary_action || {};
    var html = "";
    if (primary.label) {
      html +=
        '<p style="font-size:12px;margin:0 0 8px"><strong>Today:</strong> ' +
        esc(primary.label) +
        "</p>";
    }
    if (rec.ai_insight) {
      html +=
        '<p style="font-size:11px;color:var(--muted);margin:0 0 8px;font-style:italic">' +
        esc(rec.ai_insight) +
        "</p>";
    }
    var today = rec.content_to_create_today || [];
    if (today.length) {
      html += renderList(
        today,
        function (i) {
          return (i.hook || i.keyword || "") + " (score " + (i.opportunity_score || 0) + ")";
        },
        ""
      );
    } else {
      html += '<p style="font-size:11px;color:var(--muted);margin:0">Recommendations refresh after each scan</p>';
    }
    return html;
  }

  function render(state) {
    state = state || emptyState();
    var warnings = state.warnings || [];
    var warningHtml = warnings.length
      ? warnings
          .slice(0, 4)
          .map(function (w) {
            return '<div style="font-size:10px;color:var(--yellow,#ffaa00);padding:2px 0">⚠ ' + esc(w) + "</div>";
          })
          .join("")
      : "";

    return (
      '<div class="card" style="margin-bottom:16px" id="trendIntelPanel">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
      '<h3 style="margin:0;font-size:14px">Trend Intelligence Engine</h3>' +
      '<span style="font-size:10px;color:' +
      healthColor(state.health_status) +
      '">' +
      esc(state.system_status || state.health_status || "operational") +
      "</span>" +
      "</div>" +
      '<p style="font-size:11px;color:var(--muted);margin:0 0 4px">Last scan: ' +
      esc(formatTime(state.last_scan_time)) +
      "</p>" +
      warningHtml +
      "<h4 style=\"font-size:12px;margin:12px 0 6px\">Trend Providers</h4>" +
      renderProviderPills(state.providers_online, state.providers_offline) +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">' +
      '<div><h4 style="font-size:12px;margin:0 0 6px">Trending Topics</h4>' +
      renderList(
        state.trends,
        function (t) {
          return (t.keyword || t.trend || "") + " (" + (t.source || "source") + ")";
        },
        "Topics appear after first scan"
      ) +
      "</div>" +
      '<div><h4 style="font-size:12px;margin:0 0 6px">Emerging Keywords</h4>' +
      renderList(
        state.emerging_keywords,
        function (k) {
          return (k.keyword || "") + " · " + (k.popularity || 0);
        },
        "Emerging keywords update hourly"
      ) +
      "</div></div>" +
      '<h4 style="font-size:12px;margin:12px 0 6px">Buying Intent Opportunities</h4>' +
      renderOpportunities(state.buying_intent_opportunities || state.opportunities) +
      '<h4 style="font-size:12px;margin:12px 0 6px">AI Recommendations</h4>' +
      renderRecommendations(state.recommendations) +
      '<h4 style="font-size:12px;margin:12px 0 6px">Content Queue</h4>' +
      renderList(
        state.content_queue,
        function (q) {
          return (q.caption || q.hook || "Queued item") + " · " + (q.status || "pending");
        },
        "No queued content"
      ) +
      '<h4 style="font-size:12px;margin:12px 0 6px">Recent Discoveries</h4>' +
      renderList(
        state.recent_discoveries || state.trends,
        function (d) {
          return (d.keyword || d.trend || "") + " from " + (d.source || "scan");
        },
        "Discoveries appear as providers report"
      ) +
      "</div>"
    );
  }

  async function refresh() {
    var mount = document.getElementById(MOUNT_ID);
    if (!mount) return null;
    mount.innerHTML = '<p style="font-size:12px;color:var(--muted)">Loading trend intelligence...</p>';
    var niche = global.USER_NICHE ? String(global.USER_NICHE) : "general";
    var state = await fetchState(niche);
    _cache = state;
    mount.innerHTML = render(state);
    global.TREND_INTELLIGENCE_STATE = state;
    return state;
  }

  function mount() {
    var anchor = document.getElementById("tiktokTrendIntelligence");
    if (!anchor) return;
    if (!document.getElementById(MOUNT_ID)) {
      var wrapper = document.createElement("div");
      wrapper.id = MOUNT_ID;
      anchor.parentNode.insertBefore(wrapper, anchor);
    }
    refresh();
    if (!global._trendIntelInterval) {
      global._trendIntelInterval = setInterval(refresh, REFRESH_MS);
    }
  }

  global.TrendIntelligenceDashboard = {
    fetchState: fetchState,
    refresh: refresh,
    mount: mount,
    render: render,
    getCached: function () {
      return _cache || emptyState();
    },
  };
})(typeof window !== "undefined" ? window : global);
