/**
 * Live dashboard orchestration panels for the TikTok viral loop.
 * Graceful degradation — never crashes on missing data.
 */
(function (global) {
  "use strict";

  var MOUNT_ID = "tiktokOrchestrationDashboard";
  var REFRESH_MS = 60000;

  function emptyLiveState() {
    return {
      automation_mode: "queue_only",
      pending_posts: [],
      queued_posts: [],
      approved_posts: [],
      blocked_posts: [],
      last_learning_update: null,
      system_health: "degraded",
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

  function renderPostRow(post, showActions) {
    var caption = esc((post && post.caption) || "(no caption)");
    var product = esc((post && post.product_name) || "");
    var status = esc((post && post.status) || "");
    var id = esc((post && post.id) || "");
    var actions = "";
    if (showActions && id) {
      actions =
        '<div style="margin-top:6px;display:flex;gap:6px">' +
        '<button type="button" class="btn-approve" data-id="' + id + '" style="font-size:10px;padding:4px 8px;border-radius:4px;border:1px solid var(--green);background:rgba(0,255,136,.1);color:var(--green);cursor:pointer">Approve</button>' +
        '<button type="button" class="btn-reject" data-id="' + id + '" style="font-size:10px;padding:4px 8px;border-radius:4px;border:1px solid var(--red,#ff4444);background:rgba(255,68,68,.1);color:var(--red,#ff4444);cursor:pointer">Reject</button>' +
        "</div>";
    }
    return (
      '<div style="padding:8px 0;border-bottom:1px solid var(--border)">' +
      '<div style="font-size:11px;color:var(--muted)">' + status + (product ? " · " + product : "") + "</div>" +
      '<div style="font-size:12px;margin-top:2px">' + caption.slice(0, 120) + "</div>" +
      actions +
      "</div>"
    );
  }

  function renderProductList(products, label) {
    var list = Array.isArray(products) ? products : [];
    if (!list.length) {
      return '<p style="font-size:11px;color:var(--muted)">No ' + esc(label) + " detected yet.</p>";
    }
    return list
      .slice(0, 6)
      .map(function (p) {
        var name = esc((p && (p.product || p.name)) || "Unknown");
        var score = p && (p.signal_strength != null ? p.signal_strength : p.score);
        var scoreStr = score != null ? " · " + esc(String(score)) : "";
        return '<div style="font-size:12px;padding:4px 0">• ' + name + scoreStr + "</div>";
      })
      .join("");
  }

  function renderContentPack(pack) {
    var p = pack && typeof pack === "object" ? pack : {};
    var captions = Array.isArray(p.captions) ? p.captions : [];
    var hashtags = Array.isArray(p.hashtags) ? p.hashtags : [];
    var hooks = Array.isArray(p.hook_variations) ? p.hook_variations : [];
    if (!captions.length && !hashtags.length && !hooks.length) {
      return '<p style="font-size:11px;color:var(--muted)">Content pack not generated yet.</p>';
    }
    var html = "";
    if (captions.length) {
      html += '<div style="font-size:11px;color:var(--muted);margin-bottom:4px">Captions</div>';
      html += captions
        .slice(0, 3)
        .map(function (c) {
          return '<div style="font-size:12px;padding:2px 0">"' + esc(c).slice(0, 100) + '"</div>';
        })
        .join("");
    }
    if (hashtags.length) {
      html += '<div style="font-size:11px;color:var(--muted);margin:8px 0 4px">Hashtags</div><div style="font-size:12px">' + esc(hashtags.join(" ")) + "</div>";
    }
    return html;
  }

  function renderPerformance(perfRows) {
    var rows = Array.isArray(perfRows) ? perfRows : [];
    if (!rows.length) {
      return '<p style="font-size:11px;color:var(--muted)">No performance data yet.</p>';
    }
    var bestCaption = "";
    var bestRate = -1;
    rows.forEach(function (row) {
      var metrics = (row && row.performance_metrics) || row.metrics || {};
      var rate = parseFloat(metrics.engagement_rate || 0);
      var cap = (row && row.matched_queue_caption) || metrics.caption_preview || "";
      if (rate > bestRate) {
        bestRate = rate;
        bestCaption = cap;
      }
    });
    return (
      rows
        .slice(0, 5)
        .map(function (row) {
          var m = (row && row.performance_metrics) || row.metrics || {};
          return (
            '<div style="font-size:12px;padding:4px 0;border-bottom:1px solid var(--border)">' +
            "Views: " + esc(String(m.views || 0)) +
            " · Engagement: " + esc(String((m.engagement_rate || 0).toFixed ? (m.engagement_rate || 0).toFixed(4) : m.engagement_rate || 0)) +
            "</div>"
          );
        })
        .join("") +
      (bestCaption
        ? '<div style="margin-top:8px;font-size:11px;color:var(--muted)">Best caption: "' + esc(bestCaption).slice(0, 80) + '"</div>'
        : "")
    );
  }

  function renderStrategy(weights, lastUpdate) {
    var w = weights && typeof weights === "object" ? weights : {};
    var captionStyle = w.caption_style || {};
    var html = '<div style="font-size:11px;color:var(--muted);margin-bottom:6px">Caption style weights</div>';
    var keys = Object.keys(captionStyle);
    if (!keys.length) {
      html += '<p style="font-size:11px;color:var(--muted)">Strategy weights not available.</p>';
    } else {
      html += keys
        .map(function (k) {
          return '<div style="font-size:12px">' + esc(k) + ": " + esc(String(captionStyle[k])) + "</div>";
        })
        .join("");
    }
    if (lastUpdate) {
      html += '<div style="margin-top:8px;font-size:11px;color:var(--muted)">Last optimization: ' + esc(String(lastUpdate)) + "</div>";
    }
    return html;
  }

  function renderDashboard(data) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var live = (data && data.live_state) || emptyLiveState();
    var emerging = (data && data.emerging_products) || [];
    var trending = (data && data.trending_products) || [];
    var pack = (data && data.content_pack) || {};
    var perf = (data && data.performance_tracking && data.performance_tracking.snapshots) || [];
    var strategy = (data && data.strategy_update && data.strategy_update.weights) || {};

    var pending = live.pending_posts || [];
    var queued = live.queued_posts || [];
    var queueForApproval = pending.length ? pending : queued;

    el.innerHTML =
      '<div class="card" style="margin-top:12px;border-color:rgba(0,255,136,.2)">' +
      '<div class="card-header"><h2 style="color:var(--green)">Live Viral Loop</h2>' +
      '<span style="font-size:11px;padding:4px 8px;border-radius:12px;border:1px solid ' +
      healthColor(live.system_health) +
      ";color:" +
      healthColor(live.system_health) +
      '">' +
      esc(live.system_health || "degraded") +
      "</span></div>" +
      '<div style="font-size:11px;color:var(--muted);margin-bottom:12px">Automation: <strong style="color:var(--text)">' +
      esc(live.automation_mode || "queue_only") +
      "</strong></div>" +
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px">' +
      '<div style="padding:10px;border:1px solid var(--border);border-radius:8px">' +
      "<h3 style=\"font-size:13px;margin:0 0 8px\">Viral Loop</h3>" +
      '<div style="font-size:11px;color:var(--muted);margin-bottom:4px">Emerging products</div>' +
      renderProductList(emerging, "emerging products") +
      '<div style="font-size:11px;color:var(--muted);margin:12px 0 4px">Trending products</div>' +
      renderProductList(trending, "trending products") +
      '<div style="font-size:11px;color:var(--muted);margin:12px 0 4px">Content pack</div>' +
      renderContentPack(pack) +
      "</div>" +
      '<div style="padding:10px;border:1px solid var(--border);border-radius:8px" id="orchestrationQueuePanel">' +
      "<h3 style=\"font-size:13px;margin:0 0 8px\">Content Queue</h3>" +
      (queueForApproval.length
        ? queueForApproval.map(function (p) {
            return renderPostRow(p, live.automation_mode === "approval_required" || p.status === "pending");
          }).join("")
        : '<p style="font-size:11px;color:var(--muted)">Queue is empty.</p>') +
      "</div>" +
      '<div style="padding:10px;border:1px solid var(--border);border-radius:8px">' +
      "<h3 style=\"font-size:13px;margin:0 0 8px\">Performance</h3>" +
      renderPerformance(perf) +
      "</div>" +
      '<div style="padding:10px;border:1px solid var(--border);border-radius:8px">' +
      "<h3 style=\"font-size:13px;margin:0 0 8px\">Strategy</h3>" +
      renderStrategy(strategy, live.last_learning_update) +
      "</div>" +
      "</div></div>";

    el.querySelectorAll(".btn-approve, .btn-reject").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-id");
        var decision = btn.classList.contains("btn-approve") ? "approve" : "reject";
        handleApproval(id, decision);
      });
    });
  }

  async function fetchLiveStateFromSupabase(accountId) {
    if (!global.supabaseClient) return emptyLiveState();
    var live = emptyLiveState();
    try {
      var modeResp = await global.supabaseClient
        .from("automation_settings")
        .select("mode")
        .eq("account_id", accountId)
        .limit(1);
      if (modeResp.data && modeResp.data[0] && modeResp.data[0].mode) {
        live.automation_mode = modeResp.data[0].mode;
      }
    } catch (e) {}

    var statuses = [
      ["pending_posts", "pending"],
      ["queued_posts", "queued"],
      ["approved_posts", "approved"],
      ["blocked_posts", "blocked"],
    ];
    for (var i = 0; i < statuses.length; i++) {
      try {
        var resp = await global.supabaseClient
          .from("content_queue")
          .select("id,account_id,caption,hashtags,hook,product_name,status,scheduled_time,created_at,metadata")
          .eq("account_id", accountId)
          .eq("status", statuses[i][1])
          .order("created_at", { ascending: false })
          .limit(50);
        live[statuses[i][0]] = resp.data || [];
      } catch (e) {
        live[statuses[i][0]] = [];
      }
    }

    try {
      var strat = await global.supabaseClient
        .from("content_strategy_weights")
        .select("updated_at")
        .eq("account_id", accountId)
        .limit(1);
      if (strat.data && strat.data[0]) {
        live.last_learning_update = strat.data[0].updated_at;
      }
    } catch (e) {}

    live.system_health = live.pending_posts.length || live.queued_posts.length ? "healthy" : "degraded";
    return live;
  }

  async function fetchOrchestrationData() {
    var accountId = getAccountId();
    var result = {
      live_state: emptyLiveState(),
      emerging_products: [],
      trending_products: [],
      content_pack: { captions: [], hashtags: [], hook_variations: [] },
      performance_tracking: { snapshots: [] },
      strategy_update: { weights: {} },
    };

    try {
      var resp = await fetch("/api/tiktok-insights?account_id=" + encodeURIComponent(accountId), {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      if (resp.ok) {
        var apiData = await resp.json();
        if (apiData && typeof apiData === "object") {
          result.live_state = apiData.live_state || result.live_state;
          result.emerging_products = apiData.emerging_products || [];
          result.trending_products = apiData.trending_products || [];
          result.content_pack = apiData.content_pack || result.content_pack;
        }
      }
    } catch (e) {}

    if (global.supabaseClient) {
      try {
        var liveFromDb = await fetchLiveStateFromSupabase(accountId);
        result.live_state = Object.assign({}, result.live_state, liveFromDb);
      } catch (e) {}

      try {
        var perfResp = await global.supabaseClient
          .from("content_performance")
          .select("content_id,performance_metrics,timestamp")
          .eq("account_id", accountId)
          .order("timestamp", { ascending: false })
          .limit(20);
        result.performance_tracking.snapshots = perfResp.data || [];
      } catch (e) {}

      try {
        var stratResp = await global.supabaseClient
          .from("content_strategy_weights")
          .select("weights_json,updated_at")
          .eq("account_id", accountId)
          .limit(1);
        if (stratResp.data && stratResp.data[0]) {
          result.strategy_update.weights = stratResp.data[0].weights_json || {};
          result.live_state.last_learning_update =
            result.live_state.last_learning_update || stratResp.data[0].updated_at;
        }
      } catch (e) {}
    }

    return result;
  }

  async function handleApproval(contentId, decision) {
    if (!contentId) return;
    try {
      var resp = await fetch("/api/tiktok-content-approval", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content_id: contentId, decision: decision }),
      });
      if (!resp.ok && global.supabaseClient) {
        var newStatus = decision === "approve" ? "approved" : "blocked";
        await global.supabaseClient.from("content_queue").update({ status: newStatus }).eq("id", contentId);
      }
    } catch (e) {
      if (global.supabaseClient) {
        try {
          var status = decision === "approve" ? "approved" : "blocked";
          await global.supabaseClient.from("content_queue").update({ status: status }).eq("id", contentId);
        } catch (e2) {}
      }
    }
    refreshTiktokOrchestrationDashboard();
  }

  var _refreshTimer = null;

  async function refreshTiktokOrchestrationDashboard() {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
    try {
      var data = await fetchOrchestrationData();
      renderDashboard(data);
    } catch (e) {
      renderDashboard({});
    }
  }

  function initTiktokOrchestrationDashboard() {
    if (!document.getElementById(MOUNT_ID)) return;
    refreshTiktokOrchestrationDashboard();
    if (_refreshTimer) clearInterval(_refreshTimer);
    _refreshTimer = setInterval(refreshTiktokOrchestrationDashboard, REFRESH_MS);
  }

  global.refreshTiktokOrchestrationDashboard = refreshTiktokOrchestrationDashboard;
  global.initTiktokOrchestrationDashboard = initTiktokOrchestrationDashboard;
})(typeof window !== "undefined" ? window : globalThis);
