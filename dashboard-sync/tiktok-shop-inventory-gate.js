/**
 * TikTok Shop Reactive Inventory Gate — FINAL SAFETY ENFORCEMENT (Step 4).
 *
 * Ensures no invalid product attachment occurs. Never overrides content_mode.
 * On conflict: reactive wins attachment safety, predictive wins content framing.
 *
 * Dashboard panel: inventory_gap_detected, blocked attachments
 * (visually separate from predictive inventory panel)
 */
(function () {
  "use strict";

  function commerceEnabled() {
    return window.CommerceMode && window.CommerceMode.isCommerceMode();
  }

  var MOUNT_ID = "tiktokShopInventoryGate";
  var CATALOG_KEY = "tiktok_shop_catalog";
  var PAUSED_KEY = "tiktok_shop_paused_attachments";
  var OVERRIDE_KEY = "tiktok_shop_inventory_override";
  var BLOCKED_KEY = "tiktok_shop_blocked_attachments";

  var CATEGORY_RULES = [
    { keywords: ["army", "military", "veteran", "raf", "navy", "troops"], category: "military" },
    { keywords: ["flag", "union jack", "union flag", "st george"], category: "flags" },
    { keywords: ["churchill", "history", "heritage", "ww2", "d-day", "dunkirk"], category: "history" },
    { keywords: ["hoodie", "clothing", "apparel", "wear"], category: "clothing" },
    { keywords: ["remembrance", "poppy", "cenotaph"], category: "remembrance" },
    { keywords: ["spitfire", "hurricane", "battle of britain"], category: "aviation" },
    { keywords: ["king", "royal", "monarchy", "crown", "queen"], category: "royal" },
    { keywords: ["skincare", "serum", "moisturizer", "acne"], category: "skincare" },
    { keywords: ["makeup", "cosmetic", "lipstick", "beauty"], category: "beauty" },
    { keywords: ["fitness", "workout", "gym", "protein"], category: "fitness" },
    { keywords: ["book", "books"], category: "books" }
  ];

  function normalizeName(value) {
    return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  function inferCategory(productName) {
    var lowered = normalizeName(productName);
    for (var i = 0; i < CATEGORY_RULES.length; i++) {
      var rule = CATEGORY_RULES[i];
      for (var k = 0; k < rule.keywords.length; k++) {
        if (lowered.indexOf(rule.keywords[k]) !== -1) return rule.category;
      }
    }
    return "general";
  }

  function catalogEntryName(entry) {
    return String(entry.name || entry.product_name || entry.title || "");
  }

  function catalogEntryCategory(entry) {
    if (entry.category) return String(entry.category).toLowerCase();
    return inferCategory(catalogEntryName(entry));
  }

  function findExactMatch(productName, catalog) {
    var target = normalizeName(productName);
    if (!target) return null;
    for (var i = 0; i < catalog.length; i++) {
      if (normalizeName(catalogEntryName(catalog[i])) === target) return catalog[i];
    }
    return null;
  }

  function findCategoryMatch(productName, catalog) {
    var targetCategory = inferCategory(productName);
    if (targetCategory === "general") return null;
    for (var i = 0; i < catalog.length; i++) {
      var entry = catalog[i];
      if (catalogEntryCategory(entry) === targetCategory && entry.product_id) return entry;
    }
    return null;
  }

  function checkProductAvailability(productName, tiktokShopCatalog) {
    var catalog = (tiktokShopCatalog || []).filter(function (c) { return c && typeof c === "object"; });
    productName = String(productName || "").trim();

    if (!productName) {
      return {
        status: "missing",
        product_id: null,
        attachable: false,
        action_required: "add_to_showcase",
        suggested_product: productName,
        category: "general",
        match_type: null
      };
    }

    var match = findExactMatch(productName, catalog);
    var matchType = "exact";
    if (!match) {
      match = findCategoryMatch(productName, catalog);
      matchType = match ? "category" : null;
    }

    if (match && match.product_id) {
      return {
        status: "available",
        product_id: String(match.product_id),
        attachable: true,
        match_type: matchType,
        matched_name: catalogEntryName(match),
        category: catalogEntryCategory(match)
      };
    }

    return {
      status: "missing",
      product_id: null,
      attachable: false,
      action_required: "add_to_showcase",
      suggested_product: productName,
      category: inferCategory(productName),
      match_type: null
    };
  }

  function buildInventoryGapEvent(availability) {
    return {
      product_name: availability.suggested_product || "",
      category: availability.category || "general",
      message: "Add this product to your TikTok Shop Showcase",
      status: "waiting_user_action",
      action_required: availability.action_required || "add_to_showcase"
    };
  }

  function modeAllowsAttachment(contentMode) {
    if (window.TikTokContentModeResolver && typeof window.TikTokContentModeResolver.modeAllowsAttachment === "function") {
      return window.TikTokContentModeResolver.modeAllowsAttachment(contentMode);
    }
    if (!contentMode) return false;
    var mode = contentMode.mode || "generic";
    return mode !== "generic" && mode !== "generic_high_priority" && !contentMode.pause_product_attachment;
  }

  function getCatalog() {
    try {
      var raw = localStorage.getItem(CATALOG_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveCatalog(catalog) {
    localStorage.setItem(CATALOG_KEY, JSON.stringify(catalog));
  }

  function getPausedAttachments() {
    try {
      var raw = localStorage.getItem(PAUSED_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function savePausedAttachments(items) {
    localStorage.setItem(PAUSED_KEY, JSON.stringify(items));
  }

  function getBlockedAttachments() {
    try {
      var raw = localStorage.getItem(BLOCKED_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveBlockedAttachments(items) {
    localStorage.setItem(BLOCKED_KEY, JSON.stringify(items));
  }

  function getAccountId() {
    if (typeof currentUser !== "undefined" && currentUser && currentUser.id) {
      return currentUser.id;
    }
    return "local_account";
  }

  function emitInventoryGapDetected(availability, metadata) {
    var gapEvent = buildInventoryGapEvent(availability);
    if (typeof trackEvent === "function") {
      trackEvent("inventory_gap_detected", {
        event: "inventory_gap_detected",
        inventory_gap_event: gapEvent,
        product_name: gapEvent.product_name,
        category: gapEvent.category,
        status: gapEvent.status,
        metadata: metadata || {}
      });
    }
    return gapEvent;
  }

  function suggestProductName(keyword) {
    if (typeof makeProduct === "function") return makeProduct(keyword);
    return keyword ? String(keyword) + " product" : "";
  }

  function registerPausedAttachment(contentId, productName, availability, keyword, contentMode) {
    var paused = getPausedAttachments();
    var record = {
      content_id: contentId,
      account_id: getAccountId(),
      product_name: productName,
      keyword: keyword || "",
      category: availability.category,
      content_mode: contentMode ? contentMode.mode : "unknown",
      inventory_gap_event: buildInventoryGapEvent(availability),
      status: "waiting_user_action",
      paused_at: new Date().toISOString()
    };
    paused = paused.filter(function (p) { return p.content_id !== contentId; });
    paused.push(record);
    savePausedAttachments(paused);
    return record;
  }

  function registerBlockedAttachment(contentId, productName, availability, contentMode, reason) {
    var blocked = getBlockedAttachments();
    var record = {
      content_id: contentId,
      product_name: productName,
      content_mode: contentMode ? contentMode.mode : "unknown",
      reason: reason || "reactive_safety_block",
      inventory_gap_event: buildInventoryGapEvent(availability),
      blocked_at: new Date().toISOString()
    };
    blocked = blocked.filter(function (b) { return b.content_id !== contentId; });
    blocked.push(record);
    saveBlockedAttachments(blocked);
    return record;
  }

  function resumeAfterInventoryUpdate(accountId, contentId) {
    var catalog = getCatalog();
    var paused = getPausedAttachments();
    var targetAccount = accountId || getAccountId();
    var resumed = [];
    var stillWaiting = [];

    for (var i = 0; i < paused.length; i++) {
      var item = paused[i];
      if (item.account_id !== targetAccount) continue;
      if (contentId && item.content_id !== contentId) continue;

      var availability = checkProductAvailability(item.product_name, catalog);
      if (availability.attachable) {
        resumed.push({
          content_id: item.content_id,
          product_name: item.product_name,
          product_id: availability.product_id,
          content_mode: item.content_mode,
          status: "attached",
          resumed_at: new Date().toISOString()
        });
        item.status = "resumed";
        item.product_id = availability.product_id;
      } else {
        stillWaiting.push({
          content_id: item.content_id,
          product_name: item.product_name,
          content_mode: item.content_mode,
          inventory_gap_event: buildInventoryGapEvent(availability),
          status: "waiting_user_action"
        });
      }
    }

    var remaining = paused.filter(function (p) {
      return p.status !== "resumed";
    });
    savePausedAttachments(remaining);

    if (typeof trackEvent === "function") {
      trackEvent("inventory_gap_resume", {
        account_id: targetAccount,
        resumed_count: resumed.length,
        still_waiting_count: stillWaiting.length
      });
    }

    return {
      success: true,
      account_id: targetAccount,
      resumed: resumed,
      still_waiting: stillWaiting
    };
  }

  function gateProductAttachment(keyword, productName, contentId, contentMode) {
    var catalog = getCatalog();
    var resolvedName = productName || suggestProductName(keyword);
    contentMode = contentMode || { mode: "product_specific" };
    var id = contentId || "content_" + normalizeName(keyword).replace(/\s+/g, "_");

    if (!modeAllowsAttachment(contentMode)) {
      return {
        content_id: id,
        keyword: keyword,
        product_name: resolvedName,
        content_mode: contentMode.mode,
        attachment_status: "skipped_by_content_mode",
        product_id: null,
        paused: false,
        layer: "reactive"
      };
    }

    var attachName = contentMode.product_name || resolvedName;
    var availability = checkProductAvailability(attachName, catalog);

    if (availability.attachable) {
      return {
        content_id: id,
        keyword: keyword,
        product_name: attachName,
        content_mode: contentMode.mode,
        attachment_status: "attached",
        product_id: availability.product_id,
        paused: false,
        layer: "reactive"
      };
    }

    var paused = registerPausedAttachment(id, attachName, availability, keyword, contentMode);
    var blocked = registerBlockedAttachment(id, attachName, availability, contentMode, "reactive_safety_block");
    var gapEvent = emitInventoryGapDetected(availability, { content_id: id, keyword: keyword, content_mode: contentMode.mode });

    return {
      content_id: id,
      keyword: keyword,
      product_name: attachName,
      content_mode: contentMode.mode,
      attachment_status: "blocked_inventory_gap",
      product_id: null,
      paused: true,
      inventory_gap_event: gapEvent,
      blocked_attachment: blocked,
      paused_record: paused,
      layer: "reactive"
    };
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(value) {
    return String(value || "").replace(/'/g, "\\'");
  }

  function renderInventoryGapCard(gap) {
    var h = '<div style="padding:12px;background:rgba(255,71,87,.06);border:1px solid rgba(255,71,87,.2);border-radius:10px;margin-bottom:10px">';
    h += '<div style="font-size:10px;color:#ff4757;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">';
    h += gap.blocked ? "Blocked Attachment" : "Inventory Gap Detected";
    h += '</div>';
    h += '<div style="font-size:16px;font-weight:900;margin-bottom:4px">' + escapeHtml(gap.product_name) + '</div>';
    h += '<div style="font-size:10px;color:var(--muted)">Category: ' + escapeHtml(gap.category || "general");
    if (gap.content_mode) h += ' | Content mode: ' + escapeHtml(gap.content_mode);
    h += '</div>';
    h += '<div style="font-size:11px;color:var(--white);margin-top:8px">' + escapeHtml(gap.message || "Add this product to your TikTok Shop Showcase") + '</div>';
    if (gap.content_id) {
      h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">';
      h += '<button class="copy-btn" style="flex:1;background:rgba(255,71,87,.12);color:#ff4757;border-color:rgba(255,71,87,.35)" ';
      h += 'onclick="TikTokShopInventoryGate.handleAddToShowcase(\'' + escapeAttr(gap.content_id) + '\')">';
      h += 'Re-check Catalog</button>';
      h += '<button class="copy-btn" style="flex:1" ';
      h += 'onclick="TikTokShopInventoryGate.handleUserOverride(\'' + escapeAttr(gap.content_id) + '\')">';
      h += 'Continue Without Product</button>';
      h += '</div>';
    }
    h += '</div>';
    return h;
  }

  function render(gaps, blockedList) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
    if (!commerceEnabled()) {
      el.innerHTML = "";
      return;
    }

    gaps = gaps || [];
    blockedList = blockedList || getBlockedAttachments();

    var paused = getPausedAttachments().filter(function (p) {
      return p.status === "waiting_user_action";
    });

    if (gaps.length === 0 && paused.length === 0 && blockedList.length === 0) {
      el.innerHTML = "";
      return;
    }

    var seen = {};
    var h = '<div class="card" style="border-color:rgba(255,71,87,.35);margin-bottom:12px" data-panel="reactive-inventory">';
    h += '<div class="card-header"><h2>Reactive Inventory Panel</h2>';
    h += '<div class="section-icon" style="color:#ff4757">&#9888;</div></div>';
    h += '<p style="font-size:11px;color:var(--muted);margin-bottom:10px">';
    h += '<strong style="color:#ff4757">Safety layer</strong> — final attachment enforcement. Never overrides content mode.';
    h += '</p>';

    var allGaps = gaps.concat(blockedList.map(function (b) {
      return {
        content_id: b.content_id,
        product_name: b.product_name,
        category: (b.inventory_gap_event && b.inventory_gap_event.category) || "general",
        content_mode: b.content_mode,
        message: (b.inventory_gap_event && b.inventory_gap_event.message) || "Attachment blocked by safety gate",
        blocked: true
      };
    })).concat(paused.map(function (p) {
      return {
        content_id: p.content_id,
        product_name: p.product_name,
        category: p.category,
        content_mode: p.content_mode,
        message: (p.inventory_gap_event && p.inventory_gap_event.message) || "Add this product to your TikTok Shop Showcase",
        status: "waiting_user_action"
      };
    }));

    for (var i = 0; i < allGaps.length; i++) {
      var gap = allGaps[i];
      var key = gap.content_id || gap.product_name;
      if (seen[key]) continue;
      seen[key] = true;
      h += renderInventoryGapCard(gap);
    }

    h += '<p style="font-size:9px;color:var(--muted);margin-top:8px;text-align:center">';
    h += blockedList.length + ' blocked | ' + paused.length + ' paused | reactive wins attachment safety';
    h += '</p></div>';

    el.innerHTML = h;
  }

  function lookupContentMode(productName, predictive) {
    if (!predictive || !predictive.content_mode_suggestions) return null;
    var key = normalizeName(productName);
    for (var i = 0; i < predictive.content_mode_suggestions.length; i++) {
      var s = predictive.content_mode_suggestions[i];
      if (normalizeName(s.product_name) === key) return s.content_mode;
    }
    return null;
  }

  function processTrendResults(results, predictiveIntelligence) {
    if (!commerceEnabled()) {
      render([], []);
      return { gaps: [], blocked: [], attachments: [], inventory_gaps: [] };
    }
    if (!results || !results.length) {
      render([], []);
      return { gaps: [], blocked: [], attachments: [], inventory_gaps: [] };
    }

    var catalog = getCatalog();
    if (!catalog.length) {
      seedDefaultCatalog();
      catalog = getCatalog();
    }

    var productPick = results.length >= 3 ? results[2] : results[results.length - 1];
    var keyword = productPick.keyword || "";
    var productName = productPick.product || suggestProductName(keyword);
    var contentMode = lookupContentMode(productName, predictiveIntelligence);

    if (!contentMode && window.TikTokContentModeResolver) {
      var demand = 0;
      if (predictiveIntelligence && predictiveIntelligence.likely_needed_products) {
        var pk = normalizeName(productName);
        for (var d = 0; d < predictiveIntelligence.likely_needed_products.length; d++) {
          var lp = predictiveIntelligence.likely_needed_products[d];
          if (normalizeName(lp.product_name) === pk) {
            demand = lp.demand_score;
            break;
          }
        }
      }
      var avail = checkProductAvailability(productName, catalog);
      contentMode = window.TikTokContentModeResolver.resolveContentMode(productName, demand, avail, catalog);
    }

    if (!contentMode) {
      contentMode = { mode: "generic", pause_product_attachment: true };
    }

    var attachment = gateProductAttachment(keyword, productName, "plan_slot_3", contentMode);

    var gaps = [];
    var blocked = [];
    var attachments = [];

    if (attachment.paused || attachment.attachment_status === "blocked_inventory_gap") {
      gaps.push({
        content_id: attachment.content_id,
        product_name: attachment.product_name,
        category: attachment.inventory_gap_event.category,
        content_mode: attachment.content_mode,
        message: attachment.inventory_gap_event.message,
        status: "waiting_user_action"
      });
      if (attachment.blocked_attachment) blocked.push(attachment.blocked_attachment);
    } else if (attachment.attachment_status === "attached") {
      attachments.push(attachment);
    }

    render(gaps, blocked);
    return { gaps: gaps, blocked: blocked, attachments: attachments, inventory_gaps: gaps };
  }

  function seedDefaultCatalog() {
    if (getCatalog().length > 0) return;
    var catalog = [];
    if (window.TikTokLiveState && window.TikTokLiveState.getCache) {
      var cached = window.TikTokLiveState.getCache();
      if (cached && cached.shop_catalog && cached.shop_catalog.length) {
        catalog = cached.shop_catalog;
      }
    }
    if (!catalog.length) {
      catalog = [
        { product_id: "tts_10001", name: "British Army history books", category: "military" },
        { product_id: "tts_10002", name: "Union Jack flags and patriotic decor", category: "flags" },
        { product_id: "tts_10003", name: "Royal family collectibles", category: "royal" },
        { product_id: "tts_10004", name: "British history books", category: "history" },
        { product_id: "tts_10005", name: "Proudly British merchandise", category: "general" }
      ];
    }
    saveCatalog(catalog);
  }

  async function seedCatalogFromLiveState() {
    if (getCatalog().length > 0) return;
    if (!window.TikTokLiveState) return;
    try {
      var niche = (typeof USER_NICHE !== "undefined" && USER_NICHE) ? USER_NICHE : "general";
      var liveState = await window.TikTokLiveState.fetch(niche);
      if (liveState && liveState.shop_catalog && liveState.shop_catalog.length) {
        saveCatalog(liveState.shop_catalog);
      } else {
        seedDefaultCatalog();
      }
    } catch (e) {
      seedDefaultCatalog();
    }
  }

  function handleAddToShowcase(contentId) {
    var result = resumeAfterInventoryUpdate(getAccountId(), contentId);
    if (result.resumed.length > 0) {
      if (typeof showToast === "function") {
        showToast("Product found in catalog — attachment resumed!");
      }
      var blocked = getBlockedAttachments().filter(function (b) { return b.content_id !== contentId; });
      saveBlockedAttachments(blocked);
      render([], blocked);
    } else if (result.still_waiting.length > 0) {
      if (typeof showToast === "function") {
        showToast("Still not in catalog — add the product to Showcase, then try again.");
      }
      render(result.still_waiting.map(function (w) {
        return {
          content_id: w.content_id,
          product_name: w.product_name,
          category: (w.inventory_gap_event && w.inventory_gap_event.category) || "general",
          content_mode: w.content_mode,
          message: (w.inventory_gap_event && w.inventory_gap_event.message) || "Add this product to your TikTok Shop Showcase",
          status: "waiting_user_action"
        };
      }), getBlockedAttachments());
    }
  }

  function handleUserOverride(contentId) {
    localStorage.setItem(OVERRIDE_KEY + "_" + contentId, "1");
    var paused = getPausedAttachments().filter(function (p) {
      return p.content_id !== contentId;
    });
    savePausedAttachments(paused);
    var blocked = getBlockedAttachments().filter(function (b) {
      return b.content_id !== contentId;
    });
    saveBlockedAttachments(blocked);
    if (typeof trackEvent === "function") {
      trackEvent("inventory_gap_user_override", { content_id: contentId });
    }
    if (typeof showToast === "function") {
      showToast("Continuing without product attachment for this slot.");
    }
    render([], blocked);
  }

  function init() {
    seedCatalogFromLiveState();
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
    if (!commerceEnabled()) {
      el.innerHTML = "";
      return;
    }
    var paused = getPausedAttachments().filter(function (p) {
      return p.status === "waiting_user_action";
    });
    if (paused.length || getBlockedAttachments().length) {
      render(paused.map(function (p) {
        return {
          content_id: p.content_id,
          product_name: p.product_name,
          category: p.category,
          content_mode: p.content_mode,
          message: (p.inventory_gap_event && p.inventory_gap_event.message) || "Add this product to your TikTok Shop Showcase",
          status: "waiting_user_action"
        };
      }), getBlockedAttachments());
    }
  }

  window.TikTokShopInventoryGate = {
    checkProductAvailability: checkProductAvailability,
    inferCategory: inferCategory,
    resumeAfterInventoryUpdate: resumeAfterInventoryUpdate,
    gateProductAttachment: gateProductAttachment,
    processTrendResults: processTrendResults,
    handleAddToShowcase: handleAddToShowcase,
    handleUserOverride: handleUserOverride,
    getCatalog: getCatalog,
    saveCatalog: saveCatalog,
    render: render,
    init: init
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
