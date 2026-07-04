/**
 * Virality Intelligence System — additive dashboard extension.
 * Extends Early Virality Prediction with learning status, accuracy trends,
 * confidence evolution, and prediction explainability.
 * Does NOT modify existing UI components.
 */
(function () {
  "use strict";

  var MOUNT_ID = "viralityIntelligenceExtension";
  var TABLES = {
    calibration: "virality_calibration_logs",
    explanations: "virality_explanations",
    snapshots: "virality_snapshots"
  };

  var initialized = false;

  function getClient() {
    if (typeof supabaseClient !== "undefined" && supabaseClient) return supabaseClient;
    return null;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function confidenceColor(level) {
    if (level === "High") return "#22c55e";
    if (level === "Low") return "#ef4444";
    return "#fbbf24";
  }

  function renderSparkline(values, color) {
    if (!values || !values.length) {
      return '<div style="font-size:11px;color:var(--muted)">No trend data yet</div>';
    }
    var max = Math.max.apply(null, values.concat([1]));
    var w = 200;
    var h = 40;
    var step = w / Math.max(values.length - 1, 1);
    var points = [];
    for (var i = 0; i < values.length; i++) {
      var x = i * step;
      var y = h - (values[i] / max) * (h - 4) - 2;
      points.push(x.toFixed(1) + "," + y.toFixed(1));
    }
    return (
      '<svg width="' + w + '" height="' + h + '" style="display:block;margin-top:6px">' +
      '<polyline fill="none" stroke="' + color + '" stroke-width="2" points="' + points.join(" ") + '"/>' +
      '</svg>'
    );
  }

  function renderLearningStatus(calibration) {
    var latest = calibration[0] || {};
    var weights = latest.new_weights || {};
    var adjustments = latest.adjustments || {};
    var h = '<div style="padding:14px;background:var(--panel2);border:1px solid rgba(168,85,247,.3);border-radius:10px">';
    h += '<div style="font-size:10px;color:#a855f7;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Model Learning Status</div>';

    if (!latest.calibrated_at) {
      h += '<p style="font-size:12px;color:var(--muted)">Learning pipeline active — awaiting first calibration cycle. Run sql/virality_intelligence_tables.sql in Supabase.</p>';
    } else {
      h += '<div style="font-size:12px;color:var(--white);margin-bottom:8px">Last calibrated: <span style="color:#a855f7">' + escapeHtml(String(latest.calibrated_at).slice(0, 19)) + ' UTC</span></div>';
      h += '<div style="font-size:11px;color:var(--muted);margin-bottom:8px">Outcomes processed: ' + (latest.outcomes_processed || 0) + ' · Accuracy: ' + (latest.accuracy_after != null ? Number(latest.accuracy_after).toFixed(1) + '%' : '—') + '</div>';
      h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:6px">';
      var keys = Object.keys(weights);
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var adj = adjustments[k];
        var adjStr = adj != null && adj !== 0 ? (adj > 0 ? "+" : "") + (Number(adj) * 100).toFixed(1) + "%" : "—";
        h += '<div style="padding:8px;background:rgba(168,85,247,.08);border-radius:8px;text-align:center">';
        h += '<div style="font-size:10px;color:var(--muted);text-transform:capitalize">' + escapeHtml(k.replace("_", " ")) + '</div>';
        h += '<div style="font-size:14px;font-weight:800;color:#a855f7">' + Number(weights[k]).toFixed(2) + '</div>';
        h += '<div style="font-size:9px;color:' + (adj > 0 ? "#22c55e" : adj < 0 ? "#ef4444" : "var(--muted)") + '">' + adjStr + '</div>';
        h += '</div>';
      }
      h += '</div>';
    }
    h += '</div>';
    return h;
  }

  function renderAccuracyChart(calibration) {
    var sorted = calibration.slice().reverse();
    var values = [];
    for (var i = 0; i < sorted.length; i++) {
      if (sorted[i].accuracy_after != null) values.push(Number(sorted[i].accuracy_after));
    }
    var h = '<div style="padding:14px;background:var(--panel2);border:1px solid rgba(34,197,94,.3);border-radius:10px">';
    h += '<div style="font-size:10px;color:#22c55e;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Prediction Accuracy Over Time</div>';
    h += renderSparkline(values, "#22c55e");
    if (values.length) {
      h += '<div style="font-size:10px;color:var(--muted);margin-top:4px">Latest: ' + values[values.length - 1].toFixed(1) + '% · ' + values.length + ' cycles</div>';
    }
    h += '</div>';
    return h;
  }

  function renderConfidenceChart(explanations) {
    var values = [];
    for (var i = 0; i < explanations.length; i++) {
      values.push(Number(explanations[i].confidence_score || 50));
    }
    values.reverse();
    var h = '<div style="padding:14px;background:var(--panel2);border:1px solid rgba(251,191,36,.3);border-radius:10px">';
    h += '<div style="font-size:10px;color:#fbbf24;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Confidence Evolution</div>';
    h += renderSparkline(values.slice(-20), "#fbbf24");
    if (values.length) {
      var avg = values.reduce(function (a, b) { return a + b; }, 0) / values.length;
      h += '<div style="font-size:10px;color:var(--muted);margin-top:4px">Avg confidence: ' + avg.toFixed(1) + '% · ' + values.length + ' predictions</div>';
    }
    h += '</div>';
    return h;
  }

  function renderExplanationBreakdown(explanations) {
    var h = '<div style="margin-top:12px">';
    h += '<div style="font-size:10px;color:#a855f7;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Why This Was Predicted</div>';

    if (!explanations.length) {
      h += '<p style="font-size:12px;color:var(--muted)">No explanations stored yet. The learning pipeline generates these automatically.</p>';
      h += '</div>';
      return h;
    }

    for (var i = 0; i < Math.min(explanations.length, 8); i++) {
      var row = explanations[i];
      var expl = row.explanation || {};
      var conf = row.confidence_level || (expl.confidence && expl.confidence.level) || "Medium";
      var confScore = row.confidence_score || (expl.confidence && expl.confidence.score) || 50;

      h += '<div class="feed-item" style="border-left:3px solid #a855f7;padding:10px;margin-bottom:8px">';
      h += '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">';
      h += '<span style="font-size:12px;color:var(--white)">Video ' + escapeHtml(String(row.video_id).slice(0, 16)) + '</span>';
      h += '<span class="tag" style="border-color:rgba(168,85,247,.4);color:#a855f7">Score ' + Number(row.virality_score || 0).toFixed(0) + '</span>';
      h += '<span class="tag" style="border-color:' + confidenceColor(conf) + '44;color:' + confidenceColor(conf) + '">' + escapeHtml(conf) + ' (' + Number(confScore).toFixed(0) + '%)</span>';
      h += '</div>';

      if (expl.summary) {
        h += '<div style="font-size:11px;color:var(--muted);margin:6px 0">' + escapeHtml(expl.summary) + '</div>';
      }

      if (expl.top_contributors && expl.top_contributors.length) {
        h += '<div style="font-size:10px;color:#22c55e;margin-top:4px">';
        for (var j = 0; j < expl.top_contributors.length; j++) {
          h += '<div>• ' + escapeHtml(expl.top_contributors[j]) + '</div>';
        }
        h += '</div>';
      }

      if (expl.negative_factors && expl.negative_factors.length) {
        h += '<div style="font-size:10px;color:#ef4444;margin-top:4px">';
        for (var n = 0; n < Math.min(expl.negative_factors.length, 2); n++) {
          h += '<div>• ' + escapeHtml(expl.negative_factors[n]) + '</div>';
        }
        h += '</div>';
      }

      h += '</div>';
    }
    h += '</div>';
    return h;
  }

  function renderDashboard(calibration, explanations) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var h = '<div class="card" style="border-color:rgba(168,85,247,.3);margin-top:16px">';
    h += '<div class="card-header"><h2 style="color:#a855f7">Virality Intelligence</h2>';
    h += '<div class="section-icon" style="background:rgba(168,85,247,.1);border-color:rgba(168,85,247,.3);color:#a855f7">&#129504;</div></div>';
    h += '<p style="font-size:11px;color:var(--muted);margin-bottom:12px">Self-improving explainable layer — automatic learning from engagement outcomes</p>';

    h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:12px">';
    h += renderLearningStatus(calibration);
    h += renderAccuracyChart(calibration);
    h += renderConfidenceChart(explanations);
    h += '</div>';

    h += renderExplanationBreakdown(explanations);
    h += '</div>';
    el.innerHTML = h;
  }

  function renderShell(message, isError) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
    el.innerHTML =
      '<div class="card" style="border-color:rgba(168,85,247,.3);margin-top:16px">' +
      '<div class="card-header"><h2 style="color:#a855f7">Virality Intelligence</h2>' +
      '<div class="section-icon" style="background:rgba(168,85,247,.1);border-color:rgba(168,85,247,.3);color:#a855f7">&#129504;</div></div>' +
      '<p style="font-size:12px;color:' + (isError ? "var(--red)" : "var(--muted)") + ';padding:8px 0">' + message + '</p></div>';
  }

  async function refreshViralityIntelligence() {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    if (!window.TikTokLiveState) {
      renderShell("Waiting for live state client...");
      return;
    }

    renderShell("Loading virality intelligence data...");

    try {
      var client = getClient();
      if (client) {
        var session = await client.auth.getSession();
        if (!session.data || !session.data.session) {
          renderShell("Login required for virality intelligence analytics.");
          return;
        }
      }

      var niche = (typeof USER_NICHE !== "undefined" && USER_NICHE) ? USER_NICHE : "general";
      var liveState = await window.TikTokLiveState.fetch(niche);
      var virality = (liveState && liveState.virality) || {};
      var calibration = virality.calibration || [];
      var explanations = virality.explanations || [];

      if (liveState && liveState.errors && liveState.errors.length && !calibration.length && !explanations.length) {
        var errMsg = liveState.errors[0] || "";
        if (errMsg.indexOf("PGRST205") !== -1 || errMsg.indexOf("not found") !== -1) {
          renderShell("Virality intelligence tables not found. Run sql/virality_intelligence_tables.sql in Supabase.");
          return;
        }
      }

      renderDashboard(calibration, explanations);
    } catch (err) {
      renderShell("Virality intelligence error: " + (err.message || String(err)), true);
    }
  }

  function isTrendsTabVisible() {
    var tab = document.getElementById("tab-tiktok");
    return tab && tab.classList.contains("active");
  }

  function hookTabObserver() {
    var tab = document.getElementById("tab-tiktok");
    if (!tab || typeof MutationObserver === "undefined") return;
    var observer = new MutationObserver(function () {
      if (isTrendsTabVisible()) refreshViralityIntelligence();
    });
    observer.observe(tab, { attributes: true, attributeFilter: ["class"] });
  }

  function init() {
    if (initialized) return;
    initialized = true;
    if (!document.getElementById(MOUNT_ID)) return;
    hookTabObserver();
    if (isTrendsTabVisible()) {
      refreshViralityIntelligence();
    } else {
      setTimeout(function () {
        if (getClient()) refreshViralityIntelligence();
      }, 3000);
    }
  }

  window.refreshViralityIntelligence = refreshViralityIntelligence;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
