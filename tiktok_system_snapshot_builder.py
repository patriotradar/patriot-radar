"""
System snapshot builder — single deterministic capture per request cycle.

Collects all backend module state at once before live state assembly.
Never raises; failed modules are replaced with safe defaults (no retries).
"""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

_SNAPSHOT_MODULES: tuple[tuple[str, str, str], ...] = (
    ("trends_snapshot", "trend_detection_engine", "get_state"),
    ("product_snapshot_emerging", "emerging_products_engine", "get_state"),
    ("product_snapshot_trending", "trending_products_engine", "get_state"),
    ("inventory_snapshot_gaps", "inventory_gap_system", "get_state"),
    ("inventory_snapshot_prevention", "inventory_prevention_system", "get_state"),
    ("queue_snapshot", "content_queue_system", "get_state"),
    ("approval_snapshot", "approval_system", "get_state"),
    ("performance_snapshot", "performance_tracker", "get_state"),
    ("learning_snapshot", "learning_engine", "get_state"),
    ("system_health_snapshot", "system_health_monitor", "get_state"),
)


def _empty_trends_snapshot() -> dict[str, Any]:
    return {"trends": []}


def _empty_product_snapshot() -> dict[str, Any]:
    return {"emerging": [], "trending": [], "products": []}


def _empty_inventory_snapshot() -> dict[str, Any]:
    return {"inventory_gaps": [], "inventory_prevention": []}


def _empty_queue_snapshot() -> dict[str, Any]:
    return {"content_queue": []}


def _empty_approval_snapshot() -> dict[str, Any]:
    return {"approvals": []}


def _empty_performance_snapshot() -> dict[str, Any]:
    return {"performance": {}}


def _empty_learning_snapshot() -> dict[str, Any]:
    return {"learning": {}}


def _empty_system_health_snapshot() -> dict[str, Any]:
    return {"system_health": "unknown"}


def empty_system_snapshot(account_id: str = "") -> dict[str, Any]:
    """Return a fully populated empty snapshot — used when build fails entirely."""
    return {
        "account_id": str(account_id or ""),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "trends_snapshot": _empty_trends_snapshot(),
        "product_snapshot": _empty_product_snapshot(),
        "inventory_snapshot": _empty_inventory_snapshot(),
        "queue_snapshot": _empty_queue_snapshot(),
        "approval_snapshot": _empty_approval_snapshot(),
        "performance_snapshot": _empty_performance_snapshot(),
        "learning_snapshot": _empty_learning_snapshot(),
        "system_health_snapshot": _empty_system_health_snapshot(),
        "partial_failures": [],
    }


def _safe_invoke(module_name: str, fn_name: str, account_id: str) -> tuple[dict[str, Any], bool]:
    """Invoke a backend module once. Returns (payload, success). Does not retry on failure."""
    try:
        module = importlib.import_module(module_name)
        fn: Callable[[str], Any] | None = getattr(module, fn_name, None)
        if not callable(fn):
            logger.warning("buildSystemSnapshot: %s.%s is not callable", module_name, fn_name)
            return {}, False
        result = fn(account_id)
        if not isinstance(result, dict):
            return {}, False
        return result, True
    except Exception as exc:
        logger.warning("buildSystemSnapshot: %s.%s failed: %s", module_name, fn_name, exc)
        return {}, False


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _merge_product_snapshot(emerging_state: dict[str, Any], trending_state: dict[str, Any]) -> dict[str, Any]:
    emerging = _as_list(emerging_state.get("products"))
    trending = _as_list(trending_state.get("products"))
    return {
        "emerging": emerging,
        "trending": trending,
        "products": emerging + trending,
    }


def _merge_inventory_snapshot(gaps_state: dict[str, Any], prevention_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "inventory_gaps": _as_list(gaps_state.get("inventory_gaps")),
        "inventory_prevention": _as_list(prevention_state.get("inventory_prevention")),
    }


def buildSystemSnapshot(account_id: str) -> dict[str, Any]:
    """
    Build a deterministic system snapshot for one account in a single request cycle.

    All backend modules are queried once. Module failures are replaced with safe
    defaults — no retries, no partial live merges inside the assembler.
    """
    account = str(account_id or "")
    snapshot = empty_system_snapshot(account)
    partial_failures: list[str] = []

    try:
        collected: dict[str, dict[str, Any]] = {}
        for key, module_name, fn_name in _SNAPSHOT_MODULES:
            payload, ok = _safe_invoke(module_name, fn_name, account)
            collected[key] = payload
            if not ok:
                partial_failures.append(module_name)

        snapshot["trends_snapshot"] = collected.get("trends_snapshot") or _empty_trends_snapshot()
        if "trends" not in snapshot["trends_snapshot"]:
            snapshot["trends_snapshot"] = _empty_trends_snapshot()

        snapshot["product_snapshot"] = _merge_product_snapshot(
            collected.get("product_snapshot_emerging") or {},
            collected.get("product_snapshot_trending") or {},
        )

        snapshot["inventory_snapshot"] = _merge_inventory_snapshot(
            collected.get("inventory_snapshot_gaps") or {},
            collected.get("inventory_snapshot_prevention") or {},
        )

        queue_state = collected.get("queue_snapshot") or {}
        snapshot["queue_snapshot"] = {
            "content_queue": _as_list(queue_state.get("content_queue")),
        }

        approval_state = collected.get("approval_snapshot") or {}
        snapshot["approval_snapshot"] = {
            "approvals": _as_list(approval_state.get("approvals")),
        }

        performance_state = collected.get("performance_snapshot") or {}
        performance = performance_state.get("performance")
        snapshot["performance_snapshot"] = {
            "performance": performance if isinstance(performance, dict) else {},
        }

        learning_state = collected.get("learning_snapshot") or {}
        learning = learning_state.get("learning")
        snapshot["learning_snapshot"] = {
            "learning": learning if isinstance(learning, dict) else {},
        }

        health_state = collected.get("system_health_snapshot") or {}
        snapshot["system_health_snapshot"] = {
            "system_health": str(health_state.get("system_health") or "unknown"),
        }

        snapshot["partial_failures"] = partial_failures
        snapshot["snapshot_at"] = datetime.now(timezone.utc).isoformat()
        return snapshot

    except Exception as exc:
        logger.error("buildSystemSnapshot failed entirely for account=%s: %s", account, exc)
        empty = empty_system_snapshot(account)
        empty["partial_failures"] = ["buildSystemSnapshot"]
        return empty
