"""
Orchestrator for raw TikTok comment ingestion.

Completely isolated from trend_shift_engine.py and existing TikTok trend scan.
Stores raw comments only — niche signals are computed at query time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from apify_tiktok_comment_fetcher import (
    fetch_tiktok_comments_via_apify,
    load_sample_comment_videos,
)
from niche_comment_raw_store import store_raw_comment_videos

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_PATH = Path(__file__).resolve().parent / "data" / "tiktok_comment_sample.json"


def run_niche_comment_ingest(
    *,
    video_inputs: list[dict[str, Any]] | None = None,
    sample_path: str | Path | None = None,
    persist: bool = True,
    use_apify: bool = True,
) -> dict[str, Any]:
    """
    Ingest raw TikTok comments into niche_comment_raw.

    Input resolution:
      1. Explicit video_inputs (with comments)
      2. Apify fetch (if token present and use_apify=True)
      3. Sample file fallback (when no token or Apify fails without token)
    """
    apify_result: dict[str, Any] = {}
    data_source = "unknown"
    videos: list[dict[str, Any]] = []

    if video_inputs:
        videos = [v for v in video_inputs if isinstance(v, dict)]
        data_source = "explicit_inputs"
        logger.info("Using %d explicit video input(s).", len(videos))
    elif use_apify:
        apify_result = fetch_tiktok_comments_via_apify()
        if apify_result.get("success") and apify_result.get("items"):
            videos = apify_result["items"]
            data_source = "apify"
            logger.info("Using %d video(s) from Apify comment fetch.", len(videos))
        elif apify_result.get("token_present"):
            logger.error(
                "Apify comment fetch failed with token configured (error=%s). "
                "Refusing sample fallback.",
                apify_result.get("error"),
            )
            return {
                "success": False,
                "data_source": "apify_failed",
                "apify_fetch": apify_result,
                "error": apify_result.get("error") or "apify_fetch_failed",
                "video_count": 0,
                "comment_count": 0,
                "store_result": {"stored": 0, "skipped": 0, "error": "apify_fetch_failed"},
            }
        else:
            path = Path(sample_path) if sample_path else DEFAULT_SAMPLE_PATH
            videos = load_sample_comment_videos(path)
            data_source = "sample_fallback"
            logger.warning("No Apify token — using sample comment data from %s", path)
    else:
        path = Path(sample_path) if sample_path else DEFAULT_SAMPLE_PATH
        videos = load_sample_comment_videos(path)
        data_source = "sample_fallback"

    if not videos:
        return {
            "success": False,
            "data_source": data_source,
            "apify_fetch": apify_result,
            "error": "no_videos_with_comments",
            "video_count": 0,
            "comment_count": 0,
            "store_result": {"stored": 0, "skipped": 0, "error": "no_videos_with_comments"},
        }

    comment_count = sum(len(v.get("comments") or []) for v in videos)

    store_result: dict[str, Any] = {"stored": 0, "skipped": 0, "error": None}
    if persist and comment_count:
        store_result = store_raw_comment_videos(videos)
        logger.info(
            "Raw comment ingest complete: stored=%d skipped=%d error=%s",
            store_result.get("stored", 0),
            store_result.get("skipped", 0),
            store_result.get("error"),
        )
    elif persist and not comment_count:
        logger.warning("No comments to persist to niche_comment_raw.")

    hardened: dict[str, Any] = {"insights": [], "recommended_posts": [], "trend_scores": [], "errors": []}
    try:
        from tiktok_insights_pipeline import run_hardened_pipeline_from_raw_rows
        from niche_comment_raw_store import videos_to_raw_rows

        raw_rows = videos_to_raw_rows(videos)
        hardened = run_hardened_pipeline_from_raw_rows(raw_rows, niche="")
    except Exception as exc:
        logger.warning("Hardened insights overlay skipped: %s", exc)
        hardened["errors"] = [str(exc)]

    return {
        "success": comment_count > 0,
        "data_source": data_source,
        "apify_fetch": apify_result,
        "video_count": len(videos),
        "comment_count": comment_count,
        "store_result": store_result,
        "insights": hardened.get("insights") or [],
        "recommended_posts": hardened.get("recommended_posts") or [],
        "trend_scores": hardened.get("trend_scores") or [],
        "errors": hardened.get("errors") or [],
    }
