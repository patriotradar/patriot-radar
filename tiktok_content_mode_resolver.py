"""
TikTok Shop content mode resolver — Step 2 in the dual-layer inventory pipeline.

Predictive layer produces intent signals; this module resolves content_mode for
generation. Reactive gate NEVER overrides the resolved mode.

Hierarchy:
  PREDICTIVE LAYER = intent decision (via demand_score + availability pre-check)
  REACTIVE LAYER  = final attachment safety only (separate module)
"""

from __future__ import annotations

import logging
from typing import Any

from tiktok_shop_inventory_gate import checkProductAvailability, infer_category

logger = logging.getLogger(__name__)

HIGH_DEMAND_THRESHOLD = 0.7
GENERIC_FALLBACK_MODE = "generic"

VALID_MODES = frozenset({
    "product_specific",
    "category_substitute",
    "generic_high_priority",
    GENERIC_FALLBACK_MODE,
})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_category_substitute(
    product_name: str,
    tiktok_shop_catalog: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find an attachable catalog product in the same category for content framing."""
    availability = checkProductAvailability(product_name, tiktok_shop_catalog)
    if availability.get("attachable") and availability.get("match_type") == "category":
        return {
            "product_name": availability.get("matched_name") or product_name,
            "product_id": availability.get("product_id"),
            "category": availability.get("category"),
            "substitution_type": "category",
        }
    return None


def resolve_content_mode(
    product_name: str,
    demand_score: float,
    availability: dict[str, Any] | None,
    tiktok_shop_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Resolve content_mode from predictive intent signals.

    IF product exists in catalog:
        mode = product_specific
    IF product missing AND demand_score < 0.7:
        mode = category_substitute
    IF product missing AND demand_score >= 0.7:
        mode = generic_high_priority

    Fail-safe: always returns a valid mode; falls back to generic on error.
    """
    product_name = (product_name or "").strip()
    demand_score = _safe_float(demand_score)

    try:
        avail = availability or checkProductAvailability(product_name, tiktok_shop_catalog)

        if avail.get("attachable") and avail.get("match_type") == "exact":
            return {
                "mode": "product_specific",
                "product_name": avail.get("matched_name") or product_name,
                "product_id": avail.get("product_id"),
                "demand_score": demand_score,
                "pause_product_attachment": False,
                "resolved_by": "content_mode_resolver",
            }

        if demand_score >= HIGH_DEMAND_THRESHOLD:
            return {
                "mode": "generic_high_priority",
                "product_name": product_name,
                "product_id": None,
                "demand_score": demand_score,
                "pause_product_attachment": True,
                "high_priority": True,
                "fallback_reason": "high_demand_missing_product",
                "resolved_by": "content_mode_resolver",
            }

        substitute = find_category_substitute(product_name, tiktok_shop_catalog)
        if substitute:
            return {
                "mode": "category_substitute",
                "product_name": substitute["product_name"],
                "product_id": substitute["product_id"],
                "original_product_name": product_name,
                "substitution_type": substitute.get("substitution_type", "category"),
                "demand_score": demand_score,
                "pause_product_attachment": False,
                "resolved_by": "content_mode_resolver",
            }

        return {
            "mode": "category_substitute",
            "product_name": product_name,
            "product_id": None,
            "category": infer_category(product_name),
            "demand_score": demand_score,
            "pause_product_attachment": False,
            "substitution_type": "category_framing_only",
            "resolved_by": "content_mode_resolver",
        }
    except Exception:
        logger.exception("Content mode resolution failed for %r — falling back to generic", product_name)
        return generic_fallback_mode(product_name)


def generic_fallback_mode(product_name: str = "") -> dict[str, Any]:
    """Universal fail-safe content mode when prediction or resolution fails."""
    return {
        "mode": GENERIC_FALLBACK_MODE,
        "product_name": product_name,
        "product_id": None,
        "pause_product_attachment": True,
        "fallback_reason": "resolver_fail_safe",
        "resolved_by": "content_mode_resolver",
    }


def mode_allows_attachment(content_mode: dict[str, Any]) -> bool:
    """Whether predictive framing permits a reactive attachment attempt."""
    mode = content_mode.get("mode", GENERIC_FALLBACK_MODE)
    if mode in (GENERIC_FALLBACK_MODE, "generic_high_priority"):
        return False
    if content_mode.get("pause_product_attachment"):
        return False
    return True


__all__ = [
    "HIGH_DEMAND_THRESHOLD",
    "GENERIC_FALLBACK_MODE",
    "VALID_MODES",
    "find_category_substitute",
    "resolve_content_mode",
    "generic_fallback_mode",
    "mode_allows_attachment",
]
