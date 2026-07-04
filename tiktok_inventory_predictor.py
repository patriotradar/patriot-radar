"""
TikTok Shop predictive inventory intelligence — INTENT DECISION layer.

Predicts likely-needed products BEFORE content generation and pre-checks catalog
availability. This layer ONLY influences decisions — it NEVER attaches products.

Produces:
  - likely_needed_products
  - content_mode suggestions (via content_mode_resolver)
  - must_add_products
  - inventory_prevention_event

The reactive inventory gate (tiktok_shop_inventory_gate) is FINAL SAFETY at
attachment time. On conflict: reactive wins attachment, predictive wins framing.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from tiktok_content_mode_resolver import (
    HIGH_DEMAND_THRESHOLD,
    generic_fallback_mode,
    resolve_content_mode,
)
from tiktok_shop_inventory_gate import checkProductAvailability, infer_category

logger = logging.getLogger(__name__)

MEDIUM_DEMAND_THRESHOLD = 0.4

VALID_REASONS = frozenset({"trend_match", "engagement_spike", "niche_alignment"})

_NICHE_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "military": ("army", "military", "veteran", "raf", "navy", "defence", "troops"),
    "flags": ("flag", "union jack", "patriotic", "national"),
    "history": ("history", "heritage", "churchill", "ww2", "d-day"),
    "royal": ("royal", "king", "monarchy", "crown", "queen"),
    "remembrance": ("remembrance", "poppy", "cenotaph"),
    "fitness": ("fitness", "workout", "gym", "health"),
    "beauty": ("beauty", "makeup", "skincare", "cosmetic"),
    "books": ("book", "reading", "literature"),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _resolve_product_name(item: dict[str, Any]) -> str:
    return (
        (item.get("product_name") or item.get("product") or item.get("suggested_product") or "")
        .strip()
    )


def _iter_trend_items(trends: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Flatten trend payloads into a single list of trend items."""
    if not trends:
        return []
    if isinstance(trends, list):
        return [t for t in trends if isinstance(t, dict)]

    items: list[dict[str, Any]] = []
    for key in ("product_trends", "emerging", "results", "trending", "items"):
        block = trends.get(key)
        if isinstance(block, list):
            items.extend(t for t in block if isinstance(t, dict))

    niche_signals = trends.get("niche_signals")
    if isinstance(niche_signals, list):
        items.extend(t for t in niche_signals if isinstance(t, dict))

    return items


def _historical_product_scores(
    historical_content: list[dict[str, Any]] | None,
) -> dict[str, float]:
    """Map normalized product names to engagement-based scores from past content."""
    scores: dict[str, float] = {}
    if not historical_content:
        return scores

    for entry in historical_content:
        if not isinstance(entry, dict):
            continue
        name = _normalize_name(_resolve_product_name(entry))
        if not name:
            continue
        views = _safe_float(entry.get("views") or entry.get("avg_views"))
        likes = _safe_float(entry.get("likes") or entry.get("avg_likes"))
        viral = _safe_float(entry.get("viral_score"))
        engagement = _clamp((views / 10000.0) * 0.5 + (likes / 1000.0) * 0.3 + (viral / 100.0) * 0.2)
        scores[name] = max(scores.get(name, 0.0), engagement)

    return scores


def _niche_alignment_score(product_name: str, niche: str) -> float:
    """Score how well a product category aligns with the creator niche."""
    niche_lower = _normalize_name(niche)
    category = infer_category(product_name)
    if category == "general" or niche_lower in ("general", ""):
        return 0.3

    hints = _NICHE_CATEGORY_HINTS.get(category, ())
    if any(hint in niche_lower for hint in hints):
        return 0.9
    if category in niche_lower:
        return 0.85

    product_lower = _normalize_name(product_name)
    niche_tokens = set(niche_lower.split())
    product_tokens = set(product_lower.split())
    overlap = len(niche_tokens & product_tokens)
    if overlap > 0:
        return _clamp(0.4 + overlap * 0.15)

    return 0.25


def _trend_signal_score(item: dict[str, Any]) -> tuple[float, list[str]]:
    """Derive demand contribution and reason codes from a single trend item."""
    reasons: list[str] = []
    viral = _safe_float(item.get("viral_score"))
    rise = _safe_float(item.get("rise_percent"))
    content_score = _safe_float(item.get("content_score"))
    demand = _safe_float(item.get("demand_score"))

    trend_component = _clamp(
        (viral / 100.0) * 0.4
        + (max(rise, 0) / 100.0) * 0.25
        + (content_score / 100.0) * 0.2
        + (demand / 100.0) * 0.15
    )

    if viral >= 30 or rise > 20 or item.get("category") == "product":
        reasons.append("trend_match")
    if rise > 50 or viral >= 50:
        reasons.append("engagement_spike")

    return trend_component, reasons


def _priority_from_demand(demand_score: float) -> str:
    if demand_score > HIGH_DEMAND_THRESHOLD:
        return "high"
    if demand_score >= MEDIUM_DEMAND_THRESHOLD:
        return "medium"
    return "low"


def _expected_revenue_score(demand_score: float, confidence: float) -> float:
    return round(_clamp(demand_score * confidence * 0.85 + demand_score * 0.15), 3)


def predictRequiredProducts(
    trends: dict[str, Any] | list[dict[str, Any]] | None,
    niche: str,
    historical_content: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Predict products likely needed for upcoming content from trend and history signals.

    Returns likely_needed_products with demand_score, confidence, and reason codes.
    Does NOT attach products.
    """
    try:
        niche = (niche or "general").strip() or "general"
        trend_items = _iter_trend_items(trends)
        historical_scores = _historical_product_scores(historical_content)

        candidates: dict[str, dict[str, Any]] = {}

        for item in trend_items:
            product_name = _resolve_product_name(item)
            if not product_name:
                keyword = (item.get("keyword") or item.get("topic") or "").strip()
                if keyword:
                    product_name = keyword
                else:
                    continue

            key = _normalize_name(product_name)
            trend_score, reasons = _trend_signal_score(item)
            hist_score = historical_scores.get(key, 0.0)

            if hist_score > 0.3:
                reasons = list(dict.fromkeys(reasons + ["engagement_spike"]))

            niche_score = _niche_alignment_score(product_name, niche)
            if niche_score >= 0.7:
                reasons = list(dict.fromkeys(reasons + ["niche_alignment"]))

            demand_score = _clamp(trend_score * 0.55 + hist_score * 0.25 + niche_score * 0.20)
            signal_count = len(reasons) + (1 if hist_score > 0 else 0)
            confidence = _clamp(0.35 + signal_count * 0.15 + demand_score * 0.25)

            existing = candidates.get(key)
            if existing:
                existing["demand_score"] = max(existing["demand_score"], demand_score)
                existing["confidence"] = max(existing["confidence"], confidence)
                existing["reason"] = list(
                    dict.fromkeys(existing["reason"] + [r for r in reasons if r in VALID_REASONS])
                )
                existing["source_items"].append(item)
            else:
                candidates[key] = {
                    "product_name": product_name,
                    "demand_score": round(demand_score, 3),
                    "confidence": round(confidence, 3),
                    "reason": [r for r in reasons if r in VALID_REASONS] or ["trend_match"],
                    "category": infer_category(product_name),
                    "source_items": [item],
                }

        likely_needed = sorted(
            candidates.values(),
            key=lambda x: (x["demand_score"], x["confidence"]),
            reverse=True,
        )

        for product in likely_needed:
            product.pop("source_items", None)

        return {
            "success": True,
            "niche": niche,
            "likely_needed_products": likely_needed,
            "prediction_count": len(likely_needed),
        }
    except Exception:
        logger.exception("Predictive product prediction failed — returning empty intent")
        return {
            "success": False,
            "niche": niche or "general",
            "likely_needed_products": [],
            "prediction_count": 0,
            "error": "prediction_failed",
        }


def precheck_catalog(
    likely_needed_products: list[dict[str, Any]],
    tiktok_shop_catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Pre-check each predicted product against the TikTok Shop catalog.

    Marks ready_to_attach or pre_add_required — never fabricates product IDs.
    Does NOT attach products.
    """
    results: list[dict[str, Any]] = []
    catalog = [c for c in (tiktok_shop_catalog or []) if isinstance(c, dict)]

    for product in likely_needed_products:
        if not isinstance(product, dict):
            continue
        product_name = (product.get("product_name") or "").strip()
        availability = checkProductAvailability(product_name, catalog)

        if availability.get("attachable") and availability.get("match_type") == "exact":
            catalog_status = "ready_to_attach"
        else:
            catalog_status = "pre_add_required"

        results.append({
            "product_name": product_name,
            "category": product.get("category") or availability.get("category") or "general",
            "demand_score": product.get("demand_score", 0.0),
            "confidence": product.get("confidence", 0.0),
            "reason": product.get("reason", []),
            "catalog_status": catalog_status,
            "availability": availability,
        })

    return results


def build_inventory_prevention_event(
    product: dict[str, Any],
    pre_check: dict[str, Any],
) -> dict[str, Any]:
    """Build the dashboard inventory_prevention_event payload."""
    demand_score = _safe_float(pre_check.get("demand_score") or product.get("demand_score"))
    confidence = _safe_float(pre_check.get("confidence") or product.get("confidence"), 0.5)
    return {
        "product_name": pre_check.get("product_name") or product.get("product_name") or "",
        "category": pre_check.get("category") or product.get("category") or "general",
        "demand_score": demand_score,
        "message": "Add this product to your TikTok Shop BEFORE posting content",
        "priority": _priority_from_demand(demand_score),
        "expected_revenue_score": _expected_revenue_score(demand_score, confidence),
    }


def run_predictive_inventory_intelligence(
    trends: dict[str, Any] | list[dict[str, Any]] | None,
    niche: str,
    historical_content: list[dict[str, Any]] | None,
    tiktok_shop_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Full predictive intelligence pass: predict → pre-check → content_mode suggestions.

    Never blocks the pipeline. Never attaches products.
    Returns must_add_products for high-demand gaps.
    """
    try:
        prediction = predictRequiredProducts(trends, niche, historical_content)
        likely_needed = prediction.get("likely_needed_products", [])
        pre_checks = precheck_catalog(likely_needed, tiktok_shop_catalog)

        prevention_events: list[dict[str, Any]] = []
        must_add_products: list[dict[str, Any]] = []
        ready_products: list[dict[str, Any]] = []
        content_mode_suggestions: list[dict[str, Any]] = []

        pre_check_by_name = {
            _normalize_name(pc.get("product_name", "")): pc for pc in pre_checks
        }

        for product in likely_needed:
            key = _normalize_name(product.get("product_name", ""))
            pre_check = pre_check_by_name.get(key, {})
            demand_score = _safe_float(product.get("demand_score"))
            availability = pre_check.get("availability") or checkProductAvailability(
                product.get("product_name", ""),
                tiktok_shop_catalog,
            )

            try:
                content_mode = resolve_content_mode(
                    product.get("product_name", ""),
                    demand_score,
                    availability,
                    tiktok_shop_catalog,
                )
            except Exception:
                logger.exception("Content mode suggestion failed for %s", product.get("product_name"))
                content_mode = generic_fallback_mode(product.get("product_name", ""))

            entry = {
                **product,
                "pre_check": pre_check,
                "content_mode": content_mode,
            }
            content_mode_suggestions.append({
                "product_name": product.get("product_name", ""),
                "demand_score": demand_score,
                "content_mode": content_mode,
            })

            if pre_check.get("catalog_status") == "ready_to_attach":
                ready_products.append(entry)
            else:
                event = build_inventory_prevention_event(product, pre_check)
                prevention_events.append(event)
                entry["inventory_prevention_event"] = event

                if demand_score > HIGH_DEMAND_THRESHOLD:
                    must_add_products.append({
                        **event,
                        "catalog_status": "pre_add_required",
                        "suggest_immediate_add": True,
                    })

        must_add_products.sort(
            key=lambda x: (x.get("demand_score", 0), x.get("expected_revenue_score", 0)),
            reverse=True,
        )

        return {
            "success": True,
            "layer": "predictive",
            "niche": niche,
            "likely_needed_products": likely_needed,
            "pre_check_results": pre_checks,
            "content_mode_suggestions": content_mode_suggestions,
            "inventory_prevention_events": prevention_events,
            "must_add_products": must_add_products,
            "ready_products": ready_products,
            "ready_count": len(ready_products),
            "pre_add_required_count": len(prevention_events),
            "high_demand_gap_count": len(must_add_products),
        }
    except Exception:
        logger.exception("Predictive inventory intelligence failed — pipeline continues")
        return {
            "success": False,
            "layer": "predictive",
            "niche": niche or "general",
            "likely_needed_products": [],
            "pre_check_results": [],
            "content_mode_suggestions": [],
            "inventory_prevention_events": [],
            "must_add_products": [],
            "ready_products": [],
            "ready_count": 0,
            "pre_add_required_count": 0,
            "high_demand_gap_count": 0,
            "error": "predictive_layer_failed",
        }


__all__ = [
    "predictRequiredProducts",
    "precheck_catalog",
    "build_inventory_prevention_event",
    "run_predictive_inventory_intelligence",
    "HIGH_DEMAND_THRESHOLD",
]
