"""
System health monitor — read-only state for live UI assembly.

Wraps tiktok_system_health. Never raises.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"system_health": str} for assembleLiveState."""
    try:
        from tiktok_system_health import compute_system_health

        account = str(account_id or "").strip()
        health = compute_system_health(account_id=account)
        return {"system_health": str(health or "unknown")}
    except Exception as exc:
        logger.warning("system_health_monitor.get_state failed: %s", exc)
        return {"system_health": "unknown"}
