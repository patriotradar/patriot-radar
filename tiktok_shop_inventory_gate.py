"""
TikTok Shop reactive inventory gate — FINAL SAFETY ENFORCEMENT.

Ensures no invalid product attachment occurs and prevents hallucinated or missing
product IDs. Never overrides content_mode (predictive layer owns content framing).

Does not modify trends.py, trend_shift_engine.py, or existing scan pipelines.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STATE_PATH = Path(__file__).resolve().parent / "data" / "tiktok_shop_inventory_state.json"

_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("army", "military", "veteran", "raf", "navy", "troops"), "military"),
    (("flag", "union jack", "union flag", "st george"), "flags"),
    (("churchill", "history", "heritage", "ww2", "d-day", "dunkirk"), "history"),
    (("hoodie", "clothing", "apparel", "wear"), "clothing"),
    (("remembrance", "poppy", "cenotaph"), "remembrance"),
    (("spitfire", "hurricane", "battle of britain"), "aviation"),
    (("king", "royal", "monarchy", "crown", "queen"), "royal"),
    (("skincare", "serum", "moisturizer", "acne"), "skincare"),
    (("makeup", "cosmetic", "lipstick", "beauty"), "beauty"),
    (("fitness", "workout", "gym", "protein"), "fitness"),
    (("book", "books"), "books"),
]


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def infer_category(product_name: str) -> str:
    """Infer a product category from the product name using keyword rules."""
    lowered = _normalize_name(product_name)
    for keywords, category in _CATEGORY_RULES:
        if any(kw in lowered for kw in keywords):
            return category
    return "general"


def _catalog_entry_name(entry: dict[str, Any]) -> str:
    return str(entry.get("name") or entry.get("product_name") or entry.get("title") or "")


def _catalog_entry_category(entry: dict[str, Any]) -> str:
    explicit = entry.get("category")
    if explicit:
        return str(explicit).lower()
    return infer_category(_catalog_entry_name(entry))


def _find_exact_match(product_name: str, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = _normalize_name(product_name)
    if not target:
        return None
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        if _normalize_name(_catalog_entry_name(entry)) == target:
            return entry
    return None


def _find_category_match(product_name: str, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    target_category = infer_category(product_name)
    if target_category == "general":
        return None
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        if _catalog_entry_category(entry) == target_category:
            product_id = entry.get("product_id")
            if product_id:
                return entry
    return None


def checkProductAvailability(
    product_name: str,
    tiktok_shop_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Search the TikTok Shop catalog for a product by exact name, then category.

    Never fabricates product IDs. Returns attachable=False when no real match exists.
    """
    catalog = [c for c in (tiktok_shop_catalog or []) if isinstance(c, dict)]
    product_name = (product_name or "").strip()

    if not product_name:
        return {
            "status": "missing",
            "product_id": None,
            "attachable": False,
            "action_required": "add_to_showcase",
            "suggested_product": product_name,
            "category": "general",
            "match_type": None,
        }

    match = _find_exact_match(product_name, catalog)
    match_type = "exact"
    if not match:
        match = _find_category_match(product_name, catalog)
        match_type = "category" if match else None

    if match:
        product_id = match.get("product_id")
        if not product_id:
            logger.warning(
                "Catalog match for %r lacks product_id — treating as missing",
                product_name,
            )
        else:
            return {
                "status": "available",
                "product_id": str(product_id),
                "attachable": True,
                "match_type": match_type,
                "matched_name": _catalog_entry_name(match),
                "category": _catalog_entry_category(match),
            }

    return {
        "status": "missing",
        "product_id": None,
        "attachable": False,
        "action_required": "add_to_showcase",
        "suggested_product": product_name,
        "category": infer_category(product_name),
        "match_type": None,
    }


def build_inventory_gap_event(availability: dict[str, Any]) -> dict[str, Any]:
    """Build the dashboard inventory_gap_event payload."""
    return {
        "product_name": availability.get("suggested_product") or "",
        "category": availability.get("category") or "general",
        "message": "Add this product to your TikTok Shop Showcase",
        "status": "waiting_user_action",
        "action_required": availability.get("action_required", "add_to_showcase"),
    }


def build_inventory_gap_notification(availability: dict[str, Any]) -> dict[str, Any]:
    """Build the pipeline inventory_gap_detected notification event."""
    product_name = availability.get("suggested_product") or "Unknown product"
    return {
        "event": "inventory_gap_detected",
        "product_name": product_name,
        "category": availability.get("category") or "general",
        "message": (
            f"Product '{product_name}' is not in your TikTok Shop catalog. "
            "Add it to Showcase to enable attachment."
        ),
        "status": "waiting_user_action",
        "action_required": "add_to_showcase",
    }


def build_blocked_attachment(
    *,
    content_id: str,
    product_name: str,
    content_mode: str,
    availability: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Record a reactive-layer blocked attachment (safety enforcement)."""
    return {
        "content_id": content_id,
        "product_name": product_name,
        "content_mode": content_mode,
        "reason": reason,
        "availability": availability,
        "inventory_gap_event": build_inventory_gap_event(availability),
        "notification": build_inventory_gap_notification(availability),
    }


def _load_state(path: Path | None = None) -> dict[str, Any]:
    state_path = path or _DEFAULT_STATE_PATH
    try:
        if state_path.exists():
            with open(state_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        logger.exception("Failed to load inventory state from %s", state_path)
    return {"accounts": {}}


def _save_state(state: dict[str, Any], path: Path | None = None) -> None:
    state_path = path or _DEFAULT_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def register_paused_attachment(
    account_id: str,
    *,
    product_name: str,
    content_id: str,
    pipeline_run_id: str,
    availability: dict[str, Any],
    state_path: Path | None = None,
) -> dict[str, Any]:
    """Record a paused product attachment for later resume."""
    state = _load_state(state_path)
    accounts = state.setdefault("accounts", {})
    account = accounts.setdefault(account_id, {"paused_attachments": []})

    paused = {
        "content_id": content_id,
        "pipeline_run_id": pipeline_run_id,
        "product_name": product_name,
        "category": availability.get("category"),
        "inventory_gap_event": build_inventory_gap_event(availability),
        "notification": build_inventory_gap_notification(availability),
        "paused_at": datetime.now(timezone.utc).isoformat(),
        "status": "waiting_user_action",
    }
    account["paused_attachments"] = [
        p for p in account.get("paused_attachments", [])
        if p.get("content_id") != content_id
    ]
    account["paused_attachments"].append(paused)
    _save_state(state, state_path)
    return paused


def get_paused_attachments(
    account_id: str,
    state_path: Path | None = None,
) -> list[dict[str, Any]]:
    state = _load_state(state_path)
    account = state.get("accounts", {}).get(account_id, {})
    return list(account.get("paused_attachments", []))


def resumeAfterInventoryUpdate(
    account_id: str,
    tiktok_shop_catalog: list[dict[str, Any]],
    *,
    content_id: str | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """
    Re-run product match ONLY for paused attachments — does not re-run the full pipeline.

    If the product is now available, marks the attachment as resumed with the real product_id.
  Never modifies content_mode.
    """
    state = _load_state(state_path)
    account = state.get("accounts", {}).get(account_id)
    if not account:
        return {
            "success": True,
            "account_id": account_id,
            "resumed": [],
            "still_waiting": [],
            "message": "No paused attachments for this account.",
        }

    paused_list = account.get("paused_attachments", [])
    if content_id:
        paused_list = [p for p in paused_list if p.get("content_id") == content_id]

    resumed: list[dict[str, Any]] = []
    still_waiting: list[dict[str, Any]] = []

    for paused in paused_list:
        product_name = paused.get("product_name") or ""
        availability = checkProductAvailability(product_name, tiktok_shop_catalog)

        if availability.get("attachable"):
            attachment = {
                "content_id": paused.get("content_id"),
                "pipeline_run_id": paused.get("pipeline_run_id"),
                "product_name": product_name,
                "product_id": availability["product_id"],
                "status": "attached",
                "resumed_at": datetime.now(timezone.utc).isoformat(),
                "match_type": availability.get("match_type"),
            }
            resumed.append(attachment)
            paused["status"] = "resumed"
            paused["product_id"] = availability["product_id"]
        else:
            still_waiting.append({
                **paused,
                "inventory_gap_event": build_inventory_gap_event(availability),
                "status": "waiting_user_action",
            })

    remaining = [
        p for p in account.get("paused_attachments", [])
        if p.get("status") != "resumed"
    ]
    account["paused_attachments"] = remaining
    _save_state(state, state_path)

    return {
        "success": True,
        "account_id": account_id,
        "resumed": resumed,
        "still_waiting": still_waiting,
        "message": (
            f"Resumed {len(resumed)} attachment(s); "
            f"{len(still_waiting)} still waiting for Showcase onboarding."
        ),
    }


__all__ = [
    "infer_category",
    "checkProductAvailability",
    "build_inventory_gap_event",
    "build_inventory_gap_notification",
    "build_blocked_attachment",
    "register_paused_attachment",
    "get_paused_attachments",
    "resumeAfterInventoryUpdate",
]
