"""Minimal system health monitor state provider."""

from __future__ import annotations

from typing import Any


def get_state(account_id: str) -> dict[str, Any]:
    return {
        "system_health": "healthy",
        "raw_logs": [],
        "account_id": account_id,
    }
