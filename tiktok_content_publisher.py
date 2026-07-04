"""
Content publishing queue layer for the TikTok viral loop engine.

Queues generated content packs for scheduled posting. Default mode is queue-only;
direct posting requires AUTO_POST=true and is a no-op without a configured poster.
Never raises; always returns a safe result dict.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from tiktok_automation_control import getAutomationMode

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_TABLE = "content_queue"
DEFAULT_SCHEDULE_OFFSET_HOURS = 2


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        logger.warning("Supabase credentials missing; content queue write skipped.")
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _empty_result() -> dict[str, Any]:
    return {"queued": 0, "skipped": 0, "posted": 0, "error": None, "items": []}


def _is_auto_post_enabled() -> bool:
    return os.getenv("AUTO_POST", "").strip().lower() in ("1", "true", "yes")


def _queue_dedupe_key(account_id: str, caption: str, hook: str, product_name: str) -> str:
    raw = f"{account_id}|{caption.strip().lower()}|{hook.strip().lower()}|{product_name.strip().lower()}"
    return "content_queue:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _initial_status_for_mode(automation_mode: str) -> str:
    if automation_mode == "approval_required":
        return "pending"
    return "queued"


def _normalize_hashtags(hashtags: Any) -> list[str]:
    if not hashtags:
        return []
    if isinstance(hashtags, str):
        return [h.strip() for h in hashtags.split() if h.strip()]
    if isinstance(hashtags, list):
        return [str(h).strip() for h in hashtags if str(h).strip()]
    return []


def _build_queue_items(
    account_id: str,
    content_pack: dict[str, Any],
    emerging_products: list[dict[str, Any]] | None,
    automation_mode: str = "queue_only",
) -> list[dict[str, Any]]:
    """Build queue row payloads from content pack and emerging products."""
    pack = content_pack if isinstance(content_pack, dict) else {}
    captions = [str(c).strip() for c in (pack.get("captions") or []) if str(c).strip()]
    hooks = [str(h).strip() for h in (pack.get("hook_variations") or []) if str(h).strip()]
    hashtags = _normalize_hashtags(pack.get("hashtags"))

    products = [p for p in (emerging_products or []) if isinstance(p, dict)]
    product_names = [
        str(p.get("product") or "").strip()
        for p in products
        if str(p.get("product") or "").strip()
    ]

    if not captions and not hooks:
        return []

    if not product_names:
        product_names = [""]

    if not captions:
        captions = [""]
    if not hooks:
        hooks = [""]

    now = datetime.now(timezone.utc)
    initial_status = _initial_status_for_mode(automation_mode)
    items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for i, caption in enumerate(captions[:8]):
        product_name = product_names[i % len(product_names)]
        hook = hooks[i % len(hooks)]
        dedupe_key = _queue_dedupe_key(account_id, caption, hook, product_name)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        scheduled_time = (now + timedelta(hours=DEFAULT_SCHEDULE_OFFSET_HOURS + i)).isoformat()
        items.append({
            "account_id": account_id,
            "caption": caption,
            "hashtags": hashtags,
            "hook": hook,
            "product_name": product_name,
            "status": initial_status,
            "scheduled_time": scheduled_time,
            "dedupe_key": dedupe_key,
            "metadata": {
                "source": "content_pack",
                "index": i,
                "automation_mode": automation_mode,
            },
        })

    return items


def _fetch_existing_dedupe_keys(supabase, table: str, keys: list[str]) -> set[str]:
    if not keys:
        return set()
    try:
        response = (
            supabase.table(table)
            .select("dedupe_key")
            .in_("dedupe_key", keys)
            .execute()
        )
        return {row["dedupe_key"] for row in (response.data or []) if row.get("dedupe_key")}
    except Exception as exc:
        logger.warning("Failed to fetch existing queue keys: %s", exc)
        return set()


def _attempt_auto_post(
    supabase,
    table: str,
    row: dict[str, Any],
    automation_mode: str,
) -> dict[str, Any]:
    """
    Attempt direct posting only when automation_mode is auto_post and AUTO_POST=true.

    No TikTok posting API is configured in this system; entries remain queued
    with metadata noting auto-post was requested but no poster is available.
    """
    if automation_mode != "auto_post" or not _is_auto_post_enabled():
        return row

    row = dict(row)
    row["metadata"] = {
        **(row.get("metadata") or {}),
        "auto_post_requested": True,
        "auto_post_result": "no_poster_configured",
    }
    return row


def queueContentForPosting(
    account_id: str,
    content_pack: dict[str, Any] | None,
    emerging_products: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Queue content pack items for scheduled posting.

    Idempotent via dedupe_key. Default mode is queue-only (AUTO_POST=false).
    Never raises; returns {"queued": N, "skipped": N, "posted": 0, "error": None, "items": []}.
    """
    result = _empty_result()
    account = str(account_id or "").strip()
    if not account:
        result["error"] = "missing_account_id"
        return result

    try:
        automation_mode = getAutomationMode(account)
        table = os.getenv("CONTENT_QUEUE_TABLE", DEFAULT_QUEUE_TABLE)
        items = _build_queue_items(
            account,
            content_pack or {},
            emerging_products,
            automation_mode=automation_mode,
        )
        if not items:
            return result

        supabase = _get_supabase_client()
        if supabase is None:
            result["skipped"] = len(items)
            result["error"] = "missing_supabase_credentials"
            return result

        dedupe_keys = [item["dedupe_key"] for item in items]
        existing = _fetch_existing_dedupe_keys(supabase, table, dedupe_keys)

        queued_items: list[dict[str, Any]] = []
        for item in items:
            if item["dedupe_key"] in existing:
                result["skipped"] += 1
                continue

            payload = _attempt_auto_post(supabase, table, item, automation_mode)
            try:
                response = (
                    supabase.table(table)
                    .upsert(payload, on_conflict="dedupe_key")
                    .execute()
                )
                stored = (response.data or [payload])[0]
                queued_items.append(stored)
                result["queued"] += 1
            except Exception as exc:
                logger.warning("Content queue upsert failed: %s", exc)
                result["skipped"] += 1
                result["error"] = str(exc)

        result["items"] = queued_items
        result["automation_mode"] = automation_mode
        return result

    except Exception as exc:
        logger.warning("queueContentForPosting failed: %s", exc)
        result["error"] = str(exc)
        return result
