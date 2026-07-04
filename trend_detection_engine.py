"""
Trend detection engine — read-only state for live UI assembly.

Fetches recent trend signals from Supabase. Never raises.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_FEED_TABLE = "trend_intelligence_feed"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"trends": [...]} for assembleLiveState."""
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {"trends": []}

        table = os.getenv("TREND_INTELLIGENCE_TABLE", DEFAULT_FEED_TABLE)
        response = (
            supabase.table(table)
            .select("timestamp,source,type,signal_strength,virality_score,trend_state,summary,raw_data")
            .eq("source", "tiktok")
            .order("timestamp", desc=True)
            .limit(50)
            .execute()
        )
        rows = response.data or []
        trends = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            trends.append({
                "id": str(row.get("dedupe_key") or row.get("summary") or ""),
                "type": str(row.get("type") or "unknown"),
                "signal_strength": row.get("signal_strength") or 0,
                "virality_score": row.get("virality_score") or 0,
                "trend_state": str(row.get("trend_state") or "unknown"),
                "summary": str(row.get("summary") or "unknown"),
                "timestamp": str(row.get("timestamp") or "unknown"),
                "account_id": str(account_id or "unknown"),
            })
        return {"trends": trends}
    except Exception as exc:
        logger.warning("trend_detection_engine.get_state failed: %s", exc)
        return {"trends": []}
