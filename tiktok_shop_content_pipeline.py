"""
TikTok Shop content pipeline — monetisation attachment with inventory gate.

Runs content preparation stages end-to-end. Product attachment is the ONLY step
that can pause; the pipeline never fails due to missing catalog inventory.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tiktok_shop_inventory_gate import (
    build_inventory_gap_event,
    build_inventory_gap_notification,
    checkProductAvailability,
    register_paused_attachment,
    resumeAfterInventoryUpdate,
)

logger = logging.getLogger(__name__)


def _resolve_product_name(item: dict[str, Any]) -> str:
    return (
        (item.get("product_name") or item.get("product") or item.get("suggested_product") or "")
        .strip()
    )


def _run_content_stages(item: dict[str, Any]) -> dict[str, Any]:
    """Non-monetisation content stages — always execute."""
    keyword = (item.get("keyword") or item.get("topic") or "").strip()
    return {
        "content_id": item.get("content_id") or str(uuid.uuid4()),
        "keyword": keyword,
        "hooks_ready": bool(keyword),
        "hashtags_ready": bool(keyword),
        "caption_ready": bool(keyword),
        "stage": "content_attachment",
    }


def attach_product_with_inventory_gate(
    *,
    account_id: str,
    content_item: dict[str, Any],
    tiktok_shop_catalog: list[dict[str, Any]],
    pipeline_run_id: str,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """
    Attempt product attachment; pause only this step when inventory is missing.

    Never blocks earlier content stages and never fabricates product IDs.
    """
    product_name = _resolve_product_name(content_item)
    content_id = content_item.get("content_id") or str(uuid.uuid4())
    availability = checkProductAvailability(product_name, tiktok_shop_catalog)

    base = {
        "content_id": content_id,
        "pipeline_run_id": pipeline_run_id,
        "product_name": product_name,
        "availability": availability,
    }

    if availability.get("attachable"):
        return {
            **base,
            "attachment_status": "attached",
            "product_id": availability["product_id"],
            "paused": False,
        }

    paused = register_paused_attachment(
        account_id,
        product_name=product_name,
        content_id=content_id,
        pipeline_run_id=pipeline_run_id,
        availability=availability,
        state_path=state_path,
    )
    gap_event = build_inventory_gap_event(availability)
    notification = build_inventory_gap_notification(availability)

    logger.info(
        "Inventory gap for account=%s product=%r — pausing attachment only",
        account_id,
        product_name,
    )

    return {
        **base,
        "attachment_status": "paused_inventory_gap",
        "product_id": None,
        "paused": True,
        "inventory_gap_event": gap_event,
        "notification_event": notification,
        "paused_record": paused,
    }


def run_tiktok_shop_content_pipeline(
    *,
    account_id: str,
    content_items: list[dict[str, Any]],
    tiktok_shop_catalog: list[dict[str, Any]],
    state_path: Path | None = None,
) -> dict[str, Any]:
    """
    Execute the full content pipeline with inventory-gated monetisation.

    Content stages always complete. Missing catalog products pause attachment only.
    """
    pipeline_run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    results: list[dict[str, Any]] = []
    inventory_gap_events: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []
    attached_count = 0
    paused_count = 0

    for item in content_items:
        if not isinstance(item, dict):
            continue

        content_stage = _run_content_stages(item)
        item_with_id = {**item, "content_id": content_stage["content_id"]}

        attachment = attach_product_with_inventory_gate(
            account_id=account_id,
            content_item=item_with_id,
            tiktok_shop_catalog=tiktok_shop_catalog,
            pipeline_run_id=pipeline_run_id,
            state_path=state_path,
        )

        if attachment.get("paused"):
            paused_count += 1
            if attachment.get("inventory_gap_event"):
                inventory_gap_events.append(attachment["inventory_gap_event"])
            if attachment.get("notification_event"):
                notifications.append(attachment["notification_event"])
        else:
            attached_count += 1

        results.append({
            **content_stage,
            **attachment,
            "pipeline_status": "completed_with_pause" if attachment.get("paused") else "completed",
        })

    return {
        "success": True,
        "pipeline_run_id": pipeline_run_id,
        "account_id": account_id,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_status": "completed",
        "content_items_processed": len(results),
        "attached_count": attached_count,
        "paused_attachment_count": paused_count,
        "results": results,
        "inventory_gap_events": inventory_gap_events,
        "notifications": notifications,
        "message": (
            "Pipeline completed. "
            f"{attached_count} product(s) attached, "
            f"{paused_count} attachment(s) paused for Showcase onboarding."
        ),
    }


__all__ = [
    "attach_product_with_inventory_gate",
    "resumeAfterInventoryUpdate",
    "run_tiktok_shop_content_pipeline",
]
