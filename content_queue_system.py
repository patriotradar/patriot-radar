"""
Content queue system — read-only state for live UI assembly.

Fetches content_queue rows for an account. Never raises.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_TABLE = "content_queue"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "account_id": str(row.get("account_id") or ""),
        "caption": str(row.get("caption") or "unknown"),
        "hashtags": row.get("hashtags") if isinstance(row.get("hashtags"), list) else [],
        "hook": str(row.get("hook") or "unknown"),
        "product_name": str(row.get("product_name") or "unknown"),
        "status": str(row.get("status") or "unknown"),
        "scheduled_time": str(row.get("scheduled_time") or "unknown"),
        "created_at": str(row.get("created_at") or "unknown"),
    }


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"content_queue": [...]} for assembleLiveState."""
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {"content_queue": []}

        account = str(account_id or "").strip()
        if not account:
            return {"content_queue": []}

        table = os.getenv("CONTENT_QUEUE_TABLE", DEFAULT_QUEUE_TABLE)
        response = (
            supabase.table(table)
            .select("id,account_id,caption,hashtags,hook,product_name,status,scheduled_time,created_at")
            .eq("account_id", account)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = response.data or []
        return {"content_queue": [_serialize_row(r) for r in rows if isinstance(r, dict)]}
    except Exception as exc:
        logger.warning("content_queue_system.get_state failed: %s", exc)
        return {"content_queue": []}
