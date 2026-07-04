"""
Apify TikTok comment reader — isolated from apify_tiktok_fetcher.py.

Fetches video metadata with comment bodies via the same Apify actor family,
but does not modify the existing trend pipeline fetch layer.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ACTOR_ID = "clockworks/tiktok-scraper"
DEFAULT_SAMPLE_PATH = (
    Path(__file__).resolve().parent / "data" / "tiktok_comment_sample.json"
)
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent / "data" / "apify_tiktok_config.json"
)

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


def _load_search_config() -> dict[str, Any]:
    config: dict[str, Any] = {
        "hashtags": list(DEFAULT_HASHTAGS),
        "searchQueries": list(DEFAULT_SEARCH_QUERIES),
        "resultsPerPage": 5,
        "commentsPerPost": 30,
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

    env_limit = os.getenv("TIKTOK_APIFY_RESULTS_PER_PAGE")
    if env_limit:
        try:
            config["resultsPerPage"] = int(env_limit)
        except ValueError:
            pass

    env_comments = os.getenv("TIKTOK_APIFY_COMMENTS_PER_POST")
    if env_comments:
        try:
            config["commentsPerPost"] = int(env_comments)
        except ValueError:
            pass

    return config


def _normalize_comment(raw: dict[str, Any]) -> dict[str, Any]:
    text = (
        raw.get("text")
        or raw.get("comment")
        or raw.get("content")
        or raw.get("desc")
        or ""
    )
    create_time = (
        raw.get("createTime")
        or raw.get("create_time")
        or raw.get("timestamp")
        or raw.get("time")
    )
    return {
        "text": str(text).strip(),
        "create_time": int(create_time) if create_time else None,
        "like_count": int(raw.get("diggCount") or raw.get("likes") or raw.get("like_count") or 0),
        "author": (
            raw.get("uniqueId")
            or raw.get("author")
            or (raw.get("authorMeta") or {}).get("name")
            or ""
        ),
    }


def _extract_comments_from_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull comment bodies from various Apify TikTok scraper output shapes."""
    comments: list[dict[str, Any]] = []

    raw_comments = item.get("comments")
    if isinstance(raw_comments, list):
        for c in raw_comments:
            if isinstance(c, dict):
                normalized = _normalize_comment(c)
                if normalized["text"]:
                    comments.append(normalized)

    # Nested comment lists (some actor versions)
    for key in ("latestComments", "topComments", "commentList"):
        nested = item.get(key)
        if isinstance(nested, list):
            for c in nested:
                if isinstance(c, dict):
                    normalized = _normalize_comment(c)
                    if normalized["text"]:
                        comments.append(normalized)

    return comments


def _apify_item_to_video_with_comments(item: dict[str, Any]) -> dict[str, Any]:
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
    comments = _extract_comments_from_item(item)
    comment_count = int(
        item.get("commentCount")
        or item.get("comment_count")
        or len(comments)
        or 0
    )

    return {
        "url": url,
        "caption": caption,
        "author": author,
        "comment_count": comment_count,
        "comments": comments,
        "source": "apify",
    }


def load_sample_comment_videos(sample_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(sample_path) if sample_path else DEFAULT_SAMPLE_PATH
    if not path.exists():
        logger.warning("Sample comment file not found: %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [v for v in data if isinstance(v, dict)]


def fetch_tiktok_comments_via_apify() -> dict[str, Any]:
    """
    Fetch TikTok videos with comment bodies via Apify.

    Returns:
      success, items, item_count, apify_run_id, error, token_present
    """
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    actor_id = os.getenv("APIFY_TIKTOK_COMMENTS_ACTOR_ID", DEFAULT_ACTOR_ID)

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
        return result

    config = _load_search_config()
    comments_per_post = int(config.get("commentsPerPost") or 30)
    run_input: dict[str, Any] = {
        "resultsPerPage": config.get("resultsPerPage", 5),
        "commentsPerPost": comments_per_post,
        "shouldDownloadComments": True,
    }

    hashtags = config.get("hashtags") or []
    search_queries = config.get("searchQueries") or []
    if hashtags:
        run_input["hashtags"] = hashtags
    if search_queries:
        run_input["searchQueries"] = search_queries

    if not hashtags and not search_queries:
        result["error"] = "no_apify_search_targets"
        return result

    logger.info(
        "Starting Apify comment fetch: actor=%s commentsPerPost=%s",
        actor_id,
        comments_per_post,
    )

    try:
        from apify_client import ApifyClient

        client = ApifyClient(token)
        run = client.actor(actor_id).call(run_input=run_input)
        run_id = run.get("id") if isinstance(run, dict) else None
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None

        if not dataset_id:
            result["error"] = "apify_run_missing_dataset"
            return result

        raw_items: list[dict[str, Any]] = []
        for item in client.dataset(dataset_id).iterate_items():
            if isinstance(item, dict):
                raw_items.append(item)

        mapped = [_apify_item_to_video_with_comments(item) for item in raw_items]
        usable = [
            item for item in mapped
            if (item.get("url") or "").strip() and item.get("comments")
        ]

        result["success"] = True
        result["items"] = usable
        result["item_count"] = len(usable)
        result["apify_run_id"] = run_id

        logger.info(
            "Apify comment fetch succeeded: run_id=%s raw=%d usable=%d",
            run_id,
            len(raw_items),
            len(usable),
        )
        return result

    except ImportError:
        result["error"] = "apify_client_not_installed"
        return result
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("Apify comment fetch failed: %s", exc)
        return result
