"""
Live state assembly layer for TikTok SaaS frontend consumption.

Step 1: buildSystemSnapshot(account_id) captures module state once per request.
Step 2: assembleLiveState formats snapshot data into the strict UI contract.
Core pipeline: trend → content → plan → insights.
Commerce add-on gated by commerce_mode / features.commerce_mode.
RBAC access block is appended read-only; does not alter core assembly logic.
"""

from __future__ import annotations

import logging
from typing import Any

from action_orchestrator import generatePrimaryActions
from tiktok_access_control import (
    buildAccessContext,
    empty_live_state_contract,
    filterLiveStateForAccess,
    _load_feature_flags,
)
from tiktok_system_snapshot_builder import buildSystemSnapshot, empty_system_snapshot

logger = logging.getLogger(__name__)

_last_valid_state: dict[str, dict[str, Any]] = {}

_REQUIRED_SNAPSHOT_KEYS = frozenset({
    "trends_snapshot",
    "product_snapshot",
    "inventory_snapshot",
    "queue_snapshot",
    "approval_snapshot",
    "performance_snapshot",
    "learning_snapshot",
    "system_health_snapshot",
})


def _empty_contract() -> dict[str, Any]:
    return empty_live_state_contract()


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_string(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _as_number(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_commerce_mode(
    commerce_mode: bool | None,
    user_record: dict[str, Any] | None,
    flags: dict[str, bool],
) -> bool:
    if commerce_mode is not None:
        return bool(commerce_mode)
    if user_record:
        meta = user_record.get("user_metadata") or {}
        if "commerce_mode" in meta:
            return bool(meta["commerce_mode"])
    return bool(flags.get("commerce_mode", False))


def _is_valid_snapshot(snapshot: dict[str, Any]) -> bool:
    return _REQUIRED_SNAPSHOT_KEYS.issubset(snapshot.keys())


def _extract_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    trends_snapshot = _as_dict(snapshot.get("trends_snapshot"))
    product_snapshot = _as_dict(snapshot.get("product_snapshot"))
    inventory_snapshot = _as_dict(snapshot.get("inventory_snapshot"))
    queue_snapshot = _as_dict(snapshot.get("queue_snapshot"))
    approval_snapshot = _as_dict(snapshot.get("approval_snapshot"))
    performance_snapshot = _as_dict(snapshot.get("performance_snapshot"))
    learning_snapshot = _as_dict(snapshot.get("learning_snapshot"))
    system_health_snapshot = _as_dict(snapshot.get("system_health_snapshot"))

    emerging = _as_list(product_snapshot.get("emerging"))
    trending = _as_list(product_snapshot.get("trending"))

    return {
        "trends": _as_list(trends_snapshot.get("trends")),
        "emerging": emerging,
        "trending": trending,
        "inventory_gaps": _as_list(inventory_snapshot.get("inventory_gaps")),
        "inventory_prevention": _as_list(inventory_snapshot.get("inventory_prevention")),
        "content_queue": _as_list(queue_snapshot.get("content_queue")),
        "approvals": _as_list(approval_snapshot.get("approvals")),
        "performance": _as_dict(performance_snapshot.get("performance")),
        "prediction": _as_dict(learning_snapshot.get("prediction")),
        "system_health": _as_string(system_health_snapshot.get("system_health"), "unknown"),
        "raw_logs": _as_list(system_health_snapshot.get("raw_logs")),
        "partial_failures": _as_list(snapshot.get("partial_failures")),
        "account_id": _as_string(snapshot.get("account_id"), ""),
    }


def _merge_products(emerging: list, trending: list) -> list:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in emerging + trending:
        if not isinstance(item, dict):
            continue
        name = _as_string(item.get("name") or item.get("product_name"), "")
        key = name.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append({
            "name": _as_string(item.get("name") or item.get("product_name")),
            "signal_strength": _as_number(item.get("signal_strength") or item.get("score")),
            "source": _as_string(item.get("source")),
            "confidence": _as_number(item.get("confidence")),
            "evidence": _as_list(item.get("evidence")),
        })
    return merged


def _build_alerts(
    inventory_gaps: list,
    inventory_prevention: list,
    system_health: str,
    partial_failures: list[str],
    hidden_alerts: list | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    alerts: list[dict[str, str]] = []
    hidden: list[dict[str, str]] = _as_list(hidden_alerts)

    for gap in inventory_gaps:
        if not isinstance(gap, dict):
            continue
        alerts.append({
            "level": "warning",
            "code": "inventory_gap",
            "message": f"Inventory gap: {_as_string(gap.get('product_name'))}",
        })

    for item in inventory_prevention:
        if not isinstance(item, dict):
            continue
        if item.get("available") is False:
            alerts.append({
                "level": "warning",
                "code": "inventory_prevention",
                "message": f"Prevent stockout: {_as_string(item.get('product_name'))}",
            })

    if system_health == "failing":
        hidden.append({
            "level": "hidden",
            "code": "system_health",
            "message": "System health is failing",
        })
        alerts.append({
            "level": "error",
            "code": "system_health",
            "message": "System health is failing",
        })
    elif system_health == "degraded":
        hidden.append({
            "level": "hidden",
            "code": "system_health_degraded",
            "message": "System health is degraded",
        })
        alerts.append({
            "level": "warning",
            "code": "system_health",
            "message": "System health is degraded",
        })

    for module_name in partial_failures:
        hidden.append({
            "level": "hidden",
            "code": "module_partial_failure",
            "message": f"Module unavailable: {module_name}",
        })
        alerts.append({
            "level": "info",
            "code": "module_fallback",
            "message": f"Using defaults for {module_name}",
        })

    return alerts, hidden


def _derive_today_flow(
    primary_action: dict[str, str],
    *,
    inventory_gaps: list,
    approvals: list,
    content_queue: list,
    products: list,
    trends: list,
    system_health: str,
    commerce_mode: bool,
) -> dict[str, str]:
    core_step = "trend → content → plan → insights"
    commerce_step = "trend → product → content → queue"
    today_flow = {
        "step": commerce_step if commerce_mode else core_step,
        "next_action": _as_string(primary_action.get("label")),
        "status": "unknown",
    }
    action = _as_string(primary_action.get("action"))

    if inventory_gaps and action in ("prevent_inventory_stockout", "resolve_inventory_gap", "fix_inventory"):
        today_flow["status"] = "blocked"
        return today_flow

    if approvals and action in ("approve_queued_content", "approve_content", "review_approval"):
        today_flow["status"] = "awaiting_approval"
        return today_flow

    if action in ("match_products_to_trends", "monetise_trending_topic", "match_products", "monetise_trending_product"):
        today_flow["status"] = "trend_detected"
        return today_flow

    if action in ("generate_content_from_products", "create_product_content", "create_trend_content", "create_content", "generate_content"):
        today_flow["status"] = "ready_for_content"
        return today_flow

    if content_queue and action in (
        "optimise_content_schedule",
        "resolve_queue_block",
        "view_queue",
    ):
        today_flow["status"] = "in_queue"
        return today_flow

    if trends or products:
        today_flow["status"] = "active"
        return today_flow

    if system_health in ("healthy", "degraded", "failing"):
        today_flow["status"] = system_health
        return today_flow

    return today_flow


def _apply_commerce_layer(
    account_id: str,
    trends: list,
    commerce_mode: bool,
) -> dict[str, Any]:
    if not commerce_mode:
        return {"revenue_suggestions": []}
    try:
        from commerce import run_commerce_pipeline

        return run_commerce_pipeline(account_id, trends)
    except Exception as exc:
        logger.warning("Commerce layer failed for %s (core unaffected): %s", account_id, exc)
        return {"revenue_suggestions": []}


def _assemble_from_extracted(
    extracted: dict[str, Any],
    *,
    user_record: dict[str, Any] | None = None,
    commerce_mode: bool | None = None,
) -> dict[str, Any]:
    account_id = extracted["account_id"]
    partial_failures = extracted["partial_failures"]
    trends = extracted["trends"]
    products = _merge_products(extracted["emerging"], extracted["trending"])
    inventory_gaps = extracted["inventory_gaps"]
    inventory_prevention = extracted["inventory_prevention"]
    content_queue = extracted["content_queue"]
    approvals = extracted["approvals"]
    performance = extracted["performance"]
    prediction = extracted["prediction"]
    system_health = extracted["system_health"]
    raw_logs = extracted["raw_logs"]

    flags = _load_feature_flags()
    commerce_mode = _resolve_commerce_mode(commerce_mode, user_record, flags)
    access = buildAccessContext(account_id, user_record, flags, commerce_mode)
    user_role = _as_string(access.get("role"), "creator")
    admin_override = bool(access.get("admin_override"))

    orchestration_input = {
        "trends": trends,
        "products": products if commerce_mode else [],
        "inventory_prevention": inventory_prevention,
        "content_queue": content_queue,
        "performance": performance,
        "commerce_mode": commerce_mode,
        "user_role": user_role,
        "admin_override": admin_override,
        "system_health": system_health,
    }

    if commerce_mode and inventory_gaps:
        gap = inventory_gaps[0] if isinstance(inventory_gaps[0], dict) else {}
        primary_action = {
            "label": "Fix inventory gap",
            "action": "resolve_inventory_gap",
            "priority": "high",
            "context_id": _as_string(gap.get("product_name")),
            "reason": "Inventory gap blocks product attachment until resolved.",
        }
        secondary_actions: list[dict[str, str]] = []
    else:
        actions = generatePrimaryActions(orchestration_input)
        primary_action = actions["primary_action"]
        secondary_actions = actions["secondary_actions"]

    if not commerce_mode:
        inventory_gaps = []

    today_flow = _derive_today_flow(
        primary_action,
        inventory_gaps=inventory_gaps,
        approvals=approvals,
        content_queue=content_queue,
        products=products if commerce_mode else [],
        trends=trends,
        system_health=system_health,
        commerce_mode=commerce_mode,
    )

    alerts, hidden_alerts = _build_alerts(
        inventory_gaps=inventory_gaps,
        inventory_prevention=inventory_prevention,
        system_health=system_health,
        partial_failures=partial_failures,
    )

    state = _empty_contract()
    state["today_flow"] = today_flow
    state["trends"] = trends
    state["products"] = products if commerce_mode else []
    state["inventory_gaps"] = inventory_gaps
    state["inventory_prevention"] = inventory_prevention
    state["content_queue"] = content_queue
    state["approvals"] = approvals
    state["performance"] = performance
    state["prediction"] = prediction
    state["alerts"] = alerts
    state["hidden_alerts"] = hidden_alerts
    state["raw_logs"] = raw_logs
    state["primary_action"] = primary_action
    state["secondary_actions"] = secondary_actions
    state["commerce_mode"] = commerce_mode
    state["user_role"] = user_role
    state["admin_override"] = admin_override
    state["system_health"] = system_health
    state["access"] = access

    commerce_result = _apply_commerce_layer(account_id, trends, commerce_mode)
    if commerce_mode:
        state["revenue_suggestions"] = _as_list(commerce_result.get("revenue_suggestions"))

    result = filterLiveStateForAccess(state, access)
    result["features"] = {"commerce_mode": commerce_mode}

    if not commerce_mode:
        result["today_flow"] = {
            "step": "trend → content → plan → insights",
            "next_action": "View content plan",
            "status": result["today_flow"].get("status", "ready"),
        }
        result["products"] = []
        result["inventory_gaps"] = []
        result["primary_action"] = {
            "label": "View content plan",
            "action": "view_plan",
            "context_id": "plan",
            "priority": "medium",
            "reason": "Commerce mode off — focus on core content workflow.",
        }
    elif "revenue_suggestions" in state:
        result["revenue_suggestions"] = state["revenue_suggestions"]

    return result


def assembleLiveStateFromSnapshot(
    snapshot: dict[str, Any],
    user_record: dict[str, Any] | None = None,
    *,
    commerce_mode: bool | None = None,
) -> dict[str, Any]:
    """Assemble UI contract from a pre-built system snapshot. Never raises."""
    account_id = str(snapshot.get("account_id") or "") if isinstance(snapshot, dict) else ""
    try:
        if not isinstance(snapshot, dict):
            raise TypeError("snapshot must be a dict")
        if not _is_valid_snapshot(snapshot):
            raise ValueError("snapshot missing required keys")
        extracted = _extract_from_snapshot(snapshot)
        account_id = extracted["account_id"]
        result = _assemble_from_extracted(
            extracted,
            user_record=user_record,
            commerce_mode=commerce_mode,
        )
        cache_key = account_id or "__default__"
        _last_valid_state[cache_key] = result
        return result
    except Exception as exc:
        logger.warning("assembleLiveStateFromSnapshot failed for account=%s: %s", account_id, exc)
        cache_key = account_id or "__default__"
        if cache_key in _last_valid_state:
            return dict(_last_valid_state[cache_key])
        return _empty_contract()


def assembleLiveState(
    account_or_snapshot: str | dict[str, Any],
    user_record: dict[str, Any] | None = None,
    *,
    commerce_mode: bool | None = None,
) -> dict[str, Any]:
    """
    Assemble the strict UI contract.

    Accepts an account_id (builds snapshot first) or a pre-built snapshot dict.
  Never raises. Never returns null. Every field is always present.
    """
    if isinstance(account_or_snapshot, dict):
        return assembleLiveStateFromSnapshot(
            account_or_snapshot,
            user_record,
            commerce_mode=commerce_mode,
        )
    snapshot = buildSystemSnapshot(account_or_snapshot)
    return assembleLiveStateFromSnapshot(
        snapshot,
        user_record,
        commerce_mode=commerce_mode,
    )


def getLiveState(
    account_id: str,
    user_record: dict[str, Any] | None = None,
    *,
    commerce_mode: bool | None = None,
) -> dict[str, Any]:
    """End-to-end live state: build snapshot, then assemble UI contract."""
    snapshot = buildSystemSnapshot(account_id)
    return assembleLiveStateFromSnapshot(snapshot, user_record, commerce_mode=commerce_mode)


def reset_last_valid_state() -> None:
    """Clear cached last-valid states (for tests)."""
    _last_valid_state.clear()
