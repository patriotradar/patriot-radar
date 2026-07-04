/**
 * Live state → existing dashboard section bridge.
 * Injects /api/tiktok-live-state data into existing pages only.
 * Does not change navigation, layout, tabs, or routing.
 */
(function (global) {
  "use strict";

  var INJECT_ATTR = "data-live-state-inject";
  var _lastStateKey = "";

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function asList(value) {
    return Array.isArray(value) ? value : [];
  }

  function asDict(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function normalizeKey(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  function trendToResult(trend) {
    if (!trend || typeof trend !== "object") return null;
    var summary = String(trend.summary || trend.id || "").trim();
    if (!summary) return null;
    var virality = Number(trend.virality_score || 0);
    var signal = Number(trend.signal_strength || 0);
    var viralScore = virality > 1 ? virality : signal > 1 ? signal * 100 : Math.max(virality, signal) * 100;
    return {
      keyword: summary,
      viral_score: Math.min(100, Math.max(0, viralScore || 35)),
      rise_percent: Math.round((signal || virality || 0.35) * 40),
      search_volume: Math.round((signal || 0.5) * 80),
      source: "TikTok Intelligence",
      content_score: Math.round((virality || signal || 0.4) * 100),
      fresh: 60,
      emotion: 45,
      debate: 35,
      product: "",
      latest_score: Math.round(viralScore || 35),
      _live_state: true,
    };
  }

  function productToResult(product) {
    if (!product || typeof product !== "object") return null;
    var name = String(product.name || product.product_name || "").trim();
    if (!name) return null;
    var strength = Number(product.signal_strength || product.confidence || 0);
    return {
      keyword: name,
      viral_score: Math.min(100, Math.max(25, strength > 1 ? strength : strength * 100)),
      rise_percent: Math.round(strength * 30),
      search_volume: Math.round(strength * 70),
      source: product.source === "emerging" ? "Emerging Product" : "Trending Product",
      content_score: Math.round((product.confidence || strength || 0.4) * 100),
      product: name,
      _live_state_product: true,
    };
  }

  function productToEmerging(product) {
    if (!product || typeof product !== "object") return null;
    var name = String(product.name || product.product_name || "").trim();
    if (!name) return null;
    var strength = Number(product.signal_strength || product.confidence || 0);
    return {
      keyword: name,
      discovery_type: "autocomplete",
      viral_score: Math.min(100, Math.max(20, strength > 1 ? strength : strength * 100)),
      rise_percent: Math.round(strength * 25),
      source_keyword: product.source === "emerging" ? "Emerging Product Intel" : "Trending Product Intel",
      description: "Product signal from live state pipeline",
      _live_state_product: true,
    };
  }

  function mergeByKeyword(existing, incoming) {
    var merged = (existing || []).slice();
    var seen = {};
    for (var i = 0; i < merged.length; i++) {
      seen[normalizeKey(merged[i].keyword)] = true;
    }
    for (var j = 0; j < (incoming || []).length; j++) {
      var item = incoming[j];
      if (!item) continue;
      var key = normalizeKey(item.keyword);
      if (!key || seen[key]) continue;
      seen[key] = true;
      merged.push(item);
    }
    return merged;
  }

  function upsertInjectedBlock(containerId, blockId, html) {
    if (!html) return;
    var container = document.getElementById(containerId);
    if (!container) return;
    var existing = container.querySelector("#" + blockId);
    if (existing) {
      existing.outerHTML = html;
      return;
    }
    container.insertAdjacentHTML("beforeend", html);
  }

  function injectTrends(state) {
    var trends = asList(state.trends);
    if (!trends.length) return;

    var converted = [];
    for (var i = 0; i < trends.length; i++) {
      var row = trendToResult(trends[i]);
      if (row) converted.push(row);
    }
    if (!converted.length) return;

    if (typeof global.cachedResults !== "undefined") {
      global.cachedResults = mergeByKeyword(global.cachedResults, converted);
    } else {
      global.cachedResults = converted.slice();
    }

    var results = global.cachedResults || converted;
    var emerging = typeof global.cachedEmerging !== "undefined" ? global.cachedEmerging : [];

    if (typeof global.renderOpportunities === "function") {
      var topEl = document.getElementById("topOpportunities");
      if (topEl) topEl.innerHTML = global.renderOpportunities(results);
    }
    if (typeof global.renderFeed === "function") {
      var feedEl = document.getElementById("intelligenceFeed");
      if (feedEl) feedEl.innerHTML = global.renderFeed(results);
    }
    if (typeof global.renderThemes === "function") {
      var themeEl = document.getElementById("themeAnalysis");
      if (themeEl) themeEl.innerHTML = global.renderThemes(results);
    }
    if (typeof global.renderLiveFeed === "function") {
      var liveEl = document.getElementById("liveFeed");
      if (liveEl) liveEl.innerHTML = global.renderLiveFeed(results, emerging);
    }
    if (typeof global.renderPlatformOptimizer === "function") {
      var platEl = document.getElementById("platformOptimizer");
      if (platEl) platEl.innerHTML = global.renderPlatformOptimizer(results);
    }
    if (typeof global.renderPersonalIntelligence === "function") {
      global.renderPersonalIntelligence(results);
    }
    if (typeof global.renderDailyPlan === "function" && results.length >= 3) {
      var planEl = document.getElementById("dailyPlan");
      if (planEl) planEl.innerHTML = global.renderDailyPlan(results, emerging);
    }
    if (typeof global.renderPrimary === "function" && results.length) {
      var primaryEl = document.getElementById("primaryTarget");
      if (primaryEl) primaryEl.innerHTML = global.renderPrimary(results[0]);
    }
  }

  function injectDiscover(state) {
    var products = asList(state.products);
    if (!products.length) return;

    var productResults = [];
    var emergingItems = [];
    for (var i = 0; i < products.length; i++) {
      var pr = productToResult(products[i]);
      var em = productToEmerging(products[i]);
      if (pr) productResults.push(pr);
      if (em) emergingItems.push(em);
    }
    if (!productResults.length && !emergingItems.length) return;

    if (emergingItems.length && typeof global.renderEmerging === "function") {
      var emergingEl = document.getElementById("emergingTopics");
      if (emergingEl) {
        var currentEmerging = emergingItems;
        if (typeof global.cachedEmerging !== "undefined" && global.cachedEmerging.length) {
          currentEmerging = mergeByKeyword(global.cachedEmerging, emergingItems);
        }
        global.cachedEmerging = currentEmerging;
        var rendered = global.renderEmerging(currentEmerging);
        if (rendered) emergingEl.innerHTML = rendered;
      }
    }

    if (productResults.length && typeof global.renderCreatorInsights === "function") {
      var creatorEl = document.getElementById("creatorInsights");
      if (creatorEl) {
        var insights = productResults.map(function (p) {
          return { keyword: "Product trend: " + p.keyword };
        });
        var block =
          '<div id="liveStateDiscoverProducts" ' +
          INJECT_ATTR +
          '="products">' +
          global.renderCreatorInsights(insights) +
          "</div>";
        upsertInjectedBlock("creatorInsights", "liveStateDiscoverProducts", block);
      }
    }

    if (productResults.length && typeof global.renderLiveFeed === "function") {
      var liveFeedEl = document.getElementById("liveFeed");
      if (liveFeedEl) {
        var baseResults = global.cachedResults && global.cachedResults.length ? global.cachedResults : productResults;
        liveFeedEl.innerHTML = global.renderLiveFeed(mergeByKeyword(baseResults, productResults), global.cachedEmerging || []);
      }
    }
  }

  function injectPlan(state) {
    var gaps = asList(state.inventory_gaps);
    var prevention = asList(state.inventory_prevention);
    var queue = asList(state.content_queue);
    var approvals = asList(state.approvals);

    if (gaps.length && global.TikTokShopInventoryGate && typeof global.TikTokShopInventoryGate.render === "function") {
      var gateGaps = gaps.map(function (g) {
        return {
          content_id: g.content_id,
          product_name: g.product_name,
          category: g.category || "general",
          message: g.message || "Inventory gap detected",
          status: g.status || "waiting_user_action",
        };
      });
      global.TikTokShopInventoryGate.render(gateGaps, []);
    }

    if (prevention.length && global.TikTokInventoryPredictor && typeof global.TikTokInventoryPredictor.render === "function") {
      var mustAdd = [];
      var events = [];
      for (var i = 0; i < prevention.length; i++) {
        var item = prevention[i];
        if (item.available === false) {
          mustAdd.push({
            product_name: item.product_name,
            category: item.category || "general",
            demand_score: Number(item.demand_score || 0.6),
            priority: item.priority || "medium",
            expected_revenue_score: Math.round(Number(item.demand_score || 0.5) * 100),
            message: item.message || "Add product to catalog before content generation",
          });
        }
        events.push({
          product_name: item.product_name,
          category: item.category || "general",
          demand_score: Number(item.demand_score || 0.5),
          priority: item.priority || "medium",
          message: item.message || "Inventory prevention event",
        });
      }
      if (mustAdd.length || events.length) {
        global.TikTokInventoryPredictor.render({
          must_add_products: mustAdd,
          inventory_prevention_events: events,
          ready_count: 0,
          pre_add_required_count: events.length,
        });
      }
    }

    if (!queue.length && !approvals.length) return;

    var items = queue.length ? queue : approvals;
    var rows = "";
    for (var q = 0; q < Math.min(items.length, 5); q++) {
      var entry = items[q];
      var label = esc(entry.caption || entry.product_name || entry.hook || "Queued content");
      var status = esc(entry.status || "queued");
      rows +=
        '<div style="padding:8px 10px;background:rgba(0,255,136,.04);border:1px solid rgba(0,255,136,.12);border-radius:8px;margin-bottom:6px">' +
        '<div style="font-size:12px;font-weight:700">' +
        label +
        "</div>" +
        '<div style="font-size:10px;color:var(--muted);margin-top:2px">Status: ' +
        status +
        "</div></div>";
    }

    var html =
      '<div id="liveStateContentQueue" ' +
      INJECT_ATTR +
      '="queue" class="card" style="border-color:rgba(0,255,136,.25);margin-bottom:12px">' +
      '<div class="card-header"><h2 style="color:var(--green)">Content Pipeline</h2></div>' +
      '<p style="font-size:11px;color:var(--muted);margin-bottom:10px">From live state content queue</p>' +
      rows +
      "</div>";
    upsertInjectedBlock("contentFunnel", "liveStateContentQueue", html);
  }

  function injectMyStats(state) {
    var performance = asDict(state.performance);
    var prediction = asDict(state.prediction);
    var hasPerf = performance.snapshot_count > 0 || performance.total_views > 0;
    var hasPred = prediction.snapshot_count > 0 || (prediction.calibration && prediction.calibration.calibrated_at);

    if (!hasPerf && !hasPred) return;

    var html = '<div id="liveStateMyStats" ' + INJECT_ATTR + '="stats" class="pi-card" style="margin-top:12px">';
    html += "<h3>&#128202; Backend Analytics</h3>";
    html += '<p style="font-size:11px;color:var(--muted);margin-bottom:10px">Live pipeline metrics from /api/tiktok-live-state</p>';

    if (hasPerf) {
      html += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:10px">';
      html +=
        '<div style="padding:10px;background:var(--panel2);border-radius:8px;text-align:center"><div style="font-size:16px;font-weight:900;color:var(--green)">' +
        Number(performance.total_views || 0).toLocaleString() +
        '</div><div style="font-size:9px;color:var(--muted)">Tracked Views</div></div>';
      html +=
        '<div style="padding:10px;background:var(--panel2);border-radius:8px;text-align:center"><div style="font-size:16px;font-weight:900;color:var(--green)">' +
        Number(performance.snapshot_count || 0) +
        '</div><div style="font-size:9px;color:var(--muted)">Snapshots</div></div>';
      html +=
        '<div style="padding:10px;background:var(--panel2);border-radius:8px;text-align:center"><div style="font-size:16px;font-weight:900;color:var(--purple)">' +
        Number(performance.avg_engagement_rate || 0).toFixed(2) +
        '%</div><div style="font-size:9px;color:var(--muted)">Avg Engagement</div></div>';
      html += "</div>";
    }

    if (hasPred) {
      var cal = asDict(prediction.calibration);
      html += '<div style="font-size:11px;font-weight:700;color:var(--purple);margin-bottom:6px">Virality Predictions</div>';
      if (cal.calibrated_at) {
        html +=
          '<div style="font-size:11px;color:var(--muted);margin-bottom:6px">Model calibrated: ' +
          esc(String(cal.calibrated_at).slice(0, 19)) +
          (cal.accuracy_after != null ? " · Accuracy " + Number(cal.accuracy_after).toFixed(1) + "%" : "") +
          "</div>";
      }
      var tops = asList(prediction.top_predictions);
      for (var t = 0; t < Math.min(tops.length, 3); t++) {
        var pred = tops[t];
        html +=
          '<div style="padding:6px 8px;border-bottom:1px solid var(--border);font-size:11px"><span style="color:var(--muted)">Video ' +
          esc(pred.video_id || "—") +
          '</span> · Score <strong style="color:var(--green)">' +
          Number(pred.virality_score || 0).toFixed(1) +
          "</strong></div>";
      }
    }

    html += "</div>";
    upsertInjectedBlock("personalIntelligence", "liveStateMyStats", html);
  }

  function buildLiveStateAiContext(state) {
    if (!state || typeof state !== "object") return "";
    var ctx = "\n\nLIVE STATE (backend pipeline):";
    var flow = asDict(state.today_flow);
    if (flow.next_action && flow.next_action !== "unknown") {
      ctx += "\n- Next action: " + flow.next_action + " (status: " + (flow.status || "unknown") + ")";
    }

    var trends = asList(state.trends);
    if (trends.length) {
      ctx += "\n- TikTok backend trends:";
      for (var i = 0; i < Math.min(5, trends.length); i++) {
        ctx += "\n  · " + (trends[i].summary || trends[i].id || "trend") + " (signal:" + (trends[i].signal_strength || "?") + ")";
      }
    }

    var products = asList(state.products);
    if (products.length) {
      ctx += "\n- Product intelligence:";
      for (var p = 0; p < Math.min(5, products.length); p++) {
        ctx += "\n  · " + (products[p].name || "product") + " [" + (products[p].source || "signal") + "]";
      }
    }

    var queue = asList(state.content_queue);
    if (queue.length) {
      ctx += "\n- Content queue: " + queue.length + " item(s)";
    }
    var approvals = asList(state.approvals);
    if (approvals.length) {
      ctx += "\n- Pending approvals: " + approvals.length;
    }

    var perf = asDict(state.performance);
    if (perf.snapshot_count) {
      ctx += "\n- Tracked performance snapshots: " + perf.snapshot_count + ", total views " + (perf.total_views || 0);
    }

    var pred = asDict(state.prediction);
    if (pred.snapshot_count) {
      ctx += "\n- Virality predictions available: " + pred.snapshot_count + " snapshot(s)";
    }

    var gaps = asList(state.inventory_gaps);
    if (gaps.length) {
      ctx += "\n- Inventory gaps: " + gaps.map(function (g) { return g.product_name; }).join(", ");
    }

    return ctx;
  }

  function patchAiContext() {
    if (global._liveStateAiPatched) return;
    global._liveStateAiPatched = true;
    var original = global.buildCrossModuleContext;
    global.buildCrossModuleContext = function () {
      var ctx = typeof original === "function" ? original() : "";
      var state = global.TIKTOK_LIVE_STATE;
      if (!state && global.TiktokLiveState && typeof global.TiktokLiveState.getCached === "function") {
        state = global.TiktokLiveState.getCached();
      }
      return ctx + buildLiveStateAiContext(state);
    };
  }

  function injectAiQuickButtons(state) {
    var action = asDict(state.primary_action);
    if (!action.label || action.label === "unknown") return;
    var quickEl = document.getElementById("aiQuickBtns");
    if (!quickEl) return;
    if (quickEl.querySelector("[" + INJECT_ATTR + '="primary-action"]')) return;
    var btn =
      '<button type="button" ' +
      INJECT_ATTR +
      '="primary-action" onclick="TiktokLiveStateIntegration.runPrimaryAction()" style="font-size:10px;padding:4px 8px;border-radius:4px;border:1px solid var(--green);background:rgba(0,255,136,.08);color:var(--green);cursor:pointer">' +
      esc(action.label) +
      "</button>";
    quickEl.insertAdjacentHTML("afterbegin", btn);
  }

  function runPrimaryAction() {
    var state = global.TIKTOK_LIVE_STATE;
    if (!state && global.TiktokLiveState) state = global.TiktokLiveState.getCached();
    var action = state ? asDict(state.primary_action) : {};
    var code = String(action.action || "");
    if (code === "review_approval" || code === "view_queue" || code === "create_content") {
      if (typeof global.switchTab === "function") global.switchTab("plan");
    } else if (code === "fix_inventory") {
      if (typeof global.switchTab === "function") global.switchTab("plan");
    } else if (code === "match_products" || code === "run_trend_scan") {
      if (typeof global.switchTab === "function") global.switchTab("trends");
    } else if (typeof global.loadLiveStats === "function") {
      global.loadLiveStats();
    }
  }

  function wirePrimaryActionButton(state) {
    var btn = document.getElementById("tiktokLiveStatePrimaryBtn");
    if (!btn) return;
    btn.onclick = function () {
      runPrimaryAction();
    };
    var action = asDict(state.primary_action);
    if (action.label && action.label !== "unknown") {
      btn.textContent = action.label;
    }
  }

  function stateFingerprint(state) {
    try {
      return JSON.stringify({
        trends: (state.trends || []).length,
        products: (state.products || []).length,
        queue: (state.content_queue || []).length,
        approvals: (state.approvals || []).length,
        gaps: (state.inventory_gaps || []).length,
        prevention: (state.inventory_prevention || []).length,
        perf: (state.performance || {}).snapshot_count || 0,
        pred: (state.prediction || {}).snapshot_count || 0,
        action: (state.primary_action || {}).action || "",
      });
    } catch (e) {
      return String(Date.now());
    }
  }

  function apply(state) {
    if (!state || typeof state !== "object") return;

    var key = stateFingerprint(state);
    if (key === _lastStateKey) return;
    _lastStateKey = key;

    global.TIKTOK_LIVE_STATE = state;
    patchAiContext();

    try {
      injectTrends(state);
    } catch (e) {}
    try {
      injectDiscover(state);
    } catch (e) {}
    try {
      injectPlan(state);
    } catch (e) {}
    try {
      injectMyStats(state);
    } catch (e) {}
    try {
      injectAiQuickButtons(state);
    } catch (e) {}
    try {
      wirePrimaryActionButton(state);
    } catch (e) {}
  }

  function hookRenderAllSections() {
    if (global._liveStateRenderHooked || typeof global.renderAllSections !== "function") return;
    global._liveStateRenderHooked = true;
    var original = global.renderAllSections;
    global.renderAllSections = function (results, emerging, productTrends, creatorInsights) {
      original.apply(global, arguments);
      var state = global.TIKTOK_LIVE_STATE;
      if (!state && global.TiktokLiveState) state = global.TiktokLiveState.getCached();
      if (state) apply(state);
    };
  }

  function init() {
    hookRenderAllSections();
    patchAiContext();
  }

  global.TiktokLiveStateIntegration = {
    apply: apply,
    runPrimaryAction: runPrimaryAction,
    buildLiveStateAiContext: buildLiveStateAiContext,
    init: init,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof window !== "undefined" ? window : global);
