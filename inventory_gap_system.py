"""
Inventory gap system — read-only state for live UI assembly.

Surfaces paused attachments and catalog gaps. Never raises.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"inventory_gaps": [...]} for assembleLiveState."""
    try:
        from tiktok_shop_inventory_gate import get_paused_attachments

        account = str(account_id or "").strip() or "unknown"
        paused = get_paused_attachments(account_id=account)
        if not isinstance(paused, list):
            return {"inventory_gaps": []}

        gaps = []
        for item in paused:
            if not isinstance(item, dict):
                continue
            gaps.append({
                "product_name": str(item.get("product_name") or item.get("product") or "unknown"),
                "category": str(item.get("category") or "unknown"),
                "status": str(item.get("status") or "paused"),
                "reason": str(item.get("reason") or "inventory_gap"),
                "paused_at": str(item.get("paused_at") or "unknown"),
            })
        return {"inventory_gaps": gaps}
    except Exception as exc:
        logger.warning("inventory_gap_system.get_state failed: %s", exc)
        return {"inventory_gaps": []}
