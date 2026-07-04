"""
Performance tracking layer for the TikTok viral loop engine.

Collects engagement metrics via Apify for queued/posted content and stores
snapshots in Supabase. Never raises; always returns a safe result dict.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from apify_tiktok_fetcher import fetch_tiktok_via_apify

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_TABLE = "content_queue"
DEFAULT_PERFORMANCE_TABLE = "content_performance"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        logger.warning("Supabase credentials missing; performance tracking skipped.")
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _empty_result() -> dict[str, Any]:
    return {"tracked": 0, "skipped": 0, "error": None, "snapshots": []}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_engagement_rate(engagement: dict[str, Any]) -> float:
    views = max(_safe_float(engagement.get("play_count")), 1.0)
    likes = _safe_float(engagement.get("digg_count"))
    shares = _safe_float(engagement.get("share_count"))
    comments = _safe_float(engagement.get("comment_count"))
    return round((likes + shares * 2 + comments * 1.5) / views, 6)


def _extract_performance_metrics(item: dict[str, Any]) -> dict[str, Any]:
    engagement = item.get("engagement") or {}
    views = int(_safe_float(engagement.get("play_count")))
    likes = int(_safe_float(engagement.get("digg_count")))
    shares = int(_safe_float(engagement.get("share_count")))
    comments = int(_safe_float(engagement.get("comment_count")))

    watch_time_proxy = round(views * min(1.0, _compute_engagement_rate(engagement) * 10), 2)

    return {
        "views": views,
        "likes": likes,
        "shares": shares,
        "comments": comments,
        "watch_time": watch_time_proxy,
        "engagement_rate": _compute_engagement_rate(engagement),
        "url": item.get("url") or "",
        "author": item.get("author") or "",
        "caption_preview": (item.get("caption") or "")[:200],
        "source": item.get("source") or "apify",
    }


def _fetch_queue_items(supabase, table: str, account_id: str) -> list[dict[str, Any]]:
    try:
        response = (
            supabase.table(table)
            .select("id,account_id,caption,hook,product_name,status,metadata")
            .eq("account_id", account_id)
            .in_("status", ["queued", "posted"])
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        logger.warning("Failed to fetch queue items for performance tracking: %s", exc)
        return []


def _match_content_to_apify(
    queue_item: dict[str, Any],
    apify_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Best-effort match of queue content to Apify video by caption/product overlap."""
    caption = str(queue_item.get("caption") or "").lower()
    product = str(queue_item.get("product_name") or "").lower()
    hook = str(queue_item.get("hook") or "").lower()

    if not caption and not product and not hook:
        return None

    best_item: dict[str, Any] | None = None
    best_score = 0.0

    for item in apify_items:
        item_caption = str(item.get("caption") or "").lower()
        if not item_caption:
            continue

        score = 0.0
        if product and product in item_caption:
            score += 0.5
        if caption and any(word in item_caption for word in caption.split()[:5] if len(word) > 3):
            score += 0.3
        if hook and any(word in item_caption for word in hook.split()[:5] if len(word) > 3):
            score += 0.2

        if score > best_score:
            best_score = score
            best_item = item

    return best_item if best_score >= 0.3 else None


def _store_performance_snapshot(
    supabase,
    table: str,
    content_id: str,
    account_id: str,
    metrics: dict[str, Any],
) -> bool:
    try:
        supabase.table(table).insert({
            "content_id": content_id,
            "account_id": account_id,
            "performance_metrics": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception as exc:
        logger.warning("Failed to store performance snapshot: %s", exc)
        return False


def trackContentPerformance(account_id: str) -> dict[str, Any]:
    """
    Track performance metrics for queued/posted content via Apify.

    Never raises; returns {"tracked": N, "skipped": N, "error": None, "snapshots": []}.
    """
    result = _empty_result()
    account = str(account_id or "").strip()
    if not account:
        result["error"] = "missing_account_id"
        return result

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            result["error"] = "missing_supabase_credentials"
            return result

        queue_table = os.getenv("CONTENT_QUEUE_TABLE", DEFAULT_QUEUE_TABLE)
        perf_table = os.getenv("CONTENT_PERFORMANCE_TABLE", DEFAULT_PERFORMANCE_TABLE)

        queue_items = _fetch_queue_items(supabase, queue_table, account)
        if not queue_items:
            return result

        apify_result = fetch_tiktok_via_apify()
        apify_items = apify_result.get("items") or [] if apify_result.get("success") else []

        if not apify_items:
            result["skipped"] = len(queue_items)
            if apify_result.get("error"):
                result["error"] = apify_result["error"]
            return result

        snapshots: list[dict[str, Any]] = []

        for queue_item in queue_items:
            content_id = queue_item.get("id")
            if not content_id:
                result["skipped"] += 1
                continue

            matched = _match_content_to_apify(queue_item, apify_items)
            if not matched:
                result["skipped"] += 1
                continue

            metrics = _extract_performance_metrics(matched)
            metrics["matched_queue_caption"] = queue_item.get("caption") or ""
            metrics["matched_product"] = queue_item.get("product_name") or ""

            if _store_performance_snapshot(supabase, perf_table, content_id, account, metrics):
                snapshots.append({"content_id": content_id, "metrics": metrics})
                result["tracked"] += 1
            else:
                result["skipped"] += 1

        result["snapshots"] = snapshots
        return result

    except Exception as exc:
        logger.warning("trackContentPerformance failed: %s", exc)
        result["error"] = str(exc)
        return result
