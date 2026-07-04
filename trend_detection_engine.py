"""Minimal trend detection state provider for live state assembly."""

from __future__ import annotations

from typing import Any


def get_state(account_id: str) -> dict[str, Any]:
    return {"trends": [], "account_id": account_id}
