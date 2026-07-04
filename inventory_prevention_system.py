"""Minimal inventory prevention state provider."""

from __future__ import annotations

from typing import Any


def get_state(account_id: str) -> dict[str, Any]:
    return {"inventory_prevention": [], "account_id": account_id}
