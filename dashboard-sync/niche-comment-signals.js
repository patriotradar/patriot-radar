/**
 * Niche Comment Signals — isolated dashboard section.
 * Does not modify or depend on existing TikTok trend intelligence UI logic.
 */
(function () {
  "use strict";

  var MOUNT_ID = "nicheCommentSignals";
  var TABLE = "niche_comment_signals_feed";
  var EMPTY_MSG =
    "No niche comment signals yet. Run sql/niche_comment_signals_feed.sql in Supabase, then scripts/run_niche_comment_signal_scan.py.";

  var cache = [];
  var initialized = false;

  function getClient() {
    if (typeof supabaseClient !== "undefined" && supabaseClient) return supabaseClient;
    if (typeof window.supabaseClient !== "undefined" && window.supabaseClient) return window.supabaseClient;
    return null;
  }

  function getSupabaseUrl() {
    if (typeof SUPABASE_URL !== "undefined") return SUPABASE_URL;
    var cfg = window.__SUPABASE_CONFIG__ || {};
    return cfg.url || "";
  }

  function formatTs(value) {
    if (!value) return "Unknown";
    try {
      var d = new Date(value);
      return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch (e) {
      return String(value);
    }
  }

  function signalBadge(state) {
    var colors = {
      high: { bg: "rgba(34,197,94,.15)", border: "rgba(34,197,94,.4)", color: "var(--green)", label: "High Signal" },
      moderate: { bg: "rgba(251,191,36,.15)", border: "rgba(251,191,36,.4)", color: "var(--amber)", label: "Moderate" },
      low: { bg: "rgba(148,163,184,.12)", border: "rgba(148,163,184,.3)", color: "var(--muted)", label: "Low Signal" },
    };
    var s = colors[state] || colors.low;
    return (
      '<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;' +
      "background:" + s.bg + ";border:1px solid " + s.border + ";color:" + s.color + '">' +
      s.label +
      "</span>"
    );
  }

  function metricBar(label, value, color) {
    var v = Math.min(100, Math.max(0, Number(value) || 0));
    return (
      '<div style="margin-bottom:8px">' +
      '<div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">' +
      '<span style="color:var(--muted)">' + label + "</span>" +
      '<span style="color:' + color + ';font-weight:600">' + v.toFixed(0) + "</span>" +
      "</div>" +
      '<div class="feed-bar" style="height:4px"><div class="feed-bar-fill" style="width:' +
      v +
      "%;background:" +
      color +
      '"></div></div></div>'
    );
  }

  function renderRows(rows) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var safe = Array.isArray(rows) ? rows.filter(function (r) { return r && typeof r === "object"; }) : [];

    if (!safe.length) {
      el.innerHTML =
        '<div class="card" style="border-color:rgba(99,102,241,.3)">' +
        '<div class="card-header"><h2 style="color:#818cf8">Niche Comment Signals</h2>' +
        '<div class="section-icon" style="background:rgba(99,102,241,.1);border-color:rgba(99,102,241,.3);color:#818cf8">&#128172;</div></div>' +
        '<p style="font-size:12px;color:var(--muted);padding:8px 0">' + EMPTY_MSG + "</p></div>";
      return;
    }

    var h =
      '<div class="card card-glow" style="border-color:rgba(99,102,241,.35)">' +
      '<div class="card-header"><h2 style="color:#818cf8">Niche Comment Signals</h2>' +
      '<div class="section-icon" style="background:rgba(99,102,241,.1);border-color:rgba(99,102,241,.3);color:#818cf8">&#128172;</div></div>' +
      '<p style="font-size:11px;color:var(--muted);margin-bottom:12px">Early virality weak-signals from TikTok comments — ' +
      safe.length +
      " videos · isolated from trend pipeline</p>";

    for (var i = 0; i < Math.min(safe.length, 30); i++) {
      var row = safe[i];
      var composite = Number(row.composite_signal || 0);
      var caption = row.caption_preview || row.summary || "Untitled video";
      var author = row.author || "unknown";
      var url = row.video_url || "";

      h += '<div class="feed-item" style="border-left:3px solid rgba(99,102,241,.5)">';
      h += '<div class="feed-header">';
      h += '<span class="feed-keyword">@' + author + "</span>";
      h += signalBadge(row.signal_state);
      h += "</div>";

      h += '<div style="font-size:12px;color:var(--white);margin:6px 0;line-height:1.4">' + caption + "</div>";

      if (row.summary) {
        h += '<div style="font-size:11px;color:var(--muted);margin-bottom:8px">' + row.summary + "</div>";
      }

      h += '<div class="feed-metrics" style="margin-bottom:10px">';
      h += '<div class="feed-metric"><div class="fm-label">Composite</div><div class="fm-value" style="color:#818cf8">' + composite.toFixed(0) + "</div></div>";
      h += '<div class="feed-metric"><div class="fm-label">Comments</div><div class="fm-value" style="color:var(--white)">' + (row.comment_count || 0) + "</div></div>";
      h += '<div class="feed-metric"><div class="fm-label">Analyzed</div><div class="fm-value" style="color:var(--white)">' + (row.comments_analyzed || 0) + "</div></div>";
      h += '<div class="feed-metric"><div class="fm-label">Updated</div><div class="fm-value" style="color:var(--muted);font-size:10px">' + formatTs(row.timestamp) + "</div></div>";
      h += "</div>";

      h += metricBar("Comment Velocity", row.comment_velocity, "#22d3ee");
      h += metricBar("Repetition Score", row.repetition_score, "#f472b6");
      h += metricBar("Curiosity / Confusion", row.curiosity_score, "#fbbf24");
      h += metricBar("Niche Relevance", row.niche_relevance_score, "#34d399");

      if (url) {
        h += '<div style="margin-top:8px"><a href="' + url + '" target="_blank" rel="noopener" style="font-size:10px;color:#818cf8">View video →</a></div>';
      }

      h += "</div>";
    }

    h += "</div>";
    el.innerHTML = h;
  }

  function describeError(error) {
    if (!error) return EMPTY_MSG;
    var code = error.code || "";
    var msg = error.message || String(error);
    if (code === "PGRST205" || msg.indexOf("Could not find the table") !== -1) {
      return "Supabase table niche_comment_signals_feed not found. Run sql/niche_comment_signals_feed.sql first.";
    }
    if (code === "42501" || /permission|policy|JWT/i.test(msg)) {
      return "Cannot read niche_comment_signals_feed — please log in or check Supabase RLS.";
    }
    return "Comment signals error: " + msg;
  }

  async function refreshNicheCommentSignals() {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var client = getClient();
    if (!client) {
      el.innerHTML =
        '<div class="card"><p style="font-size:12px;color:var(--muted);padding:12px 0">Waiting for Supabase client...</p></div>';
      return;
    }

    el.innerHTML =
      '<div class="card"><p style="font-size:12px;color:var(--muted);padding:12px 0">Loading niche comment signals...</p></div>';

    try {
      var session = await client.auth.getSession();
      if (!session.data || !session.data.session) {
        el.innerHTML =
          '<div class="card"><p style="font-size:12px;color:var(--muted);padding:12px 0">Login required to load niche comment signals.</p></div>';
        return;
      }

      var resp = await client
        .from(TABLE)
        .select("*")
        .eq("source", "tiktok_comments")
        .order("composite_signal", { ascending: false })
        .limit(100);

      if (resp.error) {
        el.innerHTML =
          '<div class="card"><p style="font-size:12px;color:var(--red);padding:12px 0">' +
          describeError(resp.error) +
          "</p></div>";
        return;
      }

      cache = resp.data || [];
      renderRows(cache);
    } catch (err) {
      el.innerHTML =
        '<div class="card"><p style="font-size:12px;color:var(--red);padding:12px 0">' +
        describeError(err) +
        "</p></div>";
    }
  }

  function isTrendsTabVisible() {
    var tab = document.getElementById("tab-trends");
    return tab && tab.classList.contains("active");
  }

  function hookTabObserver() {
    var tab = document.getElementById("tab-trends");
    if (!tab || typeof MutationObserver === "undefined") return;

    var observer = new MutationObserver(function () {
      if (isTrendsTabVisible()) refreshNicheCommentSignals();
    });
    observer.observe(tab, { attributes: true, attributeFilter: ["class"] });

    document.querySelectorAll(".tab-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var label = (btn.textContent || "").toLowerCase();
        if (label.indexOf("trend") !== -1) {
          setTimeout(refreshNicheCommentSignals, 150);
        }
      });
    });
  }

  function init() {
    if (initialized) return;
    initialized = true;

    if (!document.getElementById(MOUNT_ID)) return;

    hookTabObserver();

    if (isTrendsTabVisible()) {
      refreshNicheCommentSignals();
    } else {
      setTimeout(function () {
        if (getClient() && getSupabaseUrl()) refreshNicheCommentSignals();
      }, 2000);
    }
  }

  window.refreshNicheCommentSignals = refreshNicheCommentSignals;
  window.renderNicheCommentSignals = renderRows;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
