"""
Live dashboard state derived from Supabase for the TikTok orchestration layer.

Builds live_state payload for /api/tiktok-insights and pipeline responses.
Never raises; always returns safe defaults.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from tiktok_automation_control import DEFAULT_MODE, getAutomationMode
from tiktok_system_health import compute_system_health

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_TABLE = "content_queue"
DEFAULT_STRATEGY_TABLE = "content_strategy_weights"
DEFAULT_CALIBRATION_TABLE = "virality_calibration_logs"

PENDING_STATUSES = frozenset({"pending"})
QUEUED_STATUSES = frozenset({"queued"})
APPROVED_STATUSES = frozenset({"approved"})
BLOCKED_STATUSES = frozenset({"blocked"})


def _empty_live_state() -> dict[str, Any]:
    return {
        "automation_mode": DEFAULT_MODE,
        "pending_posts": [],
        "queued_posts": [],
        "approved_posts": [],
        "blocked_posts": [],
        "last_learning_update": None,
        "system_health": "degraded",
    }


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _serialize_queue_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id") or "",
        "account_id": row.get("account_id") or "",
        "caption": row.get("caption") or "",
        "hashtags": row.get("hashtags") or [],
        "hook": row.get("hook") or "",
        "product_name": row.get("product_name") or "",
        "status": row.get("status") or "",
        "scheduled_time": row.get("scheduled_time"),
        "created_at": row.get("created_at"),
        "metadata": row.get("metadata") or {},
    }


def _fetch_queue_by_status(
    supabase,
    table: str,
    account_id: str,
    statuses: frozenset[str],
    limit: int = 50,
) -> list[dict[str, Any]]:
    try:
        response = (
            supabase.table(table)
            .select("id,account_id,caption,hashtags,hook,product_name,status,scheduled_time,created_at,metadata")
            .eq("account_id", account_id)
            .in_("status", list(statuses))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_serialize_queue_row(r) for r in (response.data or []) if isinstance(r, dict)]
    except Exception as exc:
        logger.warning("Failed to fetch queue rows for %s: %s", statuses, exc)
        return []


def _fetch_last_learning_update(supabase, account_id: str) -> str | None:
    try:
        strategy = (
            supabase.table(DEFAULT_STRATEGY_TABLE)
            .select("updated_at")
            .eq("account_id", account_id)
            .limit(1)
            .execute()
        )
        strategy_rows = strategy.data or []
        if strategy_rows and strategy_rows[0].get("updated_at"):
            return str(strategy_rows[0]["updated_at"])

        calibration = (
            supabase.table(DEFAULT_CALIBRATION_TABLE)
            .select("created_at")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        cal_rows = calibration.data or []
        if cal_rows and cal_rows[0].get("created_at"):
            return str(cal_rows[0]["created_at"])
        return None
    except Exception:
        return None


def build_live_state(
    account_id: str,
    *,
    apify_feedback: dict[str, Any] | None = None,
    queue_result: dict[str, Any] | None = None,
    learning_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build live_state dict for dashboard and API responses.

    Derived from Supabase; safe defaults on any failure.
    """
    state = _empty_live_state()
    account = str(account_id or "").strip()
    if not account:
        return state

    try:
        state["automation_mode"] = getAutomationMode(account)
    except Exception:
        pass

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            state["system_health"] = compute_system_health(
                account_id=account,
                apify_feedback=apify_feedback,
                queue_result=queue_result,
                learning_result=learning_result,
            )
            return state

        table = os.getenv("CONTENT_QUEUE_TABLE", DEFAULT_QUEUE_TABLE)
        state["pending_posts"] = _fetch_queue_by_status(supabase, table, account, PENDING_STATUSES)
        state["queued_posts"] = _fetch_queue_by_status(supabase, table, account, QUEUED_STATUSES)
        state["approved_posts"] = _fetch_queue_by_status(supabase, table, account, APPROVED_STATUSES)
        state["blocked_posts"] = _fetch_queue_by_status(supabase, table, account, BLOCKED_STATUSES)
        state["last_learning_update"] = _fetch_last_learning_update(supabase, account)
        state["system_health"] = compute_system_health(
            account_id=account,
            apify_feedback=apify_feedback,
            queue_result=queue_result,
            learning_result=learning_result,
        )
        return state

    except Exception as exc:
        logger.warning("build_live_state failed for %s: %s", account, exc)
        state["system_health"] = compute_system_health(
            account_id=account,
            apify_feedback=apify_feedback,
            queue_result=queue_result,
            learning_result=learning_result,
        )
        return state
