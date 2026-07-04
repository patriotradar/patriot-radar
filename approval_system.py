"""
Approval system — read-only state for live UI assembly.

Lists content awaiting approval. Never raises.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_TABLE = "content_queue"
PENDING_STATUSES = frozenset({"pending", "queued"})


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"approvals": [...]} for assembleLiveState."""
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {"approvals": []}

        account = str(account_id or "").strip()
        if not account:
            return {"approvals": []}

        table = os.getenv("CONTENT_QUEUE_TABLE", DEFAULT_QUEUE_TABLE)
        response = (
            supabase.table(table)
            .select("id,account_id,caption,product_name,status,created_at")
            .eq("account_id", account)
            .in_("status", list(PENDING_STATUSES))
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        )
        rows = response.data or []
        approvals = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            approvals.append({
                "content_id": str(row.get("id") or ""),
                "caption": str(row.get("caption") or "unknown"),
                "product_name": str(row.get("product_name") or "unknown"),
                "status": str(row.get("status") or "unknown"),
                "created_at": str(row.get("created_at") or "unknown"),
            })
        return {"approvals": approvals}
    except Exception as exc:
        logger.warning("approval_system.get_state failed: %s", exc)
        return {"approvals": []}
