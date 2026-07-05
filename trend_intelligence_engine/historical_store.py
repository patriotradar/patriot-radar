"""Historical trend storage in Supabase."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from trend_intelligence_engine.types import NormalizedTrendResult, utc_now_iso

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_TABLE = "trend_intelligence_history"
DEFAULT_SCAN_TABLE = "trend_intelligence_scans"
DEFAULT_RECOMMENDATIONS_TABLE = "trend_recommendations"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    )
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def query_supabase_table(
    table: str,
    *,
    select: str = "*",
    order: str = "created_at.desc",
    limit: int = 50,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Safe Supabase read — returns [] on failure."""
    try:
        client = _get_supabase_client()
        if client is None:
            return []
        query = client.table(table).select(select).order(
            order.split(".")[0], desc=order.endswith(".desc")
        ).limit(limit)
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        response = query.execute()
        return response.data or []
    except Exception as exc:
        logger.warning("Supabase query %s failed: %s", table, exc)
        return []


def trend_result_to_history_row(result: NormalizedTrendResult) -> dict[str, Any]:
    """Map normalized result to history table row."""
    opp = result.opportunity
    ci = result.content_intelligence
    return {
        "created_at": result.timestamp or utc_now_iso(),
        "trend": result.trend[:500] if result.trend else "",
        "keyword": result.keyword[:500] if result.keyword else "",
        "source": result.source,
        "niche": result.niche,
        "popularity": int(min(100, max(0, result.popularity))),
        "buying_intent": int(min(100, max(0, result.buying_intent))),
        "competition": int(min(100, max(0, result.competition))),
        "opportunity_score": opp.opportunity_score if opp else 0,
        "category": result.category,
        "sentiment": result.sentiment,
        "related_creators": result.related_creators,
        "recommended_content": result.recommended_content or ci.to_dict(),
        "content_intelligence": ci.to_dict(),
        "opportunity_scores": opp.to_dict() if opp else {},
        "signal_type": result.signal_type,
        "raw_data": result.raw_data,
        "dedupe_key": result.dedupe_key or f"{result.source}:{result.keyword}".lower()[:120],
        "summary": (result.content_intelligence.hook or result.trend or result.keyword)[:500],
    }


def store_history_rows(
    results: list[NormalizedTrendResult],
    table: str | None = None,
) -> dict[str, Any]:
    """Upsert historical trend rows. Never raises."""
    table_name = table or os.getenv("TREND_HISTORY_TABLE", DEFAULT_HISTORY_TABLE)
    if not results:
        return {"stored": 0, "skipped": 0, "error": None}

    try:
        client = _get_supabase_client()
        if client is None:
            return {"stored": 0, "skipped": len(results), "error": "missing_supabase_credentials"}

        stored = 0
        failed = 0
        last_error: str | None = None
        for result in results:
            row = trend_result_to_history_row(result)
            try:
                client.table(table_name).upsert(row, on_conflict="dedupe_key").execute()
                stored += 1
            except Exception as exc:
                failed += 1
                last_error = str(exc)
                logger.error("History upsert failed for %s: %s", row.get("dedupe_key"), exc)

        return {
            "stored": stored,
            "skipped": failed,
            "error": None if failed == 0 else last_error,
            "table": table_name,
        }
    except Exception as exc:
        logger.exception("store_history_rows failed: %s", exc)
        return {"stored": 0, "skipped": len(results), "error": str(exc)}


def store_scan_metadata(
    *,
    niche: str,
    providers_online: list[str],
    providers_offline: list[str],
    trend_count: int,
    opportunity_count: int,
    warnings: list[str],
    table: str | None = None,
) -> dict[str, Any]:
    """Record scan run metadata for dashboard status."""
    table_name = table or os.getenv("TREND_SCAN_TABLE", DEFAULT_SCAN_TABLE)
    row = {
        "scanned_at": utc_now_iso(),
        "niche": niche,
        "providers_online": providers_online,
        "providers_offline": providers_offline,
        "trend_count": trend_count,
        "opportunity_count": opportunity_count,
        "warnings": warnings,
        "health_status": "healthy" if providers_online else "degraded",
    }
    try:
        client = _get_supabase_client()
        if client is None:
            return {"stored": 0, "error": "missing_supabase_credentials"}
        client.table(table_name).insert(row).execute()
        return {"stored": 1, "error": None, "table": table_name}
    except Exception as exc:
        logger.warning("store_scan_metadata failed: %s", exc)
        return {"stored": 0, "error": str(exc)}


def store_recommendations(
    recommendations: dict[str, Any],
    niche: str,
    table: str | None = None,
) -> dict[str, Any]:
    """Persist AI/rule-based recommendations snapshot."""
    table_name = table or os.getenv("TREND_RECOMMENDATIONS_TABLE", DEFAULT_RECOMMENDATIONS_TABLE)
    row = {
        "created_at": utc_now_iso(),
        "niche": niche,
        "recommendations": recommendations,
        "version": "1",
    }
    try:
        client = _get_supabase_client()
        if client is None:
            return {"stored": 0, "error": "missing_supabase_credentials"}
        client.table(table_name).insert(row).execute()
        return {"stored": 1, "error": None}
    except Exception as exc:
        logger.warning("store_recommendations failed: %s", exc)
        return {"stored": 0, "error": str(exc)}


def fetch_latest_scan(table: str | None = None) -> dict[str, Any] | None:
    """Return most recent scan metadata row."""
    table_name = table or os.getenv("TREND_SCAN_TABLE", DEFAULT_SCAN_TABLE)
    rows = query_supabase_table(table_name, order="scanned_at.desc", limit=1)
    return rows[0] if rows else None


def fetch_latest_recommendations(niche: str | None = None, table: str | None = None) -> dict[str, Any] | None:
    table_name = table or os.getenv("TREND_RECOMMENDATIONS_TABLE", DEFAULT_RECOMMENDATIONS_TABLE)
    rows = query_supabase_table(table_name, order="created_at.desc", limit=5)
    if niche:
        for row in rows:
            if (row.get("niche") or "").lower() == niche.lower():
                return row
    return rows[0] if rows else None


def normalized_to_feed_rows(results: list[NormalizedTrendResult]) -> list[dict[str, Any]]:
    """Convert normalized results to trend_intelligence_feed compatible rows."""
    rows: list[dict[str, Any]] = []
    for result in results[:100]:
        strength = int(min(100, max(0, result.popularity)))
        viral = int(min(100, max(0, result.opportunity.opportunity_score if result.opportunity else strength)))
        trend_state = "rising" if strength >= 50 else "emerging"
        if strength >= 75:
            trend_state = "peaking"
        rows.append(
            {
                "created_at": result.timestamp or utc_now_iso(),
                "source": result.source,
                "type": result.signal_type or "trend",
                "signal_strength": strength,
                "virality_score": viral,
                "trend_state": trend_state,
                "raw_data": {
                    **result.raw_data,
                    "keyword": result.keyword,
                    "trend": result.trend,
                    "niche": result.niche,
                    "buying_intent": result.buying_intent,
                    "opportunity": result.opportunity.to_dict() if result.opportunity else {},
                    "content_intelligence": result.content_intelligence.to_dict(),
                },
                "summary": (result.content_intelligence.hook or result.keyword or result.trend)[:500],
                "dedupe_key": result.dedupe_key or f"{result.source}:{result.keyword}".lower()[:120],
            }
        )
    return rows
