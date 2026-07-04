/**
 * Commerce mode feature flag — optional monetisation layer.
 *
 * Core content system (trend → content → plan → insights) never depends on this module.
 * All commerce operations are fail-safe and return empty defaults on error.
 */
(function (global) {
  "use strict";

  var USER_COMMERCE_MODE = false;
  var COMMERCE_TABS = ["products", "shop", "inventory", "revenue"];

  function isCommerceMode() {
    return USER_COMMERCE_MODE === true;
  }

  function loadFromUser(user) {
    USER_COMMERCE_MODE = !!(user && user.user_metadata && user.user_metadata.commerce_mode);
    global.USER_COMMERCE_MODE = USER_COMMERCE_MODE;
  }

  function setCommerceMode(enabled) {
    USER_COMMERCE_MODE = !!enabled;
    global.USER_COMMERCE_MODE = USER_COMMERCE_MODE;
    applyCommerceUI();
    syncToSupabase();
    refreshLiveState();
    if (typeof global.trackEvent === "function") {
      global.trackEvent("commerce_mode_toggle", { enabled: USER_COMMERCE_MODE });
    }
  }

  function syncToSupabase() {
    try {
      if (global.supabaseClient && global.supabaseClient.auth) {
        global.supabaseClient.auth.updateUser({ data: { commerce_mode: USER_COMMERCE_MODE } }).catch(function () {});
      }
    } catch (e) {}
  }

  function toggleCommerceMode() {
    setCommerceMode(!USER_COMMERCE_MODE);
  }

  function isCommerceTab(tab) {
    return COMMERCE_TABS.indexOf(tab) !== -1;
  }

  function applyCommerceUI() {
    var enabled = isCommerceMode();
    var i;

    var tabBtns = document.querySelectorAll("[data-commerce-tab]");
    for (i = 0; i < tabBtns.length; i++) {
      tabBtns[i].style.display = enabled ? "" : "none";
    }

    var panels = document.querySelectorAll("[data-commerce-panel]");
    for (i = 0; i < panels.length; i++) {
      panels[i].style.display = enabled ? "" : "none";
    }

    var settingsToggle = document.getElementById("settingsCommerceToggle");
    if (settingsToggle) settingsToggle.checked = enabled;

    var settingsLabel = document.getElementById("settingsCommerceLabel");
    if (settingsLabel) {
      settingsLabel.textContent = enabled ? "Commerce mode ON" : "Commerce mode OFF";
      settingsLabel.style.color = enabled ? "var(--green)" : "var(--muted)";
    }

    updatePaywallFeatures();
    filterTutorialSteps();

    if (enabled) {
      mountCommerceModules();
    } else {
      unmountCommerceModules();
      redirectFromCommerceTab();
    }
  }

  function updatePaywallFeatures() {
    if (typeof global.adaptUIForMode !== "function") return;
    global.adaptUIForMode();
  }

  function filterTutorialSteps() {
    /* Tutorial filtering handled at runtime in startTutorial via getTutorialSteps */
  }

  function getTutorialSteps(allSteps) {
    if (!Array.isArray(allSteps)) return [];
    if (isCommerceMode()) return allSteps;
    return allSteps.filter(function (step) {
      return step.tab !== "products" && step.title !== "Products";
    });
  }

  function redirectFromCommerceTab() {
    var active = localStorage.getItem("patriot_active_tab");
    if (active && isCommerceTab(active)) {
      if (typeof global.switchTab === "function") global.switchTab("plan");
    }
  }

  function mountCommerceModules() {
    try {
      if (global.TikTokShopInventoryGate && typeof global.TikTokShopInventoryGate.init === "function") {
        global.TikTokShopInventoryGate.init();
      }
    } catch (e) {}
    try {
      if (global.CommerceDashboard && typeof global.CommerceDashboard.mount === "function") {
        global.CommerceDashboard.mount();
      }
    } catch (e) {}
    try {
      if (global.TiktokLiveStateClient && typeof global.TiktokLiveStateClient.mount === "function") {
        global.TiktokLiveStateClient.mount();
      }
    } catch (e) {}
  }

  function unmountCommerceModules() {
    try {
      if (global.TikTokShopInventoryGate && typeof global.TikTokShopInventoryGate.render === "function") {
        global.TikTokShopInventoryGate.render([]);
      }
    } catch (e) {}
    try {
      if (global.CommerceDashboard && typeof global.CommerceDashboard.unmount === "function") {
        global.CommerceDashboard.unmount();
      }
    } catch (e) {}
    var gateMount = document.getElementById("tiktokShopInventoryGate");
    if (gateMount) gateMount.innerHTML = "";
  }

  function suggestProduct(keyword) {
    var kw = String(keyword || "").toLowerCase();
    if (kw.indexOf("army") !== -1) return "British Army history books";
    if (kw.indexOf("navy") !== -1) return "Royal Navy books and gifts";
    if (kw.indexOf("skincare") !== -1 || kw.indexOf("beauty") !== -1) return "Trending skincare products";
    if (kw.indexOf("fitness") !== -1 || kw.indexOf("gym") !== -1) return "Fitness and workout gear";
    if (kw.indexOf("food") !== -1 || kw.indexOf("recipe") !== -1) return "Kitchen and cooking products";
    return "";
  }

  function detectProducts(results) {
    if (!Array.isArray(results)) return [];
    var products = [];
    var seen = {};
    for (var i = 0; i < results.length; i++) {
      var item = results[i];
      if (!item || !item.keyword) continue;
      var name = (item.product && String(item.product).trim()) || suggestProduct(item.keyword);
      if (!name) continue;
      var key = name.toLowerCase();
      if (seen[key]) continue;
      seen[key] = true;
      products.push({
        name: name,
        keyword: item.keyword,
        signal_strength: Number(item.viral_score || 0),
        price: item.product_price || null,
        commission: item.product_commission || null,
        source: "product_detection",
      });
    }
    return products;
  }

  /**
   * Optional commerce add-on pipeline.
   * product detection → match → attach → queue enhancement
   */
  function runCommercePipeline(results) {
    var empty = { products: [], productTrends: [], inventory_gaps: [], attachments: [], queue_enhancements: [], revenue_suggestions: [] };
    if (!isCommerceMode()) return empty;

    try {
      var products = detectProducts(results);
      var inventoryGaps = [];
      var attachments = [];

      if (global.TikTokShopInventoryGate && typeof global.TikTokShopInventoryGate.processTrendResults === "function") {
        var gateResult = global.TikTokShopInventoryGate.processTrendResults(results) || {};
        inventoryGaps = gateResult.inventory_gaps || gateResult.gaps || [];
        attachments = gateResult.attachments || [];
      }

      var revenueSuggestions = products.slice(0, 5).map(function (p) {
        return {
          product: p.name,
          keyword: p.keyword,
          action: "Pin product link in video comments",
          expected_outcome: "Commission on viewer purchases",
        };
      });

      return {
        products: products,
        productTrends: products,
        inventory_gaps: inventoryGaps,
        attachments: attachments,
        queue_enhancements: attachments.filter(function (a) { return a && a.status === "attached"; }),
        revenue_suggestions: revenueSuggestions,
      };
    } catch (e) {
      return empty;
    }
  }

  function enrichResultsWithProducts(results, commerceResult) {
    if (!isCommerceMode() || !Array.isArray(results)) return results;
    var productMap = {};
    var products = (commerceResult && commerceResult.products) || [];
    for (var i = 0; i < products.length; i++) {
      if (products[i] && products[i].keyword) {
        productMap[String(products[i].keyword).toLowerCase()] = products[i].name;
      }
    }
    return results.map(function (r) {
      var copy = Object.assign({}, r);
      if (!copy.product && productMap[String(copy.keyword || "").toLowerCase()]) {
        copy.product = productMap[String(copy.keyword).toLowerCase()];
      }
      return copy;
    });
  }

  function buildLiveStateFeatures() {
    return { commerce_mode: isCommerceMode() };
  }

  function mergeLiveStateFeatures(state) {
    var s = state && typeof state === "object" ? state : {};
    s.features = buildLiveStateFeatures();
    return s;
  }

  function refreshLiveState() {
    try {
      if (global.TiktokLiveStateClient && typeof global.TiktokLiveStateClient.refresh === "function") {
        global.TiktokLiveStateClient.refresh();
      }
    } catch (e) {}
  }

  function guardTabSwitch(tab) {
    if (isCommerceTab(tab) && !isCommerceMode()) return "plan";
    return tab;
  }

  function shouldShowProductCTA() {
    return isCommerceMode();
  }

  function shouldShowProductInOpportunity(item) {
    return isCommerceMode() && item && item.product;
  }

  function shouldRecommendProductPost(item) {
    if (!isCommerceMode()) return false;
    if (!item) return false;
    return item.category === "product" || !!(item.product && String(item.product).trim());
  }

  global.CommerceMode = {
    isCommerceMode: isCommerceMode,
    loadFromUser: loadFromUser,
    setCommerceMode: setCommerceMode,
    toggleCommerceMode: toggleCommerceMode,
    applyCommerceUI: applyCommerceUI,
    runCommercePipeline: runCommercePipeline,
    enrichResultsWithProducts: enrichResultsWithProducts,
    buildLiveStateFeatures: buildLiveStateFeatures,
    mergeLiveStateFeatures: mergeLiveStateFeatures,
    refreshLiveState: refreshLiveState,
    guardTabSwitch: guardTabSwitch,
    isCommerceTab: isCommerceTab,
    getTutorialSteps: getTutorialSteps,
    shouldShowProductCTA: shouldShowProductCTA,
    shouldShowProductInOpportunity: shouldShowProductInOpportunity,
    shouldRecommendProductPost: shouldRecommendProductPost,
    detectProducts: detectProducts,
  };

  global.USER_COMMERCE_MODE = USER_COMMERCE_MODE;
})(typeof window !== "undefined" ? window : global);
