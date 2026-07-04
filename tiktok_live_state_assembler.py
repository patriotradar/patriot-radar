"""
Live state assembly layer for TikTok SaaS frontend consumption.

Accepts ONLY a pre-built system snapshot — never calls backend modules directly.
Normalises snapshot data into the strict UI contract with safe defaults.
Never raises; never returns null; never omits contract fields.
"""

from __future__ import annotations

import logging
from typing import Any

from tiktok_system_snapshot_builder import buildSystemSnapshot, empty_system_snapshot

logger = logging.getLogger(__name__)

_last_valid_state: dict[str, dict[str, Any]] = {}


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
        "alerts": [],
        "primary_action": {
            "label": "unknown",
            "action": "unknown",
            "context_id": "unknown",
        },
        "system_health": "unknown",
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
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

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
        alerts.append({
            "level": "error",
            "code": "system_health",
            "message": "System health is failing",
        })
    elif system_health == "degraded":
        alerts.append({
            "level": "warning",
            "code": "system_health",
            "message": "System health is degraded",
        })

    for module_name in partial_failures:
        alerts.append({
            "level": "info",
            "code": "module_fallback",
            "message": f"Using defaults for {module_name}",
        })

    return alerts


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

    if inventory_gaps:
        today_flow["next_action"] = "Resolve inventory gaps before attaching products"
        today_flow["status"] = "blocked"
        gap = inventory_gaps[0] if isinstance(inventory_gaps[0], dict) else {}
        primary_action = {
            "label": "Fix inventory gap",
            "action": "resolve_inventory_gap",
            "context_id": _as_string(gap.get("product_name")),
        }
        return today_flow, primary_action

    if approvals:
        today_flow["next_action"] = "Review pending content approvals"
        today_flow["status"] = "awaiting_approval"
        item = approvals[0] if isinstance(approvals[0], dict) else {}
        primary_action = {
            "label": "Approve content",
            "action": "approve_content",
            "context_id": _as_string(item.get("content_id")),
        }
        return today_flow, primary_action

    if not content_queue and products:
        today_flow["next_action"] = "Generate content from detected products"
        today_flow["status"] = "ready_for_content"
        product = products[0] if isinstance(products[0], dict) else {}
        primary_action = {
            "label": "Generate content",
            "action": "generate_content",
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


def _is_valid_snapshot(snapshot: dict[str, Any]) -> bool:
    return _REQUIRED_SNAPSHOT_KEYS.issubset(snapshot.keys())


def _extract_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Pull normalised slices from a system snapshot dict."""
    trends_snapshot = _as_dict(snapshot.get("trends_snapshot"))
    product_snapshot = _as_dict(snapshot.get("product_snapshot"))
    inventory_snapshot = _as_dict(snapshot.get("inventory_snapshot"))
    queue_snapshot = _as_dict(snapshot.get("queue_snapshot"))
    approval_snapshot = _as_dict(snapshot.get("approval_snapshot"))
    performance_snapshot = _as_dict(snapshot.get("performance_snapshot"))
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
        "system_health": _as_string(system_health_snapshot.get("system_health"), "unknown"),
        "partial_failures": _as_list(snapshot.get("partial_failures")),
        "account_id": _as_string(snapshot.get("account_id"), ""),
    }


def assembleLiveState(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Assemble the strict UI contract from a pre-built system snapshot.

    Does NOT call backend modules. Only formats and normalises snapshot data.
    On failure, returns the last valid state for the account (or empty contract).
    """
    account_id = ""
    try:
        if not isinstance(snapshot, dict):
            raise TypeError("snapshot must be a dict")

        account_id = str(snapshot.get("account_id") or "")

        if not _is_valid_snapshot(snapshot):
            raise ValueError("snapshot missing required keys")
        extracted = _extract_from_snapshot(snapshot)

        state = _empty_contract()
        products = _merge_products(extracted["emerging"], extracted["trending"])

        today_flow, primary_action = _derive_flow_and_action(
            trends=extracted["trends"],
            products=products,
            content_queue=extracted["content_queue"],
            approvals=extracted["approvals"],
            inventory_gaps=extracted["inventory_gaps"],
            system_health=extracted["system_health"],
        )

        alerts = _build_alerts(
            inventory_gaps=extracted["inventory_gaps"],
            inventory_prevention=extracted["inventory_prevention"],
            system_health=extracted["system_health"],
            partial_failures=extracted["partial_failures"],
        )

        state["today_flow"] = today_flow
        state["trends"] = extracted["trends"]
        state["products"] = products
        state["inventory_gaps"] = extracted["inventory_gaps"]
        state["inventory_prevention"] = extracted["inventory_prevention"]
        state["content_queue"] = extracted["content_queue"]
        state["approvals"] = extracted["approvals"]
        state["performance"] = extracted["performance"]
        state["alerts"] = alerts
        state["primary_action"] = primary_action
        state["system_health"] = extracted["system_health"]

        cache_key = account_id or "__default__"
        _last_valid_state[cache_key] = state
        return state

    except Exception as exc:
        logger.warning("assembleLiveState failed for account=%s: %s", account_id, exc)
        cache_key = account_id or "__default__"
        if cache_key in _last_valid_state:
            return dict(_last_valid_state[cache_key])
        return _empty_contract()


def getLiveState(account_id: str) -> dict[str, Any]:
    """
    End-to-end live state: build snapshot, then assemble UI contract.

    Step 1: buildSystemSnapshot(account_id)
    Step 2: assembleLiveState(snapshot)
    Step 3: return UI contract
    """
    snapshot = buildSystemSnapshot(account_id)
    return assembleLiveState(snapshot)


def reset_last_valid_state() -> None:
    """Clear cached last-valid states (for tests)."""
    _last_valid_state.clear()
