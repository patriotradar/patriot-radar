"""
Orchestrator for the Niche-Aware Comment Signal pipeline.

Completely isolated from trend_shift_engine.py and existing TikTok trend scan.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apify_tiktok_comments_reader import (
    fetch_tiktok_comments_via_apify,
    load_sample_comment_videos,
)
from niche_comment_config import load_niche_config
from niche_comment_signal_store import store_niche_comment_signals
from niche_comment_signals import compute_batch_comment_signals

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_PATH = (
    Path(__file__).resolve().parent / "data" / "tiktok_comment_sample.json"
)
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent / "data" / "niche_comment_signals_latest.json"
)


def run_niche_comment_signal_scan(
    *,
    video_inputs: list[dict[str, Any]] | None = None,
    sample_path: str | Path | None = None,
    persist: bool = True,
    use_apify: bool = True,
    niche_config: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Run the full niche comment signal pipeline.

    Input resolution:
      1. Explicit video_inputs (with comments)
      2. Apify fetch (if token present and use_apify=True)
      3. Sample file fallback (when no token or Apify fails without token)
    """
    config = niche_config or load_niche_config()
    apify_fetch: dict[str, Any] = {}
    data_source = "unknown"
    videos: list[dict[str, Any]] = []

    if video_inputs:
        videos = [v for v in video_inputs if isinstance(v, dict)]
        data_source = "explicit_inputs"
    elif use_apify:
        apify_fetch = fetch_tiktok_comments_via_apify()
        if apify_fetch.get("success") and apify_fetch.get("items"):
            videos = apify_fetch["items"]
            data_source = "apify"
        elif apify_fetch.get("token_present"):
            # Token present but fetch failed — do not silently fall back
            return {
                "success": False,
                "data_source": "apify",
                "apify_fetch": apify_fetch,
                "error": apify_fetch.get("error") or "apify_fetch_failed",
                "video_count": 0,
            }
        else:
            path = Path(sample_path) if sample_path else DEFAULT_SAMPLE_PATH
            videos = load_sample_comment_videos(path)
            data_source = "sample"
            logger.info("No Apify token — using sample comment data from %s", path)
    else:
        path = Path(sample_path) if sample_path else DEFAULT_SAMPLE_PATH
        videos = load_sample_comment_videos(path)
        data_source = "sample"

    if not videos:
        return {
            "success": False,
            "data_source": data_source,
            "apify_fetch": apify_fetch,
            "error": "no_videos_with_comments",
            "video_count": 0,
        }

    batch_result = compute_batch_comment_signals(videos, config)

    store_result: dict[str, Any] = {"stored": 0, "skipped": 0, "error": None}
    if persist:
        store_result = store_niche_comment_signals(batch_result)

    out_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch_result, f, indent=2)
    except Exception as exc:
        logger.warning("Failed to write local output to %s: %s", out_path, exc)

    return {
        "success": batch_result.get("success", False),
        "data_source": data_source,
        "apify_fetch": apify_fetch,
        "niche_id": config.get("niche_id"),
        "niche_label": config.get("label"),
        "video_count": batch_result.get("video_count", 0),
        "avg_composite_signal": batch_result.get("avg_composite_signal", 0),
        "batch_result": batch_result,
        "store_result": store_result,
        "local_output": str(out_path),
    }
