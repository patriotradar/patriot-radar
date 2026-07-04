"""
Live state assembly layer for TikTok SaaS frontend consumption.

Consolidates backend module outputs into one deterministic UI-ready object.
RBAC access block is appended read-only; does not alter core assembly logic.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from tiktok_access_control import (
    buildAccessContext,
    canAccessCommerceMode,
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
    return {
        "today_flow": {
            "step": "trend → product → content → queue",
            "next_action": "unknown",
            "status": "unknown",
        },
        "trends": [],
        "products": [],
        "inventory_gaps": [],
        "inventory_prevention": [],
        "content_queue": [],
        "approvals": [],
        "performance": {},
        "prediction": {},
        "alerts": [],
        "hidden_alerts": [],
        "raw_logs": [],
        "primary_action": {
            "label": "unknown",
            "action": "unknown",
            "context_id": "unknown",
        },
        "system_health": "unknown",
        "access": {
            "role": "creator",
            "admin_override": False,
            "visible_modules": [],
        },
    }


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

    return alerts, hidden


def _derive_flow_and_action(
    trends: list,
    products: list,
    content_queue: list,
    approvals: list,
    inventory_gaps: list,
    system_health: str,
) -> tuple[dict[str, str], dict[str, str]]:
    today_flow = {
        "step": "trend → product → content → queue",
        "next_action": "unknown",
        "status": "unknown",
    }
    primary_action = {
        "label": "unknown",
        "action": "unknown",
        "context_id": "unknown",
    }

    if approvals:
        today_flow["next_action"] = "Review pending content approvals"
        today_flow["status"] = "approval_pending"
        item = approvals[0] if isinstance(approvals[0], dict) else {}
        primary_action = {
            "label": "Review approval",
            "action": "review_approval",
            "context_id": _as_string(item.get("content_id") or item.get("id")),
        }
        return today_flow, primary_action

    if inventory_gaps:
        today_flow["next_action"] = "Address inventory gaps before posting"
        today_flow["status"] = "inventory_gap"
        gap = inventory_gaps[0] if isinstance(inventory_gaps[0], dict) else {}
        primary_action = {
            "label": "Fix inventory gap",
            "action": "fix_inventory",
            "context_id": _as_string(gap.get("product_name")),
        }
        return today_flow, primary_action

    if products and trends:
        today_flow["next_action"] = "Create content for top product-trend match"
        today_flow["status"] = "ready_to_create"
        product = products[0] if isinstance(products[0], dict) else {}
        primary_action = {
            "label": "Create content",
            "action": "create_content",
            "context_id": _as_string(product.get("name")),
        }
        return today_flow, primary_action

    if not products and trends:
        today_flow["next_action"] = "Match products to active trends"
        today_flow["status"] = "trend_detected"
        trend = trends[0] if isinstance(trends[0], dict) else {}
        primary_action = {
            "label": "Match products",
            "action": "match_products",
            "context_id": _as_string(trend.get("id") or trend.get("summary")),
        }
        return today_flow, primary_action

    if content_queue:
        today_flow["next_action"] = "Monitor queued content pipeline"
        today_flow["status"] = "in_queue"
        item = content_queue[0] if isinstance(content_queue[0], dict) else {}
        primary_action = {
            "label": "View queue",
            "action": "view_queue",
            "context_id": _as_string(item.get("id")),
        }
        return today_flow, primary_action

    if system_health in ("healthy", "degraded", "failing"):
        today_flow["status"] = system_health
        today_flow["next_action"] = "Run trend scan to refresh signals"
        primary_action = {
            "label": "Refresh trends",
            "action": "run_trend_scan",
            "context_id": "unknown",
        }

    return today_flow, primary_action


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

    today_flow, primary_action = _derive_flow_and_action(
        trends=trends,
        products=products,
        content_queue=content_queue,
        approvals=approvals,
        inventory_gaps=inventory_gaps,
        system_health=system_health,
    )

    alerts, hidden_alerts = _build_alerts(
        inventory_gaps=inventory_gaps,
        inventory_prevention=inventory_prevention,
        system_health=system_health,
        partial_failures=partial_failures,
    )

    flags = _load_feature_flags()
    commerce_mode = bool(flags.get("commerce_mode", False))
    access = buildAccessContext(account_id, user_record, flags, commerce_mode)
    access["commerce_access"] = canAccessCommerceMode(access, commerce_mode)

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
    state["system_health"] = system_health
    state["access"] = access

    return filterLiveStateForAccess(state, access)
