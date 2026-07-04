"""
Learning engine — read-only state for live UI assembly.

Fetches strategy weights and learning metadata. Never raises.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY_TABLE = "content_strategy_weights"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def get_state(account_id: str) -> dict[str, Any]:
    """Return learning metadata for assembleLiveState."""
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {"learning": {}}

        account = str(account_id or "").strip()
        if not account:
            return {"learning": {}}

        table = os.getenv("CONTENT_STRATEGY_TABLE", DEFAULT_STRATEGY_TABLE)
        response = (
            supabase.table(table)
            .select("weights,updated_at,sample_count")
            .eq("account_id", account)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return {"learning": {}}

        row = rows[0]
        weights = row.get("weights") or {}
        if not isinstance(weights, dict):
            weights = {}

        return {
            "learning": {
                "weights": weights,
                "last_updated": str(row.get("updated_at") or "unknown"),
                "sample_count": row.get("sample_count") or 0,
            }
        }
    except Exception as exc:
        logger.warning("learning_engine.get_state failed: %s", exc)
        return {"learning": {}}
