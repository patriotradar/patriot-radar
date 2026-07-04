"""
Time-based snapshot memory for the Virality Intelligence System.

Records periodic prediction states for outcome comparison and learning.
Reads niche_comment_raw (read-only) — never modifies existing tables.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_TABLE = "virality_snapshots"
DEFAULT_RAW_TABLE = "niche_comment_raw"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _snapshot_dedupe_key(video_id: str, niche: str, snapshot_hour: str) -> str:
    raw = f"{video_id}|{niche.strip().lower()}|{snapshot_hour}"
    return "virality_snapshot:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def fetch_raw_comment_rows(limit: int = 5000) -> list[dict[str, Any]]:
    """Read raw comments from Supabase (read-only). Returns empty list on failure."""
    client = _get_supabase_client()
    table = os.getenv("NICHE_COMMENT_RAW_TABLE", DEFAULT_RAW_TABLE)
    if client is None:
        logger.warning("Cannot fetch raw comments — missing Supabase credentials.")
        return []

    try:
        resp = (
            client.table(table)
            .select("*")
            .order("ingested_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error("Failed to fetch niche_comment_raw: %s", exc)
        return []


def build_snapshot_row(
    video: dict[str, Any],
    niche: str,
    weights: dict[str, float],
    *,
    snapshot_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a snapshot row from a video prediction result."""
    now = snapshot_at or datetime.now(timezone.utc)
    snapshot_hour = now.strftime("%Y%m%dT%H")
    video_id = str(video.get("video_id") or "")
    signals = video.get("signals") or {}

    return {
        "snapshot_at": now.isoformat(),
        "video_id": video_id,
        "niche": niche.strip().lower(),
        "comment_velocity": float(signals.get("velocity_per_hour") or 0.0),
        "acceleration": float(signals.get("acceleration_raw") or signals.get("acceleration_score") or 0.0),
        "repetition_score": float(signals.get("cross_video_score") or 0.0),
        "curiosity_score": float(signals.get("curiosity_score") or 0.0),
        "confusion_score": float(signals.get("curiosity_score") or 0.0),
        "niche_relevance_score": float(signals.get("niche_relevance_score") or 0.0),
        "virality_score": float(video.get("virality_score") or 0.0),
        "signals": signals,
        "weights": weights,
        "metadata": {
            "early_warning_level": (video.get("early_warning") or {}).get("level"),
            "time_to_viral_status": (video.get("time_to_viral") or {}).get("status"),
            "comments_analyzed": video.get("comments_analyzed"),
        },
        "dedupe_key": _snapshot_dedupe_key(video_id, niche, snapshot_hour),
    }


def store_snapshots(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Upsert snapshot rows. Idempotent per dedupe_key. Never raises."""
    table = os.getenv("VIRALITY_SNAPSHOT_TABLE", DEFAULT_SNAPSHOT_TABLE)
    if not rows:
        return {"stored": 0, "skipped": 0, "error": None}

    client = _get_supabase_client()
    if client is None:
        return {"stored": 0, "skipped": len(rows), "error": "missing_supabase_credentials"}

    stored = 0
    failed = 0
    last_error: str | None = None

    for row in rows:
        try:
            client.table(table).upsert(row, on_conflict="dedupe_key").execute()
            stored += 1
        except Exception as exc:
            failed += 1
            last_error = str(exc)
            logger.error("Snapshot upsert failed for %s: %s", row.get("dedupe_key"), exc)

    return {
        "stored": stored,
        "skipped": failed,
        "error": None if failed == 0 else ("partial_write_failure: " + (last_error or "unknown")),
    }


def store_prediction_snapshots(
    videos: list[dict[str, Any]],
    niche: str,
    weights: dict[str, float],
) -> dict[str, Any]:
    """Store snapshots for all video predictions in a batch."""
    rows = [build_snapshot_row(v, niche, weights) for v in videos if v.get("video_id")]
    return store_snapshots(rows)


def fetch_snapshots_for_video(
    video_id: str,
    *,
    niche: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Retrieve historical snapshots for a video."""
    client = _get_supabase_client()
    table = os.getenv("VIRALITY_SNAPSHOT_TABLE", DEFAULT_SNAPSHOT_TABLE)
    if client is None:
        return []

    try:
        query = client.table(table).select("*").eq("video_id", video_id)
        if niche:
            query = query.eq("niche", niche.strip().lower())
        resp = query.order("snapshot_at", desc=False).limit(limit).execute()
        return resp.data or []
    except Exception as exc:
        logger.warning("Could not fetch snapshots for video %s: %s", video_id, exc)
        return []


def fetch_recent_snapshots(limit: int = 500) -> list[dict[str, Any]]:
    """Fetch most recent snapshots across all videos."""
    client = _get_supabase_client()
    table = os.getenv("VIRALITY_SNAPSHOT_TABLE", DEFAULT_SNAPSHOT_TABLE)
    if client is None:
        return []

    try:
        resp = (
            client.table(table)
            .select("*")
            .order("snapshot_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.warning("Could not fetch recent snapshots: %s", exc)
        return []


def fetch_accuracy_trend(limit: int = 30) -> list[dict[str, Any]]:
    """Build accuracy-over-time data from calibration logs."""
    client = _get_supabase_client()
    table = os.getenv("VIRALITY_CALIBRATION_TABLE", "virality_calibration_logs")
    if client is None:
        return []

    try:
        resp = (
            client.table(table)
            .select("calibrated_at, accuracy_before, accuracy_after, outcomes_processed")
            .order("calibrated_at", desc=False)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.warning("Could not fetch accuracy trend: %s", exc)
        return []
