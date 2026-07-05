"""Trend detection engine — aggregates multi-source trend intelligence."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_state(account_id: str = "") -> dict[str, Any]:
    """
    Return aggregated trend state from historical store and local cache.
    Safe stub replacement — never raises.
    """
    trends: list[dict[str, Any]] = []
    status: dict[str, Any] = {}

    try:
        from trend_intelligence_engine.engine import TrendIntelligenceEngine

        status = TrendIntelligenceEngine.load_status()
    except Exception as exc:
        logger.warning("TrendIntelligenceEngine.load_status failed: %s", exc)
        status = {"health_status": "degraded", "warnings": [str(exc)]}

    try:
        from trend_intelligence_engine.historical_store import query_supabase_table

        rows = query_supabase_table(
            "trend_intelligence_history",
            select="keyword,trend,source,popularity,opportunity_score,created_at,summary",
            order="created_at.desc",
            limit=25,
        )
        if not rows:
            rows = query_supabase_table(
                "trend_intelligence_feed",
                select="summary,source,signal_strength,virality_score,created_at,raw_data",
                order="created_at.desc",
                limit=25,
            )
        for row in rows:
            trends.append(
                {
                    "keyword": row.get("keyword") or row.get("summary") or "",
                    "source": row.get("source", "unknown"),
                    "signal_strength": row.get("popularity") or row.get("signal_strength") or 0,
                    "virality_score": row.get("opportunity_score") or row.get("virality_score") or 0,
                    "summary": row.get("summary") or row.get("keyword") or row.get("trend") or "",
                    "timestamp": row.get("created_at"),
                }
            )
    except Exception as exc:
        logger.warning("Historical trend fetch failed: %s", exc)

    if not trends:
        cache = None
        try:
            from trend_intelligence_engine.engine import TrendIntelligenceEngine

            cache = TrendIntelligenceEngine.load_cache()
        except Exception:
            pass
        if cache:
            for item in (cache.get("trends") or [])[:20]:
                trends.append(
                    {
                        "keyword": item.get("keyword") or item.get("trend") or "",
                        "source": item.get("source", "cache"),
                        "signal_strength": item.get("popularity", 0),
                        "virality_score": item.get("opportunity", {}).get("opportunity_score", 0),
                        "summary": item.get("keyword") or item.get("trend") or "",
                        "timestamp": item.get("timestamp"),
                    }
                )

    return {
        "trends": trends,
        "account_id": account_id,
        "trend_intelligence_status": status,
        "provider_count_online": len(status.get("providers_online") or []),
    }
