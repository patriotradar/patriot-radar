"""Tests for TikTok Shop predictive inventory intelligence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tiktok_inventory_predictor import (
    HIGH_DEMAND_THRESHOLD,
    build_inventory_prevention_event,
    predictRequiredProducts,
    precheck_catalog,
    resolve_content_mode,
    run_predictive_inventory_intelligence,
)
from tiktok_shop_content_pipeline import run_tiktok_shop_content_pipeline

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
    assert all(0 <= p["confidence"] <= 1 for p in products)
    assert all(isinstance(p["reason"], list) for p in products)


def test_predict_includes_engagement_spike_from_history(trends):
    historical = [
        {"keyword": "british army pride", "product_name": "British Army history books", "views": 50000}
    ]
    result = predictRequiredProducts(trends, niche="military", historical_content=historical)
    army = next(
        (p for p in result["likely_needed_products"] if "army" in p["product_name"].lower()),
        None,
    )
    assert army is not None
    assert "engagement_spike" in army["reason"]


def test_precheck_marks_missing_as_pre_add_required(catalog, trends):
    prediction = predictRequiredProducts(trends, niche="general")
    pre_checks = precheck_catalog(prediction["likely_needed_products"], catalog)
    fitness = next(
        (p for p in pre_checks if "fitness" in p["product_name"].lower()),
        None,
    )
    assert fitness is not None
    assert fitness["catalog_status"] == "pre_add_required"
    assert fitness["availability"]["attachable"] is False
    assert fitness["availability"]["product_id"] is None


def test_precheck_marks_existing_as_ready_to_attach(catalog, trends):
    prediction = predictRequiredProducts(trends, niche="military")
    pre_checks = precheck_catalog(prediction["likely_needed_products"], catalog)
    army = next(
        (p for p in pre_checks if "army" in p["product_name"].lower()),
        None,
    )
    assert army is not None
    assert army["catalog_status"] == "ready_to_attach"
    assert army["availability"]["attachable"] is True
    assert army["availability"]["product_id"] is not None


def test_prevention_event_for_missing_high_demand(catalog, trends):
    intelligence = run_predictive_inventory_intelligence(
        trends, "general", None, catalog
    )
    events = intelligence["inventory_prevention_events"]
    assert len(events) > 0
    for evt in events:
        assert evt["message"] == "Add this product to your TikTok Shop BEFORE posting content"
        assert evt["priority"] in ("high", "medium", "low")
        assert 0 <= evt["expected_revenue_score"] <= 1


def test_must_add_products_only_high_demand(catalog, trends):
    intelligence = run_predictive_inventory_intelligence(
        trends, "general", None, catalog
    )
    for item in intelligence["must_add_products"]:
        assert item["demand_score"] > HIGH_DEMAND_THRESHOLD
        assert item.get("suggest_immediate_add") is True


def test_resolve_content_mode_generic_for_missing(catalog):
    mode = resolve_content_mode("Smart fitness tracker band", None, catalog)
    assert mode["mode"] == "generic"
    assert mode["pause_product_content"] is True
    assert mode["product_id"] is None


def test_resolve_content_mode_product_specific_when_available(catalog):
    pre_check = {
        "catalog_status": "ready_to_attach",
        "availability": {
            "attachable": True,
            "product_id": "tts_10001",
            "status": "available",
        },
    }
    mode = resolve_content_mode("British Army history books", pre_check, catalog)
    assert mode["mode"] == "product_specific"
    assert mode["product_id"] == "tts_10001"


def test_never_fabricates_product_ids(catalog, trends):
    intelligence = run_predictive_inventory_intelligence(
        trends, "general", None, catalog
    )
    for pc in intelligence["pre_check_results"]:
        if pc["catalog_status"] == "pre_add_required":
            assert pc["availability"]["product_id"] is None


def test_pipeline_integrates_predictive_layer(catalog, content_items, trends):
    result = run_tiktok_shop_content_pipeline(
        account_id="test_account",
        content_items=content_items,
        tiktok_shop_catalog=catalog,
        trends=trends,
        niche="military",
    )
    assert result["success"] is True
    assert "predictive_intelligence" in result
    assert "inventory_prevention_events" in result
    assert "must_add_products" in result
    assert result["pipeline_steps"] == [
        "trend_detection",
        "product_prediction",
        "inventory_pre_check",
        "content_generation",
        "product_attachment",
        "queue_system",
        "learning_engine",
    ]

    fitness_result = next(
        (r for r in result["results"] if "fitness" in (r.get("product_name") or "").lower()),
        None,
    )
    assert fitness_result is not None
    assert fitness_result.get("content_mode") == "generic" or fitness_result.get("attachment_status") == "skipped_generic_mode"


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


def test_pipeline_preserves_reactive_inventory_gap_fallback(catalog, content_items):
    """Reactive gate still catches gaps when prediction is not run."""
    items = [{"keyword": "test", "product_name": "Nonexistent product xyz"}]
    result = run_tiktok_shop_content_pipeline(
        account_id="test_account",
        content_items=items,
        tiktok_shop_catalog=catalog,
    )
    assert result["success"] is True
    assert result["paused_attachment_count"] >= 0
    assert "inventory_gap_events" in result


def test_build_inventory_prevention_event_structure():
    product = {"product_name": "Test Product", "category": "fitness", "demand_score": 0.8}
    pre_check = {"product_name": "Test Product", "category": "fitness", "demand_score": 0.8, "confidence": 0.7}
    evt = build_inventory_prevention_event(product, pre_check)
    assert evt["product_name"] == "Test Product"
    assert evt["priority"] == "high"
    assert evt["demand_score"] == 0.8
