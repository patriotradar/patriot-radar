"""
Content approval engine for the TikTok viral loop dashboard.

approveQueuedContent updates content_queue.status only — rows are never deleted.
Never raises; returns a safe result dict on all paths.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_TABLE = "content_queue"
VALID_DECISIONS = frozenset({"approve", "reject", "queue"})
DECISION_TO_STATUS = {
    "approve": "approved",
    "reject": "blocked",
}


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        logger.warning("Supabase credentials missing; content approval skipped.")
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _empty_result() -> dict[str, Any]:
    return {
        "success": False,
        "content_id": "",
        "decision": "",
        "status": "",
        "error": None,
    }


def approveQueuedContent(content_id: str, decision: str) -> dict[str, Any]:
    """
    Apply approval decision to queued content.

    Decisions:
      - approve → status "approved"
      - reject  → status "blocked"
      - queue   → leave unchanged

    Never raises; if Supabase fails, does nothing safely.
    """
    result = _empty_result()
    cid = str(content_id or "").strip()
    dec = str(decision or "").strip().lower()

    result["content_id"] = cid
    result["decision"] = dec

    if not cid:
        result["error"] = "missing_content_id"
        return result

    if dec not in VALID_DECISIONS:
        result["error"] = "invalid_decision"
        return result

    if dec == "queue":
        result["success"] = True
        result["status"] = "unchanged"
        return result

    new_status = DECISION_TO_STATUS[dec]
    result["status"] = new_status

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            result["error"] = "missing_supabase_credentials"
            return result

        table = os.getenv("CONTENT_QUEUE_TABLE", DEFAULT_QUEUE_TABLE)
        response = (
            supabase.table(table)
            .update({"status": new_status})
            .eq("id", cid)
            .execute()
        )
        rows = response.data or []
        if not rows:
            result["error"] = "content_not_found"
            return result

        result["success"] = True
        result["status"] = str(rows[0].get("status") or new_status)
        return result

    except Exception as exc:
        logger.warning("approveQueuedContent failed for %s: %s", cid, exc)
        result["error"] = str(exc)
        return result
