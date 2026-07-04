"""
Persistence layer for Niche-Aware Comment Signals.

Writes to a NEW Supabase table (niche_comment_signals_feed).
Does not touch trend_intelligence_feed or any existing tables.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TABLE = "niche_comment_signals_feed"
SOURCE = "tiktok_comments"


def _get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        logger.error("Failed to create Supabase client: %s", exc)
        return None


def signals_to_feed_rows(batch_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert compute_batch_comment_signals output to Supabase rows."""
    videos = batch_result.get("videos") or []
    rows: list[dict[str, Any]] = []

    for video in videos:
        if not isinstance(video, dict):
            continue
        signals = video.get("signals") or {}
        dedupe_key = video.get("dedupe_key")
        if not dedupe_key:
            continue

        composite = float(signals.get("composite_signal") or 0)
        niche = float(signals.get("niche_relevance_score") or 0)

        if composite >= 70:
            signal_state = "high"
        elif composite >= 40:
            signal_state = "moderate"
        else:
            signal_state = "low"

        rows.append({
            "timestamp": video.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "source": SOURCE,
            "video_url": video.get("video_url") or "",
            "author": video.get("author") or "",
            "caption_preview": video.get("caption_preview") or "",
            "comment_count": int(video.get("comment_count") or 0),
            "comments_analyzed": int(video.get("comments_analyzed") or 0),
            "comment_velocity": float(signals.get("comment_velocity") or 0),
            "repetition_score": float(signals.get("repetition_score") or 0),
            "curiosity_score": float(signals.get("curiosity_score") or 0),
            "niche_relevance_score": niche,
            "composite_signal": composite,
            "signal_state": signal_state,
            "niche_id": (video.get("details") or {}).get("niche_id") or batch_result.get("niche_id") or "",
            "raw_data": video,
            "summary": _build_summary(video),
            "dedupe_key": dedupe_key,
        })

    return rows


def _build_summary(video: dict[str, Any]) -> str:
    signals = video.get("signals") or {}
    details = video.get("details") or {}
    phrases = details.get("top_repeated_phrases") or []
    phrase_hint = f" Repeated: {', '.join(phrases[:2])}." if phrases else ""
    return (
        f"Composite {signals.get('composite_signal', 0):.0f} "
        f"(velocity {signals.get('comment_velocity', 0):.0f}, "
        f"niche {signals.get('niche_relevance_score', 0):.0f})."
        f"{phrase_hint}"
    ).strip()


def store_niche_comment_signals(
    batch_result: dict[str, Any] | None,
    table: str | None = None,
) -> dict[str, Any]:
    """Upsert niche comment signal rows into Supabase."""
    if not batch_result:
        return {"stored": 0, "skipped": 0, "error": None}

    rows = signals_to_feed_rows(batch_result)
    if not rows:
        return {"stored": 0, "skipped": 0, "error": None}

    table_name = table or os.getenv("SUPABASE_NICHE_COMMENT_TABLE", DEFAULT_TABLE)

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {
                "stored": 0,
                "skipped": len(rows),
                "error": "missing_supabase_credentials",
            }

        stored = 0
        failed = 0
        last_error: str | None = None

        for row in rows:
            try:
                supabase.table(table_name).upsert(
                    row,
                    on_conflict="dedupe_key",
                ).execute()
                stored += 1
            except Exception as exc:
                failed += 1
                last_error = str(exc)
                logger.error(
                    "Upsert failed for dedupe_key=%s: %s",
                    row.get("dedupe_key"),
                    exc,
                )

        return {
            "stored": stored,
            "skipped": failed,
            "error": None if failed == 0 else (last_error or "partial_write_failure"),
        }
    except Exception as exc:
        logger.exception("Store niche comment signals failed: %s", exc)
        return {"stored": 0, "skipped": len(rows), "error": str(exc)}
