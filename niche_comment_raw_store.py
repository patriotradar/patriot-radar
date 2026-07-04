"""
Persistence layer for raw TikTok comments.

Stores comment rows without niche binding — relevance is computed at query time.
Does not touch trend_intelligence_feed or existing tables.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_RAW_TABLE = "niche_comment_raw"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        missing = []
        if not supabase_url:
            missing.append("SUPABASE_URL")
        if not service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        logger.error(
            "Supabase credentials missing (%s). Cannot write to niche_comment_raw.",
            ", ".join(missing),
        )
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _comment_dedupe_key(
    video_id: str,
    comment_text: str,
    comment_author: str,
    commented_at: str | None,
) -> str:
    raw = f"{video_id}|{comment_text.strip().lower()}|{comment_author.strip().lower()}|{commented_at or ''}"
    return "niche_comment_raw:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _parse_comment_timestamp(create_time: int | None) -> str | None:
    if create_time is None:
        return None
    try:
        return datetime.fromtimestamp(int(create_time), tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def videos_to_raw_rows(
    videos: list[dict[str, Any]],
    ingestion_batch: str | None = None,
) -> list[dict[str, Any]]:
    """Flatten video+comment payloads into niche_comment_raw rows."""
    batch = ingestion_batch or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows: list[dict[str, Any]] = []

    for video in videos:
        if not isinstance(video, dict):
            continue

        video_id = str(video.get("video_id") or "").strip()
        video_url = (video.get("url") or "").strip()
        if not video_id and video_url:
            video_id = video_url
        if not video_id:
            continue

        caption = (video.get("caption") or "").strip()
        author = (video.get("author") or "").strip()
        source = (video.get("source") or "apify").strip()
        comments = video.get("comments") or []
        if not isinstance(comments, list):
            continue

        for comment in comments:
            if not isinstance(comment, dict):
                continue
            text = (comment.get("text") or "").strip()
            if not text:
                continue

            comment_author = (comment.get("author") or "").strip()
            commented_at = _parse_comment_timestamp(comment.get("create_time"))
            dedupe_key = _comment_dedupe_key(video_id, text, comment_author, commented_at)

            rows.append(
                {
                    "video_id": video_id,
                    "video_url": video_url,
                    "video_caption": caption[:500],
                    "video_author": author,
                    "comment_text": text[:2000],
                    "comment_author": comment_author,
                    "comment_like_count": int(comment.get("like_count") or 0),
                    "commented_at": commented_at,
                    "ingestion_batch": batch,
                    "source": source,
                    "metadata": {
                        "video_comment_count": int(video.get("comment_count") or len(comments)),
                    },
                    "dedupe_key": dedupe_key,
                }
            )

    return rows


def store_raw_comment_rows(
    rows: list[dict[str, Any]],
    table: str | None = None,
) -> dict[str, Any]:
    """Upsert raw comment rows. Idempotent per dedupe_key. Never raises."""
    table_name = table or os.getenv("NICHE_COMMENT_RAW_TABLE", DEFAULT_RAW_TABLE)
    if not rows:
        logger.info("No niche_comment_raw rows to store.")
        return {"stored": 0, "skipped": 0, "error": None}

    logger.info("Preparing to upsert %d raw comment row(s) into %s.", len(rows), table_name)

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
                supabase.table(table_name).upsert(row, on_conflict="dedupe_key").execute()
                stored += 1
            except Exception as exc:
                failed += 1
                last_error = str(exc)
                logger.error(
                    "Supabase upsert failed for dedupe_key=%s: %s",
                    row.get("dedupe_key"),
                    exc,
                )

        logger.info(
            "niche_comment_raw upsert finished: stored=%d failed=%d",
            stored,
            failed,
        )
        return {
            "stored": stored,
            "skipped": failed,
            "error": None if failed == 0 else ("partial_write_failure: " + (last_error or "unknown")),
        }
    except Exception as exc:
        logger.exception("niche_comment_raw upsert failed: %s", exc)
        return {"stored": 0, "skipped": len(rows), "error": str(exc)}


def store_raw_comment_videos(
    videos: list[dict[str, Any]] | None,
    table: str | None = None,
    ingestion_batch: str | None = None,
) -> dict[str, Any]:
    """Persist video comment payloads as flat raw rows. Safe with empty input."""
    try:
        if not videos:
            return {"stored": 0, "skipped": 0, "error": None}
        rows = videos_to_raw_rows(videos, ingestion_batch=ingestion_batch)
        return store_raw_comment_rows(rows, table=table)
    except Exception as exc:
        return {"stored": 0, "skipped": 0, "error": str(exc)}
