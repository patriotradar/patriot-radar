"""
Live state assembly layer for TikTok SaaS frontend consumption.

Consolidates backend module outputs into one deterministic UI-ready object.
RBAC access block is appended read-only; does not alter core assembly logic.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from action_orchestrator import generatePrimaryActions
from tiktok_access_control import (
    buildAccessContext,
    empty_live_state_contract,
    filterLiveStateForAccess,
    _load_feature_flags,
)

logger = logging.getLogger(__name__)

_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    ("trend_detection_engine", "get_state"),
    ("emerging_products_engine", "get_state"),
    ("trending_products_engine", "get_state"),
    ("inventory_prevention_system", "get_state"),
    ("inventory_gap_system", "get_state"),
    ("content_queue_system", "get_state"),
    ("approval_system", "get_state"),
    ("performance_tracker", "get_state"),
    ("learning_engine", "get_state"),
    ("system_health_monitor", "get_state"),
)


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


def _safe_invoke(module_name: str, fn_name: str, account_id: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        fn: Callable[[str], Any] | None = getattr(module, fn_name, None)
        if not callable(fn):
            return {}
        result = fn(account_id)
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        logger.warning("assembleLiveState: %s.%s failed: %s", module_name, fn_name, exc)
        return {}


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
) -> dict[str, str]:
    """Map orchestrated primary action to today_flow status for the UI."""
    today_flow = {
        "step": "trend → product → content → queue",
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

    if action in ("generate_content_from_products", "create_product_content", "create_trend_content", "create_content"):
        today_flow["status"] = "ready_for_content"
        return today_flow

    if action in ("match_products_to_trends", "monetise_trending_topic", "match_products"):
        today_flow["status"] = "trend_detected"
        return today_flow

    if content_queue and action in (
        "optimise_content_schedule",
        "resolve_queue_block",
        "view_queue",
    ):
        today_flow["status"] = "in_queue"
        return today_flow

    if system_health in ("healthy", "degraded", "failing"):
        today_flow["status"] = system_health
        return today_flow

    if trends or products:
        today_flow["status"] = "active"
        return today_flow

    return today_flow


def assembleLiveState(
    account_id: str,
    user_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Assemble the strict UI contract from all optional backend modules.

    Never raises. Never returns null. Every field is always present.
    RBAC access block is computed server-side from secure role sources.
    """
    state = _empty_contract()
    partial_failures: list[str] = []

    collected: dict[str, Any] = {}
    for module_name, fn_name in _SOURCE_MODULES:
        payload = _safe_invoke(module_name, fn_name, account_id)
        if not payload:
            partial_failures.append(module_name)
        collected[module_name] = payload

    trends = _as_list(collected.get("trend_detection_engine", {}).get("trends"))
    emerging = _as_list(collected.get("emerging_products_engine", {}).get("products"))
    trending = _as_list(collected.get("trending_products_engine", {}).get("products"))
    products = _merge_products(emerging, trending)

    inventory_gaps = _as_list(collected.get("inventory_gap_system", {}).get("inventory_gaps"))
    inventory_prevention = _as_list(
        collected.get("inventory_prevention_system", {}).get("inventory_prevention")
    )
    content_queue = _as_list(collected.get("content_queue_system", {}).get("content_queue"))
    approvals = _as_list(collected.get("approval_system", {}).get("approvals"))
    performance = _as_dict(collected.get("performance_tracker", {}).get("performance"))
    prediction = _as_dict(collected.get("learning_engine", {}).get("prediction"))
    system_health = _as_string(
        collected.get("system_health_monitor", {}).get("system_health"),
        "unknown",
    )
    raw_logs = _as_list(collected.get("system_health_monitor", {}).get("raw_logs"))

    flags = _load_feature_flags()
    commerce_mode = bool(flags.get("commerce_mode", False))
    access = buildAccessContext(account_id, user_record, flags, commerce_mode)
    user_role = _as_string(access.get("role"), "creator")
    admin_override = bool(access.get("admin_override"))

    orchestration_input = {
        "trends": trends,
        "products": products,
        "inventory_prevention": inventory_prevention,
        "content_queue": content_queue,
        "performance": performance,
        "commerce_mode": commerce_mode,
        "user_role": user_role,
        "admin_override": admin_override,
        "system_health": system_health,
    }
    actions = generatePrimaryActions(orchestration_input)
    primary_action = actions["primary_action"]
    secondary_actions = actions["secondary_actions"]

    today_flow = _derive_today_flow(
        primary_action,
        inventory_gaps=inventory_gaps,
        approvals=approvals,
        content_queue=content_queue,
        products=products,
        trends=trends,
        system_health=system_health,
    )

    alerts, hidden_alerts = _build_alerts(
        inventory_gaps=inventory_gaps,
        inventory_prevention=inventory_prevention,
        system_health=system_health,
        partial_failures=partial_failures,
    )

    state["today_flow"] = today_flow
    state["trends"] = trends
    state["products"] = products
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

    return filterLiveStateForAccess(state, access)
