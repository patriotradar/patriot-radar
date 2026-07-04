"""
Live system health indicator for the TikTok viral loop dashboard.

Computes healthy | degraded | failing from Supabase, Apify, queue, and learning signals.
Never raises; never blocks pipeline execution.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_TABLE = "content_queue"
DEFAULT_CALIBRATION_TABLE = "virality_calibration_logs"
DEFAULT_STRATEGY_TABLE = "content_strategy_weights"

HEALTHY = "healthy"
DEGRADED = "degraded"
FAILING = "failing"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _check_supabase_available() -> bool:
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return False
        supabase.table(DEFAULT_QUEUE_TABLE).select("id").limit(1).execute()
        return True
    except Exception:
        return False


def _queue_failure_rate(supabase, account_id: str | None = None) -> float:
    try:
        query = supabase.table(DEFAULT_QUEUE_TABLE).select("status")
        if account_id:
            query = query.eq("account_id", account_id)
        response = query.limit(200).execute()
        rows = response.data or []
        if not rows:
            return 0.0
        failed = sum(1 for r in rows if r.get("status") == "failed")
        return failed / len(rows)
    except Exception:
        return 0.0


def _learning_success_rate(supabase) -> float:
    try:
        response = (
            supabase.table(DEFAULT_CALIBRATION_TABLE)
            .select("id")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        rows = response.data or []
        if not rows:
            response = (
                supabase.table(DEFAULT_STRATEGY_TABLE)
                .select("account_id")
                .limit(1)
                .execute()
            )
            return 1.0 if (response.data or []) else 0.5
        return 1.0
    except Exception:
        return 0.5


def _apify_success_rate(apify_feedback: dict[str, Any] | None) -> float:
    if not apify_feedback:
        return 1.0
    if apify_feedback.get("success") is True:
        return 1.0
    if apify_feedback.get("success") is False:
        source = str(apify_feedback.get("source") or "")
        if source == "sample_fallback":
            return 0.7
        return 0.0
    return 0.8


def compute_system_health(
    *,
    account_id: str = "",
    apify_feedback: dict[str, Any] | None = None,
    queue_result: dict[str, Any] | None = None,
    learning_result: dict[str, Any] | None = None,
) -> str:
    """
    Return system_health: healthy | degraded | failing.

    Never raises; defaults to degraded when uncertain.
    """
    try:
        supabase_ok = _check_supabase_available()
        apify_rate = _apify_success_rate(apify_feedback)

        queue_fail_rate = 0.0
        if supabase_ok:
            supabase = _get_supabase_client()
            account = str(account_id or "").strip() or None
            queue_fail_rate = _queue_failure_rate(supabase, account)

        if queue_result and queue_result.get("error"):
            queue_fail_rate = max(queue_fail_rate, 0.5)

        learning_rate = 1.0
        if learning_result and learning_result.get("error"):
            learning_rate = 0.0
        elif supabase_ok:
            learning_rate = _learning_success_rate(_get_supabase_client())

        if not supabase_ok:
            return FAILING

        if apify_rate < 0.3 or queue_fail_rate > 0.5 or learning_rate < 0.3:
            return FAILING

        if apify_rate < 0.8 or queue_fail_rate > 0.2 or learning_rate < 0.8:
            return DEGRADED

        return HEALTHY

    except Exception as exc:
        logger.warning("compute_system_health failed: %s", exc)
        return DEGRADED


def build_health_details(
    *,
    account_id: str = "",
    apify_feedback: dict[str, Any] | None = None,
    queue_result: dict[str, Any] | None = None,
    learning_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extended health payload for dashboard diagnostics."""
    return {
        "system_health": compute_system_health(
            account_id=account_id,
            apify_feedback=apify_feedback,
            queue_result=queue_result,
            learning_result=learning_result,
        ),
        "supabase_available": _check_supabase_available(),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
