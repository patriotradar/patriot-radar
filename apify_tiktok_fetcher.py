"""
Apify TikTok data fetch layer.

Fetches TikTok video metadata via the Apify clockworks/tiktok-scraper actor.
Does not modify scoring, recommendations, or signal extraction logic.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from keyword_diversity import fetch_historical_keyword_roots, select_diverse_apify_targets

logger = logging.getLogger(__name__)

DEFAULT_ACTOR_ID = "clockworks/tiktok-scraper"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "apify_tiktok_config.json"

DEFAULT_HASHTAGS = [
    "britishpride",
    "patriotism",
    "ukpolitics",
    "britishhistory",
    "england",
]

DEFAULT_SEARCH_QUERIES = [
    "British pride TikTok",
    "patriotism UK debate",
    "British veterans respect",
]


def _load_apify_config() -> dict[str, Any]:
    """Load Apify actor input from config file and environment overrides."""
    config: dict[str, Any] = {
        "hashtags": list(DEFAULT_HASHTAGS),
        "searchQueries": list(DEFAULT_SEARCH_QUERIES),
        "resultsPerPage": 10,
    }

    config_path = os.getenv("APIFY_TIKTOK_CONFIG_PATH")
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                file_config = json.load(f)
            if isinstance(file_config, dict):
                config.update(file_config)
        except Exception as exc:
            logger.warning("Failed to load Apify config from %s: %s", path, exc)

    env_hashtags = os.getenv("TIKTOK_APIFY_HASHTAGS")
    if env_hashtags:
        config["hashtags"] = [h.strip() for h in env_hashtags.split(",") if h.strip()]

    env_queries = os.getenv("TIKTOK_APIFY_SEARCH_QUERIES")
    if env_queries:
        config["searchQueries"] = [q.strip() for q in env_queries.split("|") if q.strip()]

    env_limit = os.getenv("TIKTOK_APIFY_RESULTS_PER_PAGE")
    if env_limit:
        try:
            config["resultsPerPage"] = int(env_limit)
        except ValueError:
            logger.warning("Invalid TIKTOK_APIFY_RESULTS_PER_PAGE: %s", env_limit)

    return config


def _resolve_apify_run(run: Any) -> tuple[str | None, str | None, str | None]:
    """
    Extract run id, default dataset id, and status from Apify client response.

    apify-client v3 returns a Pydantic Run model (snake_case fields); v2 returned dicts
    with camelCase keys. Without this helper, v3 runs look like apify_run_missing_dataset.
    """
    if run is None:
        return None, None, None

    if isinstance(run, dict):
        run_id = run.get("id")
        dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
        status = run.get("status")
        return run_id, dataset_id, status

    run_id = getattr(run, "id", None)
    dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
    status = getattr(run, "status", None)
    if status is not None and not isinstance(status, str):
        status = getattr(status, "value", str(status))
    return run_id, dataset_id, status


def _apify_item_to_extractor_input(item: dict[str, Any]) -> dict[str, Any]:
    """Map an Apify TikTok scraper result to tiktok_trend_extractor input format."""
    author_meta = item.get("authorMeta") or {}
    author = (
        item.get("authorMeta.name")
        or author_meta.get("name")
        or item.get("author")
        or ""
    )
    caption = (
        item.get("text")
        or item.get("desc")
        or item.get("description")
        or item.get("title")
        or ""
    )
    url = (
        item.get("webVideoUrl")
        or item.get("videoUrl")
        or item.get("url")
        or ""
    )

    engagement = {
        "play_count": int(item.get("playCount") or item.get("play_count") or 0),
        "digg_count": int(item.get("diggCount") or item.get("digg_count") or item.get("likes") or 0),
        "share_count": int(item.get("shareCount") or item.get("share_count") or 0),
        "comment_count": int(item.get("commentCount") or item.get("comment_count") or 0),
    }

    return {
        "url": url,
        "caption": caption,
        "description": caption,
        "author": author,
        "title": caption,
        "source": "apify",
        "engagement": engagement,
    }


def fetch_tiktok_via_apify(historical_keywords: set[str] | None = None) -> dict[str, Any]:
    """
    Fetch TikTok videos via Apify actor.

    Returns a result dict with keys:
      - success: bool
      - items: list of extractor-ready dicts
      - item_count: int
      - apify_run_id: str | None
      - error: str | None
      - token_present: bool
    """
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    actor_id = os.getenv("APIFY_TIKTOK_ACTOR_ID", DEFAULT_ACTOR_ID)

    result: dict[str, Any] = {
        "success": False,
        "items": [],
        "item_count": 0,
        "apify_run_id": None,
        "error": None,
        "token_present": bool(token),
        "actor_id": actor_id,
    }

    if not token:
        result["error"] = "missing_apify_api_token"
        logger.warning(
            "APIFY_API_TOKEN is not set — Apify TikTok fetch skipped. "
            "Set APIFY_API_TOKEN in GitHub Actions secrets or your runtime environment."
        )
        return result

    config = _load_apify_config()
    run_input: dict[str, Any] = {
        "resultsPerPage": config.get("resultsPerPage", 10),
    }

    historical = historical_keywords if historical_keywords is not None else fetch_historical_keyword_roots()
    diverse_targets = select_diverse_apify_targets(historical)

    hashtags = diverse_targets.get("hashtags") or config.get("hashtags") or []
    search_queries = diverse_targets.get("searchQueries") or config.get("searchQueries") or []
    if hashtags:
        run_input["hashtags"] = hashtags
    if search_queries:
        run_input["searchQueries"] = search_queries

    if not hashtags and not search_queries:
        result["error"] = "no_apify_search_targets"
        logger.error("Apify config has no hashtags or searchQueries configured.")
        return result

    logger.info(
        "Starting Apify TikTok fetch: actor=%s hashtags=%s searchQueries=%s resultsPerPage=%s",
        actor_id,
        hashtags,
        search_queries,
        run_input["resultsPerPage"],
    )

    try:
        from apify_client import ApifyClient

        client = ApifyClient(token)
        run = client.actor(actor_id).call(run_input=run_input)
        run_id, dataset_id, run_status = _resolve_apify_run(run)

        if run is None:
            result["error"] = "apify_run_failed"
            logger.error("Apify actor call returned no run object.")
            return result

        if not dataset_id:
            result["error"] = "apify_run_missing_dataset"
            result["apify_run_id"] = run_id
            logger.error(
                "Apify run completed but no default dataset id returned (run_id=%s status=%s).",
                run_id,
                run_status,
            )
            return result

        raw_items: list[dict[str, Any]] = []
        for item in client.dataset(dataset_id).iterate_items():
            if isinstance(item, dict):
                raw_items.append(item)

        mapped = [_apify_item_to_extractor_input(item) for item in raw_items]
        # Keep items that have caption text or a URL for downstream extraction.
        usable = [
            item for item in mapped
            if (item.get("caption") or "").strip() or (item.get("url") or "").strip()
        ]

        result["success"] = True
        result["items"] = usable
        result["item_count"] = len(usable)
        result["apify_run_id"] = run_id
        result["angles_used"] = diverse_targets.get("angles_used", [])

        logger.info(
            "Apify TikTok fetch succeeded: run_id=%s raw_items=%d usable_items=%d",
            run_id,
            len(raw_items),
            len(usable),
        )
        if not usable:
            logger.warning("Apify returned no usable TikTok items after mapping.")

        return result

    except ImportError:
        result["error"] = "apify_client_not_installed"
        logger.error(
            "apify-client package is not installed. Add it to requirements.txt and pip install."
        )
        return result
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("Apify TikTok fetch failed: %s", exc)
        return result
