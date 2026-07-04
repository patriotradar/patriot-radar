/**
 * TikTok Shop Inventory Gate — human-in-the-loop product onboarding.
 *
 * Detects missing catalog products, pauses ONLY product attachment, and resumes
 * after the creator adds items to TikTok Shop Showcase.
 *
 * Isolated from existing trend UI and niche comment intelligence modules.
 */
(function () {
  "use strict";

  var MOUNT_ID = "tiktokShopInventoryGate";
  var CATALOG_KEY = "tiktok_shop_catalog";
  var PAUSED_KEY = "tiktok_shop_paused_attachments";
  var OVERRIDE_KEY = "tiktok_shop_inventory_override";

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

  function registerPausedAttachment(contentId, productName, availability, keyword) {
    var paused = getPausedAttachments();
    var record = {
      content_id: contentId,
      account_id: getAccountId(),
      product_name: productName,
      keyword: keyword || "",
      category: availability.category,
      inventory_gap_event: buildInventoryGapEvent(availability),
      status: "waiting_user_action",
      paused_at: new Date().toISOString()
    };
    paused = paused.filter(function (p) { return p.content_id !== contentId; });
    paused.push(record);
    savePausedAttachments(paused);
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
          status: "attached",
          resumed_at: new Date().toISOString()
        });
        item.status = "resumed";
        item.product_id = availability.product_id;
      } else {
        stillWaiting.push({
          content_id: item.content_id,
          product_name: item.product_name,
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

  function gateProductAttachment(keyword, productName, contentId) {
    var catalog = getCatalog();
    var resolvedName = productName || suggestProductName(keyword);
    var availability = checkProductAvailability(resolvedName, catalog);
    var id = contentId || "content_" + normalizeName(keyword).replace(/\s+/g, "_");

    if (availability.attachable) {
      return {
        content_id: id,
        keyword: keyword,
        product_name: resolvedName,
        attachment_status: "attached",
        product_id: availability.product_id,
        paused: false
      };
    }

    var paused = registerPausedAttachment(id, resolvedName, availability, keyword);
    var gapEvent = emitInventoryGapDetected(availability, { content_id: id, keyword: keyword });

    return {
      content_id: id,
      keyword: keyword,
      product_name: resolvedName,
      attachment_status: "paused_inventory_gap",
      product_id: null,
      paused: true,
      inventory_gap_event: gapEvent,
      paused_record: paused
    };
  }

  function renderInventoryGapCard(gap) {
    var h = '<div class="card" style="border-color:rgba(255,71,87,.35);margin-bottom:12px">';
    h += '<div class="card-header"><h2>TikTok Shop Inventory Gap</h2>';
    h += '<div class="section-icon" style="color:#ff4757">&#9888;</div></div>';
    h += '<p style="font-size:12px;color:var(--muted);margin-bottom:10px">';
    h += 'Product attachment is paused until this item is in your TikTok Shop Showcase. ';
    h += 'Your content plan and pipeline continue normally.';
    h += '</p>';
    h += '<div style="padding:12px;background:rgba(255,71,87,.06);border:1px solid rgba(255,71,87,.2);border-radius:10px;margin-bottom:10px">';
    h += '<div style="font-size:10px;color:#ff4757;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Missing Product</div>';
    h += '<div style="font-size:16px;font-weight:900;margin-bottom:4px">' + escapeHtml(gap.product_name) + '</div>';
    h += '<div style="font-size:10px;color:var(--muted)">Category: ' + escapeHtml(gap.category || "general") + '</div>';
    h += '<div style="font-size:11px;color:var(--white);margin-top:8px">' + escapeHtml(gap.message || "Add this product to your TikTok Shop Showcase") + '</div>';
    h += '</div>';
    h += '<div style="display:flex;gap:8px;flex-wrap:wrap">';
    h += '<button class="copy-btn" style="flex:1;background:rgba(255,71,87,.12);color:#ff4757;border-color:rgba(255,71,87,.35)" ';
    h += 'onclick="TikTokShopInventoryGate.handleAddToShowcase(\'' + escapeAttr(gap.content_id) + '\')">';
    h += 'Add to Showcase</button>';
    h += '<button class="copy-btn" style="flex:1" ';
    h += 'onclick="TikTokShopInventoryGate.handleUserOverride(\'' + escapeAttr(gap.content_id) + '\')">';
    h += 'Continue Without Product</button>';
    h += '</div>';
    h += '<p style="font-size:9px;color:var(--muted);margin-top:8px;text-align:center">';
    h += 'After adding in TikTok Shop, click "Add to Showcase" to re-check your catalog and resume attachment.';
    h += '</p></div>';
    return h;
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

  function render(catalogGaps) {
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;

    var gaps = catalogGaps || [];
    var paused = getPausedAttachments().filter(function (p) {
      return p.status === "waiting_user_action";
    });

    if (gaps.length === 0 && paused.length === 0) {
      el.innerHTML = "";
      return;
    }

    var seen = {};
    var h = "";
    var allGaps = gaps.concat(paused.map(function (p) {
      return {
        content_id: p.content_id,
        product_name: p.product_name,
        category: p.category,
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

    el.innerHTML = h;
  }

  function processTrendResults(results) {
    if (!results || !results.length) {
      render([]);
      return { gaps: [], attachments: [] };
    }

    var catalog = getCatalog();
    if (!catalog.length) {
      seedDefaultCatalog();
      catalog = getCatalog();
    }

    var productPick = results.length >= 3 ? results[2] : results[results.length - 1];
    var keyword = productPick.keyword || "";
    var productName = productPick.product || suggestProductName(keyword);
    var attachment = gateProductAttachment(keyword, productName, "plan_slot_3");

    var gaps = [];
    var attachments = [];

    if (attachment.paused) {
      gaps.push({
        content_id: attachment.content_id,
        product_name: attachment.product_name,
        category: attachment.inventory_gap_event.category,
        message: attachment.inventory_gap_event.message,
        status: "waiting_user_action"
      });
    } else {
      attachments.push(attachment);
    }

    render(gaps);
    return { gaps: gaps, attachments: attachments };
  }

  function seedDefaultCatalog() {
    if (getCatalog().length > 0) return;
    saveCatalog([
      { product_id: "tts_10001", name: "British Army history books", category: "military" },
      { product_id: "tts_10002", name: "Union Jack flags and patriotic decor", category: "flags" },
      { product_id: "tts_10003", name: "Royal family collectibles", category: "royal" },
      { product_id: "tts_10004", name: "British history books", category: "history" },
      { product_id: "tts_10005", name: "Proudly British merchandise", category: "general" }
    ]);
  }

  function handleAddToShowcase(contentId) {
    var result = resumeAfterInventoryUpdate(getAccountId(), contentId);
    if (result.resumed.length > 0) {
      if (typeof showToast === "function") {
        showToast("Product found in catalog — attachment resumed!");
      }
      render([]);
      if (typeof renderAllSections === "function" && typeof cachedResults !== "undefined" && cachedResults) {
        processTrendResults(cachedResults);
      }
    } else if (result.still_waiting.length > 0) {
      if (typeof showToast === "function") {
        showToast("Still not in catalog — add the product to Showcase, then try again.");
      }
      render(result.still_waiting.map(function (w) {
        return {
          content_id: w.content_id,
          product_name: w.product_name,
          category: (w.inventory_gap_event && w.inventory_gap_event.category) || "general",
          message: (w.inventory_gap_event && w.inventory_gap_event.message) || "Add this product to your TikTok Shop Showcase",
          status: "waiting_user_action"
        };
      }));
    }
  }

  function handleUserOverride(contentId) {
    localStorage.setItem(OVERRIDE_KEY + "_" + contentId, "1");
    var paused = getPausedAttachments().filter(function (p) {
      return p.content_id !== contentId;
    });
    savePausedAttachments(paused);
    if (typeof trackEvent === "function") {
      trackEvent("inventory_gap_user_override", { content_id: contentId });
    }
    if (typeof showToast === "function") {
      showToast("Continuing without product attachment for this slot.");
    }
    render([]);
  }

  function init() {
    seedDefaultCatalog();
    var el = document.getElementById(MOUNT_ID);
    if (!el) return;
    var paused = getPausedAttachments().filter(function (p) {
      return p.status === "waiting_user_action";
    });
    if (paused.length) {
      render(paused.map(function (p) {
        return {
          content_id: p.content_id,
          product_name: p.product_name,
          category: p.category,
          message: (p.inventory_gap_event && p.inventory_gap_event.message) || "Add this product to your TikTok Shop Showcase",
          status: "waiting_user_action"
        };
      }));
    }
  }

  window.TikTokShopInventoryGate = {
    checkProductAvailability: checkProductAvailability,
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
