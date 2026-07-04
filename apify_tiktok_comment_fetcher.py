"""
Apify TikTok comment fetch layer — isolated from apify_tiktok_fetcher.py.

Fetches video URLs via the existing video scraper, then pulls comment bodies
via clockworks/tiktok-comments-scraper. Does not modify the trend pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from apify_tiktok_fetcher import fetch_tiktok_via_apify

logger = logging.getLogger(__name__)

DEFAULT_COMMENT_ACTOR_ID = "clockworks/tiktok-comments-scraper"
DEFAULT_SAMPLE_PATH = Path(__file__).resolve().parent / "data" / "tiktok_comment_sample.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "niche_comment_ingest_config.json"

_VIDEO_ID_RE = re.compile(r"/video/(\d+)")


def _load_ingest_config() -> dict[str, Any]:
    config: dict[str, Any] = {
        "commentsPerPost": 50,
        "maxVideos": 15,
        "resultsPerPage": 8,
    }
    config_path = os.getenv("NICHE_COMMENT_INGEST_CONFIG_PATH")
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                file_config = json.load(f)
            if isinstance(file_config, dict):
                config.update(file_config)
        except Exception as exc:
            logger.warning("Failed to load ingest config from %s: %s", path, exc)

    env_comments = os.getenv("NICHE_COMMENT_COMMENTS_PER_POST")
    if env_comments:
        try:
            config["commentsPerPost"] = int(env_comments)
        except ValueError:
            pass

    env_max = os.getenv("NICHE_COMMENT_MAX_VIDEOS")
    if env_max:
        try:
            config["maxVideos"] = int(env_max)
        except ValueError:
            pass

    return config


def _video_id_from_url(url: str) -> str:
    match = _VIDEO_ID_RE.search(url or "")
    if match:
        return match.group(1)
    return ""


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
        "like_count": int(
            raw.get("diggCount") or raw.get("likes") or raw.get("like_count") or 0
        ),
        "author": (
            raw.get("uniqueId")
            or raw.get("author")
            or (raw.get("authorMeta") or {}).get("name")
            or ""
        ),
    }


def _extract_comments_from_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for key in ("comments", "latestComments", "topComments", "commentList"):
        nested = item.get(key)
        if not isinstance(nested, list):
            continue
        for raw in nested:
            if isinstance(raw, dict):
                normalized = _normalize_comment(raw)
                if normalized["text"]:
                    comments.append(normalized)
    return comments


def _video_lookup_from_items(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in items:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        lookup[url] = {
            "url": url,
            "video_id": _video_id_from_url(url),
            "caption": (item.get("caption") or item.get("description") or "").strip(),
            "author": (item.get("author") or "").strip(),
            "comment_count": int((item.get("engagement") or {}).get("comment_count") or 0),
        }
    return lookup


def _merge_video_comments(
    video_lookup: dict[str, dict[str, Any]],
    comment_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_url: dict[str, list[dict[str, Any]]] = {url: [] for url in video_lookup}

    for item in comment_items:
        video_url = (
            item.get("videoWebUrl")
            or item.get("webVideoUrl")
            or item.get("videoUrl")
            or item.get("submittedVideoUrl")
            or item.get("url")
            or ""
        ).strip()

        if video_url not in by_url:
            video_id = _video_id_from_url(video_url)
            if video_id:
                video_lookup[video_url] = {
                    "url": video_url,
                    "video_id": video_id,
                    "caption": (item.get("videoDescription") or item.get("text") or "").strip(),
                    "author": (item.get("authorMeta") or {}).get("name", ""),
                    "comment_count": 0,
                }
                by_url[video_url] = []

        comments = _extract_comments_from_item(item)
        if not comments and item.get("text"):
            comments = [_normalize_comment(item)]

        if video_url in by_url:
            by_url[video_url].extend(comments)

    results: list[dict[str, Any]] = []
    for url, meta in video_lookup.items():
        comments = by_url.get(url) or []
        if not comments:
            continue
        results.append(
            {
                "video_id": meta.get("video_id") or _video_id_from_url(url),
                "url": url,
                "caption": meta.get("caption", ""),
                "author": meta.get("author", ""),
                "comment_count": max(meta.get("comment_count", 0), len(comments)),
                "comments": comments,
                "source": "apify",
            }
        )
    return results


def load_sample_comment_videos(sample_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(sample_path) if sample_path else DEFAULT_SAMPLE_PATH
    if not path.exists():
        logger.warning("Sample comment file not found: %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []

    videos: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        videos.append(
            {
                "video_id": _video_id_from_url(url) or url,
                "url": url,
                "caption": (item.get("caption") or "").strip(),
                "author": (item.get("author") or "").strip(),
                "comment_count": int(item.get("comment_count") or len(item.get("comments") or [])),
                "comments": item.get("comments") or [],
                "source": "sample",
            }
        )
    return videos


def _fetch_comments_for_urls(
    token: str,
    actor_id: str,
    video_urls: list[str],
    comments_per_post: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "items": [],
        "item_count": 0,
        "apify_run_id": None,
        "error": None,
        "actor_id": actor_id,
    }

    if not video_urls:
        result["error"] = "no_video_urls"
        return result

    run_input = {
        "postURLs": video_urls,
        "commentsPerPost": comments_per_post,
        "maxRepliesPerComment": 0,
    }

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

        result["success"] = True
        result["items"] = raw_items
        result["item_count"] = len(raw_items)
        result["apify_run_id"] = run_id
        return result

    except ImportError:
        result["error"] = "apify_client_not_installed"
        return result
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("Apify comment actor fetch failed: %s", exc)
        return result


def _fetch_comments_via_video_scraper(
    token: str,
    actor_id: str,
    video_lookup: dict[str, dict[str, Any]],
    comments_per_post: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Fallback: use tiktok-scraper with shouldDownloadComments when comment actor fails."""
    from apify_tiktok_fetcher import DEFAULT_ACTOR_ID as VIDEO_ACTOR_ID

    result: dict[str, Any] = {
        "success": False,
        "items": [],
        "item_count": 0,
        "apify_run_id": None,
        "error": None,
        "actor_id": actor_id or VIDEO_ACTOR_ID,
    }

    run_input: dict[str, Any] = {
        "postURLs": list(video_lookup.keys()),
        "resultsPerPage": min(len(video_lookup), config.get("resultsPerPage", 8)),
        "commentsPerPost": comments_per_post,
        "shouldDownloadComments": True,
    }

    try:
        from apify_client import ApifyClient

        client = ApifyClient(token)
        run = client.actor(actor_id or VIDEO_ACTOR_ID).call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
        if not dataset_id:
            result["error"] = "apify_run_missing_dataset"
            return result

        raw_items: list[dict[str, Any]] = []
        for item in client.dataset(dataset_id).iterate_items():
            if isinstance(item, dict):
                raw_items.append(item)

        merged: list[dict[str, Any]] = []
        for item in raw_items:
            url = (
                item.get("webVideoUrl")
                or item.get("videoUrl")
                or item.get("url")
                or ""
            ).strip()
            meta = video_lookup.get(url) or {
                "url": url,
                "video_id": _video_id_from_url(url),
                "caption": (item.get("text") or item.get("desc") or "").strip(),
                "author": (item.get("authorMeta") or {}).get("name", ""),
                "comment_count": int(item.get("commentCount") or 0),
            }
            comments = _extract_comments_from_item(item)
            if comments:
                merged.append({**meta, "comments": comments, "source": "apify"})

        result["success"] = bool(merged)
        result["items"] = merged
        result["item_count"] = len(merged)
        result["apify_run_id"] = run.get("id") if isinstance(run, dict) else None
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result


def fetch_tiktok_comments_via_apify() -> dict[str, Any]:
    """
    Fetch TikTok videos and comment bodies via Apify.

    Returns:
      success, items (video dicts with comments), item_count, apify_run_id,
      error, token_present, video_fetch, comment_fetch
    """
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    comment_actor = os.getenv("APIFY_TIKTOK_COMMENT_ACTOR_ID", DEFAULT_COMMENT_ACTOR_ID)
    video_actor = os.getenv("APIFY_TIKTOK_COMMENTS_FALLBACK_ACTOR_ID", "clockworks/tiktok-scraper")

    result: dict[str, Any] = {
        "success": False,
        "items": [],
        "item_count": 0,
        "apify_run_id": None,
        "error": None,
        "token_present": bool(token),
        "video_fetch": {},
        "comment_fetch": {},
    }

    if not token:
        result["error"] = "missing_apify_api_token"
        return result

    config = _load_ingest_config()
    comments_per_post = int(config.get("commentsPerPost") or 50)
    max_videos = int(config.get("maxVideos") or 15)

    video_fetch = fetch_tiktok_via_apify()
    result["video_fetch"] = video_fetch

    if not video_fetch.get("success") or not video_fetch.get("items"):
        result["error"] = video_fetch.get("error") or "video_fetch_failed"
        return result

    video_items = video_fetch["items"][:max_videos]
    video_lookup = _video_lookup_from_items(video_items)
    video_urls = list(video_lookup.keys())
    if not video_urls:
        result["error"] = "no_video_urls_from_fetch"
        return result

    comment_fetch = _fetch_comments_for_urls(
        token, comment_actor, video_urls, comments_per_post
    )
    result["comment_fetch"] = comment_fetch
    result["apify_run_id"] = comment_fetch.get("apify_run_id")

    videos: list[dict[str, Any]] = []
    if comment_fetch.get("success") and comment_fetch.get("items"):
        videos = _merge_video_comments(video_lookup, comment_fetch["items"])
    else:
        logger.warning(
            "Comment actor failed (%s) — trying video scraper fallback.",
            comment_fetch.get("error"),
        )
        fallback = _fetch_comments_via_video_scraper(
            token, video_actor, video_lookup, comments_per_post, config
        )
        result["comment_fetch"] = {
            **comment_fetch,
            "fallback": fallback,
        }
        if fallback.get("success") and fallback.get("items"):
            videos = fallback["items"]
            result["apify_run_id"] = fallback.get("apify_run_id")

    if not videos:
        result["error"] = comment_fetch.get("error") or "no_comments_fetched"
        return result

    result["success"] = True
    result["items"] = videos
    result["item_count"] = len(videos)
    return result
