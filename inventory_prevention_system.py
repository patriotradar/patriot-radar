"""
Inventory prevention system — read-only state for live UI assembly.

Surfaces proactive inventory prevention events. Never raises.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"inventory_prevention": [...]} for assembleLiveState."""
    try:
        from tiktok_inventory_predictor import predictRequiredProducts

        account = str(account_id or "").strip() or "unknown"
        result = predictRequiredProducts(trends={"items": []}, niche=account)
        items = result.get("likely_needed_products") if isinstance(result, dict) else []
        if not isinstance(items, list):
            return {"inventory_prevention": []}

        prevention = []
        for item in items:
            if not isinstance(item, dict):
                continue
            reason = item.get("reason")
            if isinstance(reason, list):
                reason_text = str(reason[0]) if reason else "unknown"
            else:
                reason_text = str(reason or "unknown")
            prevention.append({
                "product_name": str(item.get("product_name") or item.get("product") or "unknown"),
                "demand_score": item.get("demand_score") or 0,
                "priority": str(item.get("priority") or "unknown"),
                "reason": reason_text,
                "available": bool(item.get("available", True)),
            })
        return {"inventory_prevention": prevention}
    except Exception as exc:
        logger.warning("inventory_prevention_system.get_state failed: %s", exc)
        return {"inventory_prevention": []}
