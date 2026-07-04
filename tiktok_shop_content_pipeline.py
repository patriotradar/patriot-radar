"""
TikTok Shop content pipeline — dual-layer inventory intelligence.

Execution flow:
  STEP 1: Predictive layer (intent decision) — tiktok_inventory_predictor.py
  STEP 2: Content mode resolver — tiktok_content_mode_resolver.py
  STEP 3: Content generation — follows resolved content_mode (never overridden)
  STEP 4: Reactive inventory gate (final safety) — tiktok_shop_inventory_gate.py

Conflict rule:
  - Reactive layer ALWAYS wins for attachment safety
  - Predictive layer ALWAYS wins for content framing
  - Either layer failing → fallback to generic content mode; pipeline continues
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tiktok_content_mode_resolver import (
    generic_fallback_mode,
    mode_allows_attachment,
    resolve_content_mode,
)
from tiktok_inventory_predictor import run_predictive_inventory_intelligence
from tiktok_shop_inventory_gate import (
    build_blocked_attachment,
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
    """Adjust content item before generation based on predictive content_mode."""
    adjusted = dict(item)
    if not content_mode:
        return adjusted

    mode = content_mode.get("mode", "generic")
    adjusted["content_mode"] = mode
    adjusted["content_mode_detail"] = content_mode

    if mode == "category_substitute":
        adjusted["product_name"] = content_mode.get("product_name") or adjusted.get("product_name")
        adjusted["product"] = adjusted["product_name"]
        adjusted["original_product_name"] = content_mode.get("original_product_name")
        adjusted["substitution_type"] = content_mode.get("substitution_type")
    elif mode in ("generic", "generic_high_priority"):
        adjusted["generic_content"] = True
        adjusted["pause_product_attachment"] = content_mode.get("pause_product_attachment", True)
        adjusted["product_attachment_skipped_reason"] = content_mode.get("fallback_reason")
        if mode == "generic_high_priority":
            adjusted["high_priority"] = True

    return adjusted


def _run_content_stages(item: dict[str, Any]) -> dict[str, Any]:
    """Content generation stages — always execute; mode set by predictive layer only."""
    keyword = (item.get("keyword") or item.get("topic") or "").strip()
    mode = item.get("content_mode", "generic")
    return {
        "content_id": item.get("content_id") or str(uuid.uuid4()),
        "keyword": keyword,
        "content_mode": mode,
        "hooks_ready": bool(keyword),
        "hashtags_ready": bool(keyword),
        "caption_ready": bool(keyword),
        "generic_content": bool(item.get("generic_content")),
        "high_priority": bool(item.get("high_priority")),
        "stage": "content_generation",
    }


def attach_product_with_inventory_gate(
    *,
    account_id: str,
    content_item: dict[str, Any],
    content_mode: dict[str, Any],
    tiktok_shop_catalog: list[dict[str, Any]],
    pipeline_run_id: str,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """
    FINAL SAFETY: reactive inventory gate for product attachment.

    Never modifies content_mode. On conflict with predictive intent:
      - blocks attachment (reactive wins safety)
      - preserves content_mode from predictive layer (predictive wins framing)
    """
    content_id = content_item.get("content_id") or str(uuid.uuid4())
    product_name = _resolve_product_name(content_item)
    mode_name = content_mode.get("mode", "generic")

    base = {
        "content_id": content_id,
        "pipeline_run_id": pipeline_run_id,
        "product_name": product_name,
        "content_mode": mode_name,
    }

    if not mode_allows_attachment(content_mode):
        return {
            **base,
            "attachment_status": "skipped_by_content_mode",
            "product_id": None,
            "paused": False,
            "availability": {"status": "skipped", "attachable": False},
            "skip_reason": content_mode.get("fallback_reason", "content_mode_no_attachment"),
            "layer": "reactive",
        }

    attach_name = content_mode.get("product_name") or product_name
    availability = checkProductAvailability(attach_name, tiktok_shop_catalog)
    base["availability"] = availability

    if availability.get("attachable"):
        return {
            **base,
            "attachment_status": "attached",
            "product_id": availability["product_id"],
            "paused": False,
            "layer": "reactive",
        }

    paused = register_paused_attachment(
        account_id,
        product_name=attach_name,
        content_id=content_id,
        pipeline_run_id=pipeline_run_id,
        availability=availability,
        state_path=state_path,
    )
    gap_event = build_inventory_gap_event(availability)
    notification = build_inventory_gap_notification(availability)
    blocked = build_blocked_attachment(
        content_id=content_id,
        product_name=attach_name,
        content_mode=mode_name,
        availability=availability,
        reason="reactive_safety_block",
    )

    logger.info(
        "Reactive gate blocked attachment for account=%s product=%r mode=%s",
        account_id,
        attach_name,
        mode_name,
    )

    return {
        **base,
        "attachment_status": "blocked_inventory_gap",
        "product_id": None,
        "paused": True,
        "inventory_gap_event": gap_event,
        "notification_event": notification,
        "blocked_attachment": blocked,
        "paused_record": paused,
        "layer": "reactive",
    }


def _lookup_content_mode(
    product_name: str,
    demand_score: float,
    predictive: dict[str, Any],
    tiktok_shop_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve content mode from predictive suggestions or compute via resolver."""
    key = _normalize_key(product_name)

    for suggestion in predictive.get("content_mode_suggestions", []):
        if _normalize_key(suggestion.get("product_name", "")) == key:
            mode = suggestion.get("content_mode")
            if mode:
                return mode

    for entry in predictive.get("ready_products", []):
        if _normalize_key(entry.get("product_name", "")) == key:
            mode = entry.get("content_mode")
            if mode:
                return mode

    for pc in predictive.get("pre_check_results", []):
        if _normalize_key(pc.get("product_name", "")) == key:
            try:
                return resolve_content_mode(
                    product_name,
                    demand_score,
                    pc.get("availability"),
                    tiktok_shop_catalog,
                )
            except Exception:
                logger.exception("Content mode lookup failed for %s", product_name)
                return generic_fallback_mode(product_name)

    try:
        return resolve_content_mode(
            product_name,
            demand_score,
            None,
            tiktok_shop_catalog,
        )
    except Exception:
        logger.exception("Content mode fallback failed for %s", product_name)
        return generic_fallback_mode(product_name)


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
    Execute the full dual-layer content pipeline.

    Predictive guides content strategy; reactive gating guarantees monetisation safety.
    """
    pipeline_run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    # STEP 1: Predictive layer (intent decision)
    try:
        predictive = run_predictive_inventory_intelligence(
            trends=trends,
            niche=niche,
            historical_content=historical_content,
            tiktok_shop_catalog=tiktok_shop_catalog,
        )
    except Exception:
        logger.exception("Predictive layer failed — continuing with empty intent")
        predictive = {
            "success": False,
            "layer": "predictive",
            "likely_needed_products": [],
            "content_mode_suggestions": [],
            "inventory_prevention_events": [],
            "must_add_products": [],
            "ready_products": [],
            "ready_count": 0,
            "pre_add_required_count": 0,
            "high_demand_gap_count": 0,
        }

    results: list[dict[str, Any]] = []
    inventory_gap_events: list[dict[str, Any]] = []
    blocked_attachments: list[dict[str, Any]] = []
    inventory_prevention_events: list[dict[str, Any]] = list(
        predictive.get("inventory_prevention_events", [])
    )
    notifications: list[dict[str, Any]] = []
    attached_count = 0
    blocked_count = 0
    skipped_mode_count = 0
    substituted_count = 0

    for item in content_items:
        if not isinstance(item, dict):
            continue

        product_name = _resolve_product_name(item)
        demand_score = 0.0
        for p in predictive.get("likely_needed_products", []):
            if _normalize_key(p.get("product_name", "")) == _normalize_key(product_name):
                demand_score = float(p.get("demand_score", 0.0))
                break

        # STEP 2: Content mode resolver (predictive framing — immutable after this)
        content_mode = _lookup_content_mode(
            product_name, demand_score, predictive, tiktok_shop_catalog
        )
        adjusted_item = _apply_content_mode(item, content_mode)

        if content_mode.get("mode") == "category_substitute":
            substituted_count += 1

        # STEP 3: Content generation (always runs; never overrides content_mode)
        content_stage = _run_content_stages(adjusted_item)
        item_with_id = {**adjusted_item, "content_id": content_stage["content_id"]}

        # STEP 4: Reactive inventory gate (final safety — never changes content_mode)
        try:
            attachment = attach_product_with_inventory_gate(
                account_id=account_id,
                content_item=item_with_id,
                content_mode=content_mode,
                tiktok_shop_catalog=tiktok_shop_catalog,
                pipeline_run_id=pipeline_run_id,
                state_path=state_path,
            )
        except Exception:
            logger.exception("Reactive gate failed for %s — skipping attachment", product_name)
            attachment = {
                "content_id": content_stage["content_id"],
                "pipeline_run_id": pipeline_run_id,
                "product_name": product_name,
                "content_mode": content_mode.get("mode", "generic"),
                "attachment_status": "gate_failed",
                "product_id": None,
                "paused": False,
                "layer": "reactive",
                "skip_reason": "reactive_gate_failed",
            }

        status = attachment.get("attachment_status")
        if status == "skipped_by_content_mode":
            skipped_mode_count += 1
        elif status in ("blocked_inventory_gap", "paused_inventory_gap"):
            blocked_count += 1
            if attachment.get("inventory_gap_event"):
                inventory_gap_events.append(attachment["inventory_gap_event"])
            if attachment.get("notification_event"):
                notifications.append(attachment["notification_event"])
            if attachment.get("blocked_attachment"):
                blocked_attachments.append(attachment["blocked_attachment"])
        elif status == "attached":
            attached_count += 1

        results.append({
            **content_stage,
            **attachment,
            "content_mode_detail": content_mode,
            "pipeline_status": "completed",
        })

    learning_metadata = {
        "prediction_count": predictive.get("prediction_count", 0),
        "ready_count": predictive.get("ready_count", 0),
        "pre_add_required_count": predictive.get("pre_add_required_count", 0),
        "high_demand_gap_count": predictive.get("high_demand_gap_count", 0),
        "prevented_before_generation": len(inventory_prevention_events),
        "substituted_count": substituted_count,
        "skipped_by_content_mode_count": skipped_mode_count,
        "blocked_attachment_count": blocked_count,
    }

    return {
        "success": True,
        "pipeline_run_id": pipeline_run_id,
        "account_id": account_id,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_status": "completed",
        "architecture": "dual_layer_inventory_intelligence",
        "hierarchy": {
            "predictive": "intent_decision",
            "reactive": "final_safety_enforcement",
            "conflict_rule": "reactive_wins_attachment_predictive_wins_framing",
        },
        "pipeline_steps": [
            "predictive_layer",
            "content_mode_resolver",
            "content_generation",
            "reactive_inventory_gate",
            "queue_system",
            "learning_engine",
        ],
        "predictive_intelligence": predictive,
        "learning_metadata": learning_metadata,
        "content_items_processed": len(results),
        "attached_count": attached_count,
        "blocked_attachment_count": blocked_count,
        "skipped_by_content_mode_count": skipped_mode_count,
        "substituted_count": substituted_count,
        "results": results,
        "inventory_prevention_events": inventory_prevention_events,
        "must_add_products": predictive.get("must_add_products", []),
        "inventory_gap_events": inventory_gap_events,
        "blocked_attachments": blocked_attachments,
        "notifications": notifications,
        "message": (
            "Dual-layer pipeline completed. "
            f"Predictive: {predictive.get('ready_count', 0)} ready, "
            f"{len(inventory_prevention_events)} prevention event(s). "
            f"Reactive: {attached_count} attached, "
            f"{blocked_count} blocked, "
            f"{skipped_mode_count} skipped by content mode."
        ),
    }


__all__ = [
    "attach_product_with_inventory_gate",
    "resumeAfterInventoryUpdate",
    "run_tiktok_shop_content_pipeline",
]
