"""Tests for dual-layer TikTok Shop inventory intelligence architecture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tiktok_content_mode_resolver import (
    HIGH_DEMAND_THRESHOLD,
    generic_fallback_mode,
    mode_allows_attachment,
    resolve_content_mode,
)
from tiktok_inventory_predictor import (
    build_inventory_prevention_event,
    predictRequiredProducts,
    precheck_catalog,
    run_predictive_inventory_intelligence,
)
from tiktok_shop_content_pipeline import run_tiktok_shop_content_pipeline
from tiktok_shop_inventory_gate import checkProductAvailability

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CATALOG = ROOT / "data" / "tiktok_shop_sample_catalog.json"
SAMPLE_ITEMS = ROOT / "data" / "tiktok_shop_sample_content_items.json"
SAMPLE_TRENDS = ROOT / "data" / "tiktok_shop_sample_trends.json"


@pytest.fixture
def catalog() -> list[dict]:
    return json.loads(SAMPLE_CATALOG.read_text(encoding="utf-8"))


@pytest.fixture
def trends() -> dict:
    return json.loads(SAMPLE_TRENDS.read_text(encoding="utf-8"))


@pytest.fixture
def content_items() -> list[dict]:
    return json.loads(SAMPLE_ITEMS.read_text(encoding="utf-8"))


def test_predict_required_products_returns_scored_items(trends):
    result = predictRequiredProducts(trends, niche="military", historical_content=None)
    assert result["success"] is True
    assert result["prediction_count"] > 0
    products = result["likely_needed_products"]
    assert all("product_name" in p for p in products)
    assert all(0 <= p["demand_score"] <= 1 for p in products)


def test_predictive_layer_never_attaches_products(catalog, trends):
    intelligence = run_predictive_inventory_intelligence(
        trends, "general", None, catalog
    )
    assert "product_id" not in str(intelligence.get("must_add_products", []))
    for pc in intelligence.get("pre_check_results", []):
        if pc["catalog_status"] == "pre_add_required":
            assert pc["availability"]["product_id"] is None


def test_content_mode_product_specific_when_exists(catalog):
    avail = checkProductAvailability("British Army history books", catalog)
    mode = resolve_content_mode("British Army history books", 0.5, avail, catalog)
    assert mode["mode"] == "product_specific"
    assert mode["product_id"] is not None


def test_content_mode_generic_high_priority_when_missing_high_demand(catalog):
    avail = checkProductAvailability("Smart fitness tracker band", catalog)
    mode = resolve_content_mode("Smart fitness tracker band", 0.85, avail, catalog)
    assert mode["mode"] == "generic_high_priority"
    assert mode["product_id"] is None
    assert mode["pause_product_attachment"] is True


def test_content_mode_category_substitute_when_missing_low_demand(catalog):
    avail = checkProductAvailability("Royal commemorative medal set", catalog)
    mode = resolve_content_mode("Royal commemorative medal set", 0.3, avail, catalog)
    assert mode["mode"] == "category_substitute"


def test_generic_fallback_mode_on_resolver_failure():
    mode = generic_fallback_mode("test product")
    assert mode["mode"] == "generic"
    assert mode["pause_product_attachment"] is True


def test_mode_allows_attachment_respects_predictive_framing():
    assert mode_allows_attachment({"mode": "product_specific"}) is True
    assert mode_allows_attachment({"mode": "category_substitute"}) is True
    assert mode_allows_attachment({"mode": "generic_high_priority", "pause_product_attachment": True}) is False
    assert mode_allows_attachment({"mode": "generic", "pause_product_attachment": True}) is False


def test_must_add_products_only_high_demand(catalog, trends):
    intelligence = run_predictive_inventory_intelligence(
        trends, "general", None, catalog
    )
    for item in intelligence["must_add_products"]:
        assert item["demand_score"] > HIGH_DEMAND_THRESHOLD


def test_prevention_event_structure():
    product = {"product_name": "Test Product", "category": "fitness", "demand_score": 0.8}
    pre_check = {"product_name": "Test Product", "category": "fitness", "demand_score": 0.8, "confidence": 0.7}
    evt = build_inventory_prevention_event(product, pre_check)
    assert evt["product_name"] == "Test Product"
    assert evt["priority"] == "high"


def test_pipeline_dual_layer_architecture(catalog, content_items, trends):
    result = run_tiktok_shop_content_pipeline(
        account_id="test_account",
        content_items=content_items,
        tiktok_shop_catalog=catalog,
        trends=trends,
        niche="military",
    )
    assert result["success"] is True
    assert result["architecture"] == "dual_layer_inventory_intelligence"
    assert result["hierarchy"]["conflict_rule"] == "reactive_wins_attachment_predictive_wins_framing"
    assert "predictive_intelligence" in result
    assert "blocked_attachments" in result
    assert "must_add_products" in result
    assert "inventory_prevention_events" in result
    assert "inventory_gap_events" in result


def test_pipeline_never_blocks_on_missing_inventory(catalog, content_items, trends):
    result = run_tiktok_shop_content_pipeline(
        account_id="test_account",
        content_items=content_items,
        tiktok_shop_catalog=catalog,
        trends=trends,
        niche="general",
    )
    assert result["success"] is True
    assert result["pipeline_status"] == "completed"
    assert result["content_items_processed"] == len(content_items)


def test_reactive_wins_attachment_predictive_wins_framing(catalog):
    """When gate blocks attachment, content_mode from predictive layer is preserved."""
    items = [{"keyword": "test", "product_name": "Nonexistent product xyz"}]
    result = run_tiktok_shop_content_pipeline(
        account_id="test_account",
        content_items=items,
        tiktok_shop_catalog=catalog,
    )
    assert result["success"] is True
    for r in result["results"]:
        assert "content_mode" in r
        assert "content_mode_detail" in r
        if r.get("attachment_status") == "blocked_inventory_gap":
            assert r["content_mode"] == r["content_mode_detail"]["mode"]


def test_fitness_item_uses_generic_high_priority_or_skipped(catalog, content_items, trends):
    result = run_tiktok_shop_content_pipeline(
        account_id="test_account",
        content_items=content_items,
        tiktok_shop_catalog=catalog,
        trends=trends,
        niche="general",
    )
    fitness_result = next(
        (r for r in result["results"] if "fitness" in (r.get("product_name") or "").lower()),
        None,
    )
    assert fitness_result is not None
    assert fitness_result.get("content_mode") in (
        "generic_high_priority",
        "generic",
        "category_substitute",
    ) or fitness_result.get("attachment_status") == "skipped_by_content_mode"
