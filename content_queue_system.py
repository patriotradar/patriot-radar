"""Minimal content queue state provider."""

from __future__ import annotations

from typing import Any


def get_state(account_id: str) -> dict[str, Any]:
    return {"content_queue": [], "account_id": account_id}
