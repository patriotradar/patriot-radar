"""
Live state assembly layer for TikTok SaaS frontend consumption.

Core pipeline always runs: trend → content → plan → insights
Commerce pipeline is optional add-on gated by features.commerce_mode.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _empty_contract(commerce_mode: bool = False) -> dict[str, Any]:
    core_step = "trend → content → plan → insights"
    commerce_step = "trend → product → content → queue"
    return {
        "features": {
            "commerce_mode": bool(commerce_mode),
        },
        "today_flow": {
            "step": commerce_step if commerce_mode else core_step,
            "next_action": "Run trend scan" if not commerce_mode else "Match products to trends",
            "status": "ready",
        },
        "trends": [],
        "products": [],
        "inventory_gaps": [],
        "inventory_prevention": [],
        "content_queue": [],
        "approvals": [],
        "performance": {},
        "alerts": [],
        "revenue_suggestions": [],
        "primary_action": {
            "label": "View content plan",
            "action": "view_plan",
            "context_id": "plan",
        },
        "system_health": "healthy",
    }


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_get_trends(account_id: str) -> list[dict[str, Any]]:
    """Core trend signals — always attempted, never raises."""
    try:
        from trend_intelligence_store import fetch_recent_signals

        rows = fetch_recent_signals(account_id, limit=20)
        if isinstance(rows, list) and rows:
            return [
                {
                    "id": r.get("id", ""),
                    "summary": r.get("topic") or r.get("keyword") or "",
                    "keyword": r.get("keyword") or r.get("topic") or "",
                    "signal_strength": r.get("signal_strength") or r.get("viral_score") or 0,
                    "trend_state": r.get("trend_state", "emerging"),
                }
                for r in rows
                if isinstance(r, dict)
            ]
    except Exception as exc:
        logger.debug("Core trend fetch unavailable: %s", exc)

    return []


def _derive_core_flow(trends: list, commerce_mode: bool) -> dict[str, str]:
    if trends:
        return {
            "step": "trend → product → content → queue" if commerce_mode else "trend → content → plan → insights",
            "next_action": "Review trending topics in your plan" if not commerce_mode else "Match products to active trends",
            "status": "trend_detected",
        }
    return {
        "step": "trend → content → plan → insights" if not commerce_mode else "trend → product → content → queue",
        "next_action": "Run trend scan to refresh signals",
        "status": "ready",
    }


def assembleLiveState(account_id: str, *, commerce_mode: bool = False) -> dict[str, Any]:
    """
    Assemble the strict UI contract.

    Never raises. Never returns null. Core fields always present.
    Commerce fields populated only when commerce_mode=True.
    """
    state = _empty_contract(commerce_mode)
    account = str(account_id or "").strip() or "default"

    trends = _safe_get_trends(account)
    state["trends"] = trends
    state["today_flow"] = _derive_core_flow(trends, commerce_mode)

    if not commerce_mode:
        state["primary_action"] = {
            "label": "View content plan",
            "action": "view_plan",
            "context_id": "plan",
        }
        return state

    try:
        from commerce import run_commerce_pipeline

        catalog: list[dict[str, Any]] = []
        try:
            import json
            from pathlib import Path

            catalog_path = Path(__file__).resolve().parent / "data" / "tiktok_shop_sample_catalog.json"
            if catalog_path.exists():
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                if not isinstance(catalog, list):
                    catalog = []
        except Exception:
            catalog = []

        commerce = run_commerce_pipeline(account, trends, catalog=catalog)
        state["products"] = _as_list(commerce.get("products"))
        state["inventory_gaps"] = _as_list(commerce.get("inventory_gaps"))
        state["content_queue"] = _as_list(commerce.get("queue_enhancements"))
        state["revenue_suggestions"] = _as_list(commerce.get("revenue_suggestions"))

        gaps = state["inventory_gaps"]
        if gaps:
            state["alerts"] = [
                {
                    "type": "inventory_gap",
                    "message": g.get("message", "Product missing from TikTok Shop Showcase"),
                }
                for g in gaps[:5]
                if isinstance(g, dict)
            ]
            state["today_flow"] = {
                "step": "trend → product → content → queue",
                "next_action": "Resolve inventory gaps in TikTok Shop",
                "status": "inventory_gap",
            }
            state["primary_action"] = {
                "label": "Fix inventory gap",
                "action": "view_inventory",
                "context_id": gaps[0].get("product_name", "inventory") if gaps else "inventory",
            }
        elif state["products"]:
            state["today_flow"] = {
                "step": "trend → product → content → queue",
                "next_action": "Generate content from detected products",
                "status": "ready_for_content",
            }
            state["primary_action"] = {
                "label": "View products",
                "action": "view_products",
                "context_id": state["products"][0].get("name", "products") if state["products"] else "products",
            }
    except Exception as exc:
        logger.warning("Commerce layer failed for %s (core unaffected): %s", account, exc)
        state["alerts"] = [{
            "type": "commerce_degraded",
            "message": "Commerce module unavailable — core content features still active",
        }]

    return state
