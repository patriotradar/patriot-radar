"""
Performance tracker — read-only state for live UI assembly.

Fetches content performance snapshots. Never raises.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PERFORMANCE_TABLE = "content_performance"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"performance": {...}} for assembleLiveState."""
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {"performance": {}}

        account = str(account_id or "").strip()
        if not account:
            return {"performance": {}}

        table = os.getenv("CONTENT_PERFORMANCE_TABLE", DEFAULT_PERFORMANCE_TABLE)
        response = (
            supabase.table(table)
            .select("content_id,performance_metrics,timestamp")
            .eq("account_id", account)
            .order("timestamp", desc=True)
            .limit(25)
            .execute()
        )
        rows = response.data or []
        snapshots = []
        total_views = 0
        total_engagement = 0.0
        count = 0

        for row in rows:
            if not isinstance(row, dict):
                continue
            metrics = row.get("performance_metrics") or {}
            if not isinstance(metrics, dict):
                metrics = {}
            views = metrics.get("views") or 0
            rate = metrics.get("engagement_rate") or 0
            total_views += int(views) if views else 0
            total_engagement += float(rate) if rate else 0.0
            count += 1
            snapshots.append({
                "content_id": str(row.get("content_id") or ""),
                "metrics": metrics,
                "timestamp": str(row.get("timestamp") or "unknown"),
            })

        return {
            "performance": {
                "snapshot_count": count,
                "total_views": total_views,
                "avg_engagement_rate": round(total_engagement / max(count, 1), 4),
                "snapshots": snapshots,
            }
        }
    except Exception as exc:
        logger.warning("performance_tracker.get_state failed: %s", exc)
        return {"performance": {}}
