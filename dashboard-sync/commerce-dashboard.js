/**
 * Commerce dashboard panels — Products, Shop, Inventory, Revenue.
 * Only rendered when commerce_mode=true.
 */
(function (global) {
  "use strict";

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function isEnabled() {
    return global.CommerceMode && global.CommerceMode.isCommerceMode();
  }

  function renderProductsPanel(products) {
    var list = Array.isArray(products) ? products : [];
    if (!list.length) {
      return '<p style="font-size:12px;color:var(--muted);padding:12px 0">No matched products yet. Run a trend scan with commerce mode enabled.</p>';
    }
    var h = '<div style="display:flex;flex-direction:column;gap:8px">';
    for (var i = 0; i < list.length && i < 12; i++) {
      var p = list[i];
      h += '<div style="padding:10px;background:var(--panel2);border:1px solid var(--border);border-radius:8px">';
      h += '<div style="font-size:13px;font-weight:700;color:var(--green)">' + esc(p.name) + "</div>";
      h += '<div style="font-size:11px;color:var(--muted);margin-top:4px">Trend: ' + esc(p.keyword || "—") + "</div>";
      if (p.commission) h += '<div style="font-size:10px;color:var(--amber);margin-top:4px">Est. commission: ' + esc(p.commission) + "</div>";
      h += "</div>";
    }
    h += "</div>";
    return h;
  }

  function renderShopPanel() {
    var catalog = [];
    try {
      if (global.TikTokShopInventoryGate && typeof global.TikTokShopInventoryGate.getCatalog === "function") {
        catalog = global.TikTokShopInventoryGate.getCatalog() || [];
      }
    } catch (e) {}
    if (!catalog.length) {
      return '<p style="font-size:12px;color:var(--muted)">Connect your TikTok Shop catalog to enable product attachment.</p>';
    }
    var h = '<div style="display:flex;flex-direction:column;gap:6px">';
    for (var i = 0; i < catalog.length && i < 10; i++) {
      var c = catalog[i];
      h += '<div style="font-size:12px;padding:8px;border-bottom:1px solid var(--border)">• ' + esc(c.name || c.product_name || c.title) + "</div>";
    }
    h += "</div>";
    return h;
  }

  function renderInventoryPanel(gaps) {
    var list = Array.isArray(gaps) ? gaps : [];
    if (!list.length) {
      return '<p style="font-size:12px;color:var(--green);padding:12px 0">No inventory gaps — all matched products are in your Showcase.</p>';
    }
    var h = '<div style="display:flex;flex-direction:column;gap:8px">';
    for (var i = 0; i < list.length; i++) {
      var g = list[i];
      h += '<div style="padding:10px;background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.3);border-radius:8px">';
      h += '<div style="font-size:12px;font-weight:700;color:var(--amber)">' + esc(g.product_name || g.name) + "</div>";
      h += '<div style="font-size:11px;color:var(--muted);margin-top:4px">' + esc(g.message || "Add to TikTok Shop Showcase") + "</div>";
      h += "</div>";
    }
    h += "</div>";
    return h;
  }

  function renderRevenuePanel(suggestions) {
    var list = Array.isArray(suggestions) ? suggestions : [];
    if (!list.length) {
      return '<p style="font-size:12px;color:var(--muted)">Enable commerce mode and scan trends to get revenue suggestions.</p>';
    }
    var h = '<div style="display:flex;flex-direction:column;gap:8px">';
    for (var i = 0; i < list.length; i++) {
      var s = list[i];
      h += '<div style="padding:10px;background:var(--panel2);border:1px solid var(--border);border-radius:8px">';
      h += '<div style="font-size:12px;font-weight:700">' + esc(s.product) + "</div>";
      h += '<div style="font-size:11px;color:var(--muted);margin-top:4px">' + esc(s.action) + "</div>";
      if (s.expected_outcome) h += '<div style="font-size:10px;color:var(--green);margin-top:4px">' + esc(s.expected_outcome) + "</div>";
      h += "</div>";
    }
    h += "</div>";
    return h;
  }

  var _lastCommerce = { products: [], inventory_gaps: [], revenue_suggestions: [] };

  function update(data) {
    if (!isEnabled()) return;
    _lastCommerce = data || _lastCommerce;
    var productsEl = document.getElementById("commerceProductsPanel");
    var shopEl = document.getElementById("commerceShopPanel");
    var inventoryEl = document.getElementById("commerceInventoryPanel");
    var revenueEl = document.getElementById("commerceRevenuePanel");
    if (productsEl) productsEl.innerHTML = renderProductsPanel(_lastCommerce.products);
    if (shopEl) shopEl.innerHTML = renderShopPanel();
    if (inventoryEl) inventoryEl.innerHTML = renderInventoryPanel(_lastCommerce.inventory_gaps);
    if (revenueEl) revenueEl.innerHTML = renderRevenuePanel(_lastCommerce.revenue_suggestions);
  }

  function mount() {
    if (!isEnabled()) return;
    update(_lastCommerce);
  }

  function unmount() {
    var ids = ["commerceProductsPanel", "commerceShopPanel", "commerceInventoryPanel", "commerceRevenuePanel"];
    for (var i = 0; i < ids.length; i++) {
      var el = document.getElementById(ids[i]);
      if (el) el.innerHTML = "";
    }
  }

  global.CommerceDashboard = {
    update: update,
    mount: mount,
    unmount: unmount,
    renderProductsPanel: renderProductsPanel,
    renderShopPanel: renderShopPanel,
    renderInventoryPanel: renderInventoryPanel,
    renderRevenuePanel: renderRevenuePanel,
  };
})(typeof window !== "undefined" ? window : global);
