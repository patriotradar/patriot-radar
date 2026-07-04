/**
 * TikTok Shop Predictive Inventory Intelligence — INTENT DECISION layer (Step 1).
 *
 * Predicts likely-needed products BEFORE content generation.
 * ONLY influences decisions — NEVER attaches products.
 *
 * Dashboard panel: must_add_products, inventory_prevention_event
 * (visually separate from reactive inventory gate panel)
 */
(function () {
  "use strict";

  var MOUNT_ID = "tiktokInventoryPredictor";
  var HIGH_DEMAND = 0.7;
  var MEDIUM_DEMAND = 0.4;

  function normalizeName(value) {
    return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  function getCatalog() {
    if (window.TikTokShopInventoryGate && typeof window.TikTokShopInventoryGate.getCatalog === "function") {
      return window.TikTokShopInventoryGate.getCatalog();
    }
    try {
      var raw = localStorage.getItem("tiktok_shop_catalog");
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function checkAvailability(productName, catalog) {
    if (window.TikTokShopInventoryGate && typeof window.TikTokShopInventoryGate.checkProductAvailability === "function") {
      return window.TikTokShopInventoryGate.checkProductAvailability(productName, catalog);
    }
    return { status: "missing", attachable: false, category: "general" };
  }

  function inferCategory(productName) {
    if (window.TikTokShopInventoryGate && typeof window.TikTokShopInventoryGate.inferCategory === "function") {
      return window.TikTokShopInventoryGate.inferCategory(productName);
    }
    var lowered = normalizeName(productName);
    if (lowered.indexOf("army") !== -1 || lowered.indexOf("military") !== -1) return "military";
    if (lowered.indexOf("flag") !== -1) return "flags";
    if (lowered.indexOf("royal") !== -1) return "royal";
    return "general";
  }

  function resolveContentMode(productName, demandScore, availability, catalog) {
    if (window.TikTokContentModeResolver && typeof window.TikTokContentModeResolver.resolveContentMode === "function") {
      return window.TikTokContentModeResolver.resolveContentMode(productName, demandScore, availability, catalog);
    }
    return { mode: "generic", product_name: productName, pause_product_attachment: true };
  }

  function suggestProductName(keyword) {
    if (typeof makeProduct === "function") return makeProduct(keyword);
    return keyword ? String(keyword) + " product" : "";
  }

  function resolveProductName(item) {
    return String(item.product_name || item.product || item.suggested_product || "").trim();
  }

  function iterTrendItems(trends) {
    if (!trends) return [];
    if (Array.isArray(trends)) return trends;
    var items = [];
    ["product_trends", "emerging", "results", "trending", "items"].forEach(function (key) {
      if (trends[key] && Array.isArray(trends[key])) {
        items = items.concat(trends[key]);
      }
    });
    return items;
  }

  function clamp(v, lo, hi) {
    return Math.max(lo || 0, Math.min(hi || 1, v));
  }

  function priorityFromDemand(score) {
    if (score > HIGH_DEMAND) return "high";
    if (score >= MEDIUM_DEMAND) return "medium";
    return "low";
  }

  function predictRequiredProducts(trends, niche, historicalContent) {
    niche = niche || "general";
    var trendItems = iterTrendItems(trends);
    var candidates = {};
    var histMap = {};

    (historicalContent || []).forEach(function (entry) {
      var name = normalizeName(resolveProductName(entry));
      if (!name) return;
      var views = Number(entry.views || entry.avg_views || 0);
      var likes = Number(entry.likes || entry.avg_likes || 0);
      var viral = Number(entry.viral_score || 0);
      var engagement = clamp((views / 10000) * 0.5 + (likes / 1000) * 0.3 + (viral / 100) * 0.2);
      histMap[name] = Math.max(histMap[name] || 0, engagement);
    });

    trendItems.forEach(function (item) {
      var productName = resolveProductName(item);
      if (!productName) {
        productName = suggestProductName(item.keyword || item.topic || "");
      }
      if (!productName) return;

      var key = normalizeName(productName);
      var viral = Number(item.viral_score || 0);
      var rise = Number(item.rise_percent || 0);
      var contentScore = Number(item.content_score || 0);
      var trendScore = clamp((viral / 100) * 0.4 + (Math.max(rise, 0) / 100) * 0.25 + (contentScore / 100) * 0.2);
      var histScore = histMap[key] || 0;
      var demandScore = clamp(trendScore * 0.65 + histScore * 0.35);

      var reasons = ["trend_match"];
      if (rise > 50 || viral >= 50) reasons.push("engagement_spike");
      if (histScore > 0.3) reasons.push("engagement_spike");
      if (niche && normalizeName(productName).indexOf(normalizeName(niche)) !== -1) {
        reasons.push("niche_alignment");
      }

      var confidence = clamp(0.35 + reasons.length * 0.15 + demandScore * 0.25);
      if (!candidates[key] || candidates[key].demand_score < demandScore) {
        candidates[key] = {
          product_name: productName,
          demand_score: Math.round(demandScore * 1000) / 1000,
          confidence: Math.round(confidence * 1000) / 1000,
          reason: reasons,
          category: inferCategory(productName)
        };
      }
    });

    var likely = Object.keys(candidates).map(function (k) { return candidates[k]; });
    likely.sort(function (a, b) {
      return b.demand_score - a.demand_score || b.confidence - a.confidence;
    });

    return {
      success: true,
      niche: niche,
      likely_needed_products: likely,
      prediction_count: likely.length
    };
  }

  function precheckCatalog(likelyNeeded, catalog) {
    return (likelyNeeded || []).map(function (product) {
      var availability = checkAvailability(product.product_name, catalog);
      var exactMatch = availability.attachable && availability.match_type === "exact";
      return {
        product_name: product.product_name,
        category: product.category,
        demand_score: product.demand_score,
        confidence: product.confidence,
        reason: product.reason,
        catalog_status: exactMatch ? "ready_to_attach" : "pre_add_required",
        availability: availability
      };
    });
  }

  function buildPreventionEvent(product, preCheck) {
    var demand = Number(preCheck.demand_score || product.demand_score || 0);
    var confidence = Number(preCheck.confidence || product.confidence || 0.5);
    return {
      product_name: preCheck.product_name || product.product_name,
      category: preCheck.category || product.category || "general",
      demand_score: demand,
      message: "Add this product to your TikTok Shop BEFORE posting content",
      priority: priorityFromDemand(demand),
      expected_revenue_score: Math.round((demand * confidence * 0.85 + demand * 0.15) * 1000) / 1000
    };
  }

  function runPredictiveIntelligence(trends, niche, historicalContent, catalog) {
    catalog = catalog || getCatalog();
    try {
      var prediction = predictRequiredProducts(trends, niche, historicalContent);
      var preChecks = precheckCatalog(prediction.likely_needed_products, catalog);
      var preventionEvents = [];
      var mustAdd = [];
      var ready = [];
      var contentModeSuggestions = [];

      preChecks.forEach(function (pc) {
        var contentMode = resolveContentMode(
          pc.product_name,
          pc.demand_score,
          pc.availability,
          catalog
        );
        contentModeSuggestions.push({
          product_name: pc.product_name,
          demand_score: pc.demand_score,
          content_mode: contentMode
        });

        if (pc.catalog_status === "ready_to_attach") {
          ready.push(Object.assign({}, pc, { content_mode: contentMode }));
        } else {
          var evt = buildPreventionEvent(pc, pc);
          preventionEvents.push(evt);
          if (pc.demand_score > HIGH_DEMAND) {
            mustAdd.push(Object.assign({}, evt, {
              catalog_status: "pre_add_required",
              suggest_immediate_add: true
            }));
          }
        }
      });

      mustAdd.sort(function (a, b) {
        return b.demand_score - a.demand_score || b.expected_revenue_score - a.expected_revenue_score;
      });

      return {
        success: true,
        layer: "predictive",
        niche: niche,
        likely_needed_products: prediction.likely_needed_products,
        pre_check_results: preChecks,
        content_mode_suggestions: contentModeSuggestions,
        inventory_prevention_events: preventionEvents,
        must_add_products: mustAdd,
        ready_products: ready,
        ready_count: ready.length,
        pre_add_required_count: preventionEvents.length,
        high_demand_gap_count: mustAdd.length
      };
    } catch (e) {
      return {
        success: false,
        layer: "predictive",
        likely_needed_products: [],
        content_mode_suggestions: [],
        inventory_prevention_events: [],
        must_add_products: [],
        ready_products: [],
        ready_count: 0,
        pre_add_required_count: 0,
        high_demand_gap_count: 0
      };
    }
  }

  function emitPreventionEvents(events) {
    if (!events || !events.length || typeof trackEvent !== "function") return;
    events.forEach(function (evt) {
      trackEvent("inventory_prevention_event", {
        inventory_prevention_event: evt,
        product_name: evt.product_name,
        category: evt.category,
        demand_score: evt.demand_score,
        priority: evt.priority,
        expected_revenue_score: evt.expected_revenue_score
      });
    });
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function priorityColor(priority) {
    if (priority === "high") return "#ff4757";
    if (priority === "medium") return "#fbbf24";
    return "var(--muted)";
  }

  function render(intelligence) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var mustAdd = (intelligence && intelligence.must_add_products) || [];
    var prevention = (intelligence && intelligence.inventory_prevention_events) || [];

    if (!mustAdd.length && !prevention.length) {
      el.innerHTML = "";
      return;
    }

    var h = '<div class="card" style="border-color:rgba(251,191,36,.35);margin-bottom:12px" data-panel="predictive-inventory">';
    h += '<div class="card-header"><h2>Predictive Inventory Panel</h2>';
    h += '<div class="section-icon" style="color:#fbbf24">&#9889;</div></div>';
    h += '<p style="font-size:11px;color:var(--muted);margin-bottom:10px">';
    h += '<strong style="color:#fbbf24">Intent layer</strong> — guides content strategy before generation. Does not attach products.';
    h += '</p>';

    if (mustAdd.length) {
      h += '<div style="font-size:10px;color:#fbbf24;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Must-Add Products</div>';
      for (var i = 0; i < mustAdd.length; i++) {
        var item = mustAdd[i];
        h += '<div style="padding:10px;background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.2);border-radius:10px;margin-bottom:8px">';
        h += '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">';
        h += '<div style="font-size:14px;font-weight:900">' + escapeHtml(item.product_name) + '</div>';
        h += '<span style="font-size:9px;font-weight:800;color:' + priorityColor(item.priority) + ';text-transform:uppercase">' + escapeHtml(item.priority) + '</span>';
        h += '</div>';
        h += '<div style="font-size:10px;color:var(--muted);margin-top:4px">Demand: ' + Math.round(item.demand_score * 100) + '% | Revenue score: ' + item.expected_revenue_score + '</div>';
        h += '<div style="font-size:11px;color:var(--white);margin-top:6px">' + escapeHtml(item.message) + '</div>';
        h += '</div>';
      }
    }

    if (prevention.length) {
      h += '<div style="font-size:10px;color:#fbbf24;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px">Inventory Prevention Events</div>';
      for (var j = 0; j < Math.min(prevention.length, 5); j++) {
        var p = prevention[j];
        h += '<div style="padding:8px 10px;background:rgba(251,191,36,.04);border:1px solid rgba(251,191,36,.15);border-radius:8px;margin-bottom:6px">';
        h += '<div style="font-size:13px;font-weight:700">' + escapeHtml(p.product_name) + '</div>';
        h += '<div style="font-size:10px;color:var(--muted);margin-top:2px">' + escapeHtml(p.message) + '</div>';
        h += '</div>';
      }
    }

    h += '<p style="font-size:9px;color:var(--muted);margin-top:8px;text-align:center">';
    h += (intelligence.ready_count || 0) + ' ready | ' + (intelligence.pre_add_required_count || 0) + ' need onboarding';
    h += '</p></div>';

    el.innerHTML = h;
  }

  function loadHistoricalContent() {
    try {
      var perf = typeof loadPerfData === "function" ? loadPerfData() : {};
      var historical = [];
      for (var kw in perf) {
        if (!perf.hasOwnProperty(kw)) continue;
        var entries = perf[kw];
        if (!entries || !entries.length) continue;
        var totalViews = 0;
        for (var i = 0; i < entries.length; i++) {
          totalViews += Number(entries[i].views || 0);
        }
        historical.push({
          keyword: kw,
          product_name: typeof makeProduct === "function" ? makeProduct(kw) : kw,
          views: totalViews,
          avg_views: Math.round(totalViews / entries.length)
        });
      }
      return historical;
    } catch (e) {
      return [];
    }
  }

  function processTrendResults(results, emerging, productTrends) {
    var trends = {
      results: results || [],
      emerging: emerging || [],
      product_trends: productTrends || []
    };
    var niche = (typeof USER_NICHE !== "undefined" && USER_NICHE) ? USER_NICHE : "general";
    var historical = loadHistoricalContent();
    var intelligence = runPredictiveIntelligence(trends, niche, historical);

    emitPreventionEvents(intelligence.inventory_prevention_events);
    render(intelligence);

    if (window.TikTokShopInventoryGate && typeof window.TikTokShopInventoryGate.processTrendResults === "function") {
      window.TikTokShopInventoryGate.processTrendResults(results, intelligence);
    }

    return intelligence;
  }

  function init() {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
  }

  window.TikTokInventoryPredictor = {
    predictRequiredProducts: predictRequiredProducts,
    precheckCatalog: precheckCatalog,
    runPredictiveIntelligence: runPredictiveIntelligence,
    processTrendResults: processTrendResults,
    render: render,
    init: init
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
