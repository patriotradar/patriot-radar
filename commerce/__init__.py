"""
Optional commerce layer for TikTok SaaS.

Core content pipeline (trend → content → plan → insights) never depends on this module.
All entry points are fail-safe: they never raise and return empty defaults on error.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

COMMERCE_PIPELINE_STEPS = (
    "product_detection",
    "match",
    "attach",
    "queue_enhancement",
)


def is_commerce_enabled(commerce_mode: bool | None) -> bool:
    return commerce_mode is True


def _safe_step(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("commerce pipeline step failed: %s", exc)
        return None


def run_commerce_pipeline(
    account_id: str,
    trends: list[dict[str, Any]] | None = None,
    *,
    catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Optional add-on pipeline: product detection → match → attach → queue enhancement.

    Never raises. Core content generation can proceed without calling this.
    """
    empty: dict[str, Any] = {
        "products": [],
        "inventory_gaps": [],
        "attachments": [],
        "queue_enhancements": [],
        "revenue_suggestions": [],
        "pipeline_status": "skipped",
    }

    try:
        from commerce.product_detection import detect_products_from_trends
        from commerce.shop_attachment import attach_products_to_content
        from commerce.queue_enhancement import enhance_content_queue

        trend_list = trends if isinstance(trends, list) else []
        products = _safe_step(detect_products_from_trends, trend_list) or []
        attachments, gaps = _safe_step(
            attach_products_to_content,
            account_id,
            products,
            catalog or [],
        ) or ([], [])
        queue_items = _safe_step(enhance_content_queue, account_id, attachments or []) or []
        revenue = _build_revenue_suggestions(products, attachments or [])

        return {
            "products": products if isinstance(products, list) else [],
            "inventory_gaps": gaps if isinstance(gaps, list) else [],
            "attachments": attachments if isinstance(attachments, list) else [],
            "queue_enhancements": queue_items if isinstance(queue_items, list) else [],
            "revenue_suggestions": revenue,
            "pipeline_status": "complete",
        }
    except Exception as exc:
        logger.warning("run_commerce_pipeline failed for %s: %s", account_id, exc)
        empty["pipeline_status"] = "failed"
        return empty


def _build_revenue_suggestions(
    products: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    attached = {a.get("product_name", "").lower() for a in attachments if isinstance(a, dict)}
    for product in products[:5]:
        if not isinstance(product, dict):
            continue
        name = str(product.get("name") or product.get("product_name") or "").strip()
        if not name:
            continue
        if name.lower() in attached:
            suggestions.append({
                "product": name,
                "action": "Pin product link in video comments",
                "expected_outcome": "Commission on viewer purchases",
            })
        else:
            suggestions.append({
                "product": name,
                "action": "Add to TikTok Shop Showcase, then attach",
                "expected_outcome": "Unlock affiliate revenue on this trend",
            })
    return suggestions
