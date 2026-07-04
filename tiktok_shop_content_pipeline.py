"""
TikTok Shop content pipeline — monetisation attachment with predictive inventory intelligence.

Pipeline order:
  1. trend detection (input)
  2. product prediction (predictive layer)
  3. inventory pre-check (predictive layer)
  4. content generation (mode-adjusted: product_specific | category_substitute | generic)
  5. product attachment (reactive inventory gate — fallback)
  6. queue system (results aggregation)
  7. learning engine (prediction metadata for feedback)

Product attachment is the ONLY reactive step that can pause; the predictive layer
prevents blind product-specific content generation when catalog items are missing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tiktok_inventory_predictor import (
    resolve_content_mode,
    run_predictive_inventory_intelligence,
)
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


def _normalize_key(value: str) -> str:
    return (value or "").strip().lower()


def _apply_content_mode(
    item: dict[str, Any],
    content_mode: dict[str, Any] | None,
) -> dict[str, Any]:
    """Adjust content item before generation based on predictive content mode."""
    adjusted = dict(item)
    if not content_mode:
        return adjusted

    mode = content_mode.get("mode", "product_specific")
    adjusted["content_mode"] = mode

    if mode == "category_substitute":
        adjusted["product_name"] = content_mode.get("product_name") or adjusted.get("product_name")
        adjusted["product"] = adjusted["product_name"]
        adjusted["original_product_name"] = content_mode.get("original_product_name")
        adjusted["substitution_type"] = content_mode.get("substitution_type")
    elif mode == "generic":
        adjusted["generic_content"] = True
        adjusted["pause_product_attachment"] = content_mode.get("pause_product_content", True)
        adjusted["product_attachment_skipped_reason"] = content_mode.get("fallback_reason")

    return adjusted


def _run_content_stages(item: dict[str, Any]) -> dict[str, Any]:
    """Content generation stages — always execute; mode may be generic or substituted."""
    keyword = (item.get("keyword") or item.get("topic") or "").strip()
    mode = item.get("content_mode", "product_specific")
    return {
        "content_id": item.get("content_id") or str(uuid.uuid4()),
        "keyword": keyword,
        "content_mode": mode,
        "hooks_ready": bool(keyword),
        "hashtags_ready": bool(keyword),
        "caption_ready": bool(keyword),
        "generic_content": bool(item.get("generic_content")),
        "stage": "content_generation",
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

    Reactive fallback — predictive layer should have already adjusted content mode.
    Never blocks earlier content stages and never fabricates product IDs.
    """
    if content_item.get("pause_product_attachment") or content_item.get("generic_content"):
        return {
            "content_id": content_item.get("content_id") or str(uuid.uuid4()),
            "pipeline_run_id": pipeline_run_id,
            "product_name": _resolve_product_name(content_item),
            "attachment_status": "skipped_generic_mode",
            "product_id": None,
            "paused": False,
            "availability": {"status": "skipped", "attachable": False},
            "skip_reason": content_item.get("product_attachment_skipped_reason", "generic_content"),
        }

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
        "Inventory gap (reactive fallback) for account=%s product=%r — pausing attachment only",
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


def _lookup_content_mode(
    product_name: str,
    predictive: dict[str, Any],
    tiktok_shop_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve content mode from predictive pre-check results or compute on the fly."""
    key = _normalize_key(product_name)
    for entry in predictive.get("ready_products", []) + [
        {**p, "pre_check": p.get("pre_check", {})}
        for p in predictive.get("likely_needed_products", [])
    ]:
        if _normalize_key(entry.get("product_name", "")) == key:
            mode = entry.get("content_mode")
            if mode:
                return mode

    for pc in predictive.get("pre_check_results", []):
        if _normalize_key(pc.get("product_name", "")) == key:
            return resolve_content_mode(product_name, pc, tiktok_shop_catalog)

    return resolve_content_mode(product_name, None, tiktok_shop_catalog)


def run_tiktok_shop_content_pipeline(
    *,
    account_id: str,
    content_items: list[dict[str, Any]],
    tiktok_shop_catalog: list[dict[str, Any]],
    trends: dict[str, Any] | list[dict[str, Any]] | None = None,
    niche: str = "general",
    historical_content: list[dict[str, Any]] | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """
    Execute the full content pipeline with predictive inventory intelligence.

    Steps 1–3 run once per pipeline invocation. Content generation and attachment
    run per item. Missing catalog products trigger prevention events upstream;
    the reactive inventory gate remains as attachment-time fallback.
    """
    pipeline_run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    # Steps 1–3: trend input → product prediction → inventory pre-check
    predictive = run_predictive_inventory_intelligence(
        trends=trends,
        niche=niche,
        historical_content=historical_content,
        tiktok_shop_catalog=tiktok_shop_catalog,
    )

    results: list[dict[str, Any]] = []
    inventory_gap_events: list[dict[str, Any]] = []
    inventory_prevention_events: list[dict[str, Any]] = list(
        predictive.get("inventory_prevention_events", [])
    )
    notifications: list[dict[str, Any]] = []
    attached_count = 0
    paused_count = 0
    skipped_generic_count = 0
    substituted_count = 0

    for item in content_items:
        if not isinstance(item, dict):
            continue

        product_name = _resolve_product_name(item)
        content_mode = _lookup_content_mode(product_name, predictive, tiktok_shop_catalog)
        adjusted_item = _apply_content_mode(item, content_mode)

        if content_mode.get("mode") == "category_substitute":
            substituted_count += 1

        # Step 4: content generation (always runs)
        content_stage = _run_content_stages(adjusted_item)
        item_with_id = {**adjusted_item, "content_id": content_stage["content_id"]}

        # Step 5: product attachment (reactive gate fallback)
        attachment = attach_product_with_inventory_gate(
            account_id=account_id,
            content_item=item_with_id,
            tiktok_shop_catalog=tiktok_shop_catalog,
            pipeline_run_id=pipeline_run_id,
            state_path=state_path,
        )

        if attachment.get("attachment_status") == "skipped_generic_mode":
            skipped_generic_count += 1
        elif attachment.get("paused"):
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
            "content_mode_detail": content_mode,
            "pipeline_status": "completed_with_pause" if attachment.get("paused") else "completed",
        })

    # Step 6: queue system — aggregated results
    # Step 7: learning engine metadata — prediction snapshot for feedback loops
    learning_metadata = {
        "prediction_count": predictive.get("prediction_count", 0),
        "ready_count": predictive.get("ready_count", 0),
        "pre_add_required_count": predictive.get("pre_add_required_count", 0),
        "high_demand_gap_count": predictive.get("high_demand_gap_count", 0),
        "prevented_before_generation": len(inventory_prevention_events),
        "substituted_count": substituted_count,
        "generic_mode_count": skipped_generic_count,
    }

    return {
        "success": True,
        "pipeline_run_id": pipeline_run_id,
        "account_id": account_id,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_status": "completed",
        "pipeline_steps": [
            "trend_detection",
            "product_prediction",
            "inventory_pre_check",
            "content_generation",
            "product_attachment",
            "queue_system",
            "learning_engine",
        ],
        "predictive_intelligence": predictive,
        "learning_metadata": learning_metadata,
        "content_items_processed": len(results),
        "attached_count": attached_count,
        "paused_attachment_count": paused_count,
        "skipped_generic_count": skipped_generic_count,
        "substituted_count": substituted_count,
        "results": results,
        "inventory_prevention_events": inventory_prevention_events,
        "must_add_products": predictive.get("must_add_products", []),
        "inventory_gap_events": inventory_gap_events,
        "notifications": notifications,
        "message": (
            "Pipeline completed with predictive inventory intelligence. "
            f"{predictive.get('ready_count', 0)} product(s) ready, "
            f"{len(inventory_prevention_events)} prevention event(s), "
            f"{attached_count} attached, "
            f"{paused_count} reactive gap(s), "
            f"{skipped_generic_count} generic mode, "
            f"{substituted_count} category substitute(s)."
        ),
    }


__all__ = [
    "attach_product_with_inventory_gate",
    "resumeAfterInventoryUpdate",
    "run_tiktok_shop_content_pipeline",
]
