/**
 * TikTok Shop Content Mode Resolver — client-side mirror (Step 2).
 *
 * Predictive layer owns intent; this module resolves content_mode for generation.
 * Reactive gate NEVER overrides the resolved mode.
 */
(function () {
  "use strict";

  var HIGH_DEMAND = 0.7;
  var GENERIC_FALLBACK = "generic";

  function normalizeName(value) {
    return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
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
    return "general";
  }

  function findCategorySubstitute(productName, catalog) {
    var availability = checkAvailability(productName, catalog);
    if (availability.attachable && availability.match_type === "category") {
      return {
        product_name: availability.matched_name || productName,
        product_id: availability.product_id,
        category: availability.category,
        substitution_type: "category"
      };
    }
    return null;
  }

  function genericFallbackMode(productName) {
    return {
      mode: GENERIC_FALLBACK,
      product_name: productName || "",
      product_id: null,
      pause_product_attachment: true,
      fallback_reason: "resolver_fail_safe",
      resolved_by: "content_mode_resolver"
    };
  }

  function resolveContentMode(productName, demandScore, availability, catalog) {
    productName = String(productName || "").trim();
    demandScore = Number(demandScore || 0);
    catalog = catalog || [];

    try {
      var avail = availability || checkAvailability(productName, catalog);

      if (avail.attachable && avail.match_type === "exact") {
        return {
          mode: "product_specific",
          product_name: avail.matched_name || productName,
          product_id: avail.product_id,
          demand_score: demandScore,
          pause_product_attachment: false,
          resolved_by: "content_mode_resolver"
        };
      }

      if (demandScore >= HIGH_DEMAND) {
        return {
          mode: "generic_high_priority",
          product_name: productName,
          product_id: null,
          demand_score: demandScore,
          pause_product_attachment: true,
          high_priority: true,
          fallback_reason: "high_demand_missing_product",
          resolved_by: "content_mode_resolver"
        };
      }

      var substitute = findCategorySubstitute(productName, catalog);
      if (substitute) {
        return {
          mode: "category_substitute",
          product_name: substitute.product_name,
          product_id: substitute.product_id,
          original_product_name: productName,
          substitution_type: substitute.substitution_type,
          demand_score: demandScore,
          pause_product_attachment: false,
          resolved_by: "content_mode_resolver"
        };
      }

      return {
        mode: "category_substitute",
        product_name: productName,
        product_id: null,
        category: inferCategory(productName),
        demand_score: demandScore,
        pause_product_attachment: false,
        substitution_type: "category_framing_only",
        resolved_by: "content_mode_resolver"
      };
    } catch (e) {
      return genericFallbackMode(productName);
    }
  }

  function modeAllowsAttachment(contentMode) {
    if (!contentMode) return false;
    var mode = contentMode.mode || GENERIC_FALLBACK;
    if (mode === GENERIC_FALLBACK || mode === "generic_high_priority") return false;
    if (contentMode.pause_product_attachment) return false;
    return true;
  }

  window.TikTokContentModeResolver = {
    HIGH_DEMAND_THRESHOLD: HIGH_DEMAND,
    GENERIC_FALLBACK_MODE: GENERIC_FALLBACK,
    resolveContentMode: resolveContentMode,
    genericFallbackMode: genericFallbackMode,
    modeAllowsAttachment: modeAllowsAttachment,
    findCategorySubstitute: findCategorySubstitute
  };
})();
