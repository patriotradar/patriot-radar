"""
Action orchestration layer — deterministic state-to-action conversion.

Converts assembled live_state into explicit primary and secondary user actions.
This layer does NOT fetch data or block execution — it only interprets state.

Never raises; never returns null actions; never blocks UI rendering.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HIGH_DEMAND_THRESHOLD = 0.7
MONETISATION_SIGNAL_THRESHOLD = 0.6
REPOST_PERFORMANCE_GAP = 0.35

CONTINUE_STRATEGY_ACTION: dict[str, str] = {
    "label": "Continue current strategy",
    "action": "continue_current_strategy",
    "priority": "low",
    "context_id": "default",
    "reason": "No higher-priority action identified; maintain current workflow.",
}

ADMIN_DEBUG_ACTIONS: tuple[dict[str, str], ...] = (
    {
        "label": "Inspect system health",
        "action": "inspect_system_health",
        "priority": "low",
        "context_id": "system",
        "reason": "Admin override enabled — review pipeline health and module status.",
    },
    {
        "label": "View debug state",
        "action": "view_debug_state",
        "priority": "low",
        "context_id": "debug",
        "reason": "Admin override enabled — inspect raw live_state payload.",
    },
)


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_string(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if value is not None:
        return bool(value)
    return default


def _as_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _make_action(
    *,
    label: str,
    action: str,
    priority: str,
    context_id: str,
    reason: str,
) -> dict[str, str]:
    return {
        "label": _as_string(label),
        "action": _as_string(action),
        "priority": priority if priority in ("high", "medium", "low") else "low",
        "context_id": _as_string(context_id),
        "reason": _as_string(reason),
    }


def _normalize_live_state(live_state: dict[str, Any] | None) -> dict[str, Any]:
    state = _as_dict(live_state)
    queue = _as_list(state.get("content_queue"))
    if not queue:
        queue = _as_list(state.get("queue"))
    if not queue:
        queue_status = _as_dict(state.get("queue_status"))
        queue = _as_list(queue_status.get("items") or queue_status.get("content_queue"))

    commerce_mode = _as_bool(state.get("commerce_mode"))
    if not commerce_mode:
        account_mode = _as_string(state.get("account_mode") or state.get("user_role"), "")
        commerce_mode = account_mode.lower() in ("business", "commerce", "shop")

    return {
        "trends": _as_list(state.get("trends")),
        "products": _as_list(state.get("products")),
        "inventory_prevention": _as_list(state.get("inventory_prevention")),
        "content_queue": queue,
        "performance": _as_dict(state.get("performance")),
        "commerce_mode": commerce_mode,
        "user_role": _as_string(state.get("user_role") or state.get("account_mode"), "creator"),
        "admin_override": _as_bool(state.get("admin_override")),
        "system_health": _as_string(state.get("system_health"), "unknown"),
    }


def _is_high_demand_prevention(item: dict[str, Any]) -> bool:
    if item.get("available") is False:
        return True
    priority = _as_string(item.get("priority")).lower()
    if priority == "high":
        return True
    return _as_number(item.get("demand_score")) >= HIGH_DEMAND_THRESHOLD


def _evaluate_inventory_prevention(inventory_prevention: list) -> dict[str, str] | None:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for item in inventory_prevention:
        if not isinstance(item, dict) or not _is_high_demand_prevention(item):
            continue
        score = _as_number(item.get("demand_score"))
        if item.get("available") is False:
            score = max(score, 1.0)
        candidates.append((score, item))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    top = candidates[0][1]
    product_name = _as_string(top.get("product_name") or top.get("product"))
    reason_text = _as_string(top.get("reason"), "High-demand product may stock out soon.")
    return _make_action(
        label="Restock high-demand product",
        action="prevent_inventory_stockout",
        priority="high",
        context_id=product_name,
        reason=reason_text,
    )


def _evaluate_monetisation(
    trends: list,
    products: list,
    commerce_mode: bool,
) -> dict[str, str] | None:
    if not commerce_mode:
        return None

    candidates: list[tuple[float, dict[str, Any], str]] = []

    for product in products:
        if not isinstance(product, dict):
            continue
        signal = _as_number(product.get("signal_strength") or product.get("score"))
        if signal < MONETISATION_SIGNAL_THRESHOLD:
            continue
        name = _as_string(product.get("name") or product.get("product_name"))
        candidates.append((signal, product, name))

    for trend in trends:
        if not isinstance(trend, dict):
            continue
        monetisable = trend.get("monetisable")
        if monetisable is False:
            continue
        signal = _as_number(
            trend.get("signal_strength")
            or trend.get("velocity")
            or trend.get("score")
        )
        if signal < MONETISATION_SIGNAL_THRESHOLD:
            continue
        context = _as_string(trend.get("id") or trend.get("summary") or trend.get("topic"))
        candidates.append((signal, trend, context))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    signal, item, context_id = candidates[0]
    if isinstance(item, dict) and (item.get("name") or item.get("product_name")):
        label = "Monetise trending product"
        action = "monetise_trending_product"
        reason = (
            f"Trending product '{context_id}' has strong monetisation signal "
            f"({signal:.2f}). Attach affiliate or shop link."
        )
    else:
        label = "Capitalise on trending topic"
        action = "monetise_trending_topic"
        reason = (
            f"Active trend '{context_id}' presents a commerce opportunity "
            f"(signal {signal:.2f})."
        )

    return _make_action(
        label=label,
        action=action,
        priority="high" if signal >= 0.85 else "medium",
        context_id=context_id,
        reason=reason,
    )


def _evaluate_queue_optimisation(
    content_queue: list,
    products: list,
    trends: list,
) -> dict[str, str] | None:
    blocked = [
        item for item in content_queue
        if isinstance(item, dict) and _as_string(item.get("status")).lower() == "blocked"
    ]
    if blocked:
        item = blocked[0]
        return _make_action(
            label="Unblock queued content",
            action="resolve_queue_block",
            priority="high",
            context_id=_as_string(item.get("id") or item.get("content_id")),
            reason="Content in queue is blocked and cannot publish until resolved.",
        )

    pending = [
        item for item in content_queue
        if isinstance(item, dict)
        and _as_string(item.get("status")).lower() in ("pending", "awaiting_approval")
    ]
    if pending:
        item = pending[0]
        return _make_action(
            label="Approve queued content",
            action="approve_queued_content",
            priority="medium",
            context_id=_as_string(item.get("id") or item.get("content_id")),
            reason="Pending content is ready for approval to keep the queue moving.",
        )

    if not content_queue and products:
        product = products[0] if isinstance(products[0], dict) else {}
        name = _as_string(product.get("name") or product.get("product_name"))
        return _make_action(
            label="Generate content from products",
            action="generate_content_from_products",
            priority="medium",
            context_id=name,
            reason="Products detected but content queue is empty — create posts to capture demand.",
        )

    if content_queue:
        gaps = sum(
            1 for item in content_queue
            if isinstance(item, dict) and not _as_string(item.get("scheduled_time"))
        )
        if gaps >= 2:
            item = next(
                (i for i in content_queue if isinstance(i, dict) and not _as_string(i.get("scheduled_time"))),
                content_queue[0],
            )
            return _make_action(
                label="Optimise content schedule",
                action="optimise_content_schedule",
                priority="medium",
                context_id=_as_string(item.get("id") or item.get("content_id")),
                reason=f"{gaps} queued posts lack scheduling — optimise timing for reach.",
            )

    if not content_queue and trends:
        trend = trends[0] if isinstance(trends[0], dict) else {}
        return _make_action(
            label="Create content for active trend",
            action="create_trend_content",
            priority="medium",
            context_id=_as_string(trend.get("id") or trend.get("summary") or trend.get("topic")),
            reason="Active trend detected with no queued content — create posts to ride momentum.",
        )

    return None


def _evaluate_repost_suggestions(performance: dict) -> dict[str, str] | None:
    top_performers = _as_list(performance.get("top_performers") or performance.get("top_posts"))
    underperformers = _as_list(
        performance.get("underperformers") or performance.get("repost_candidates")
    )

    if underperformers:
        item = underperformers[0] if isinstance(underperformers[0], dict) else {}
        content_id = _as_string(item.get("content_id") or item.get("id") or item.get("video_id"))
        return _make_action(
            label="Repost underperforming content",
            action="suggest_content_repost",
            priority="medium",
            context_id=content_id,
            reason="Performance data suggests reposting with an updated hook or format.",
        )

    if top_performers:
        top = top_performers[0] if isinstance(top_performers[0], dict) else {}
        top_score = _as_number(top.get("engagement_rate") or top.get("score"))
        avg_score = _as_number(performance.get("average_engagement_rate") or performance.get("avg_score"))
        if top_score > 0 and avg_score > 0 and (top_score - avg_score) / top_score >= REPOST_PERFORMANCE_GAP:
            content_id = _as_string(top.get("content_id") or top.get("id") or top.get("video_id"))
            return _make_action(
                label="Repost top performer",
                action="repost_top_performer",
                priority="medium",
                context_id=content_id,
                reason="Top-performing content significantly outperforms average — repost to extend reach.",
            )

    repost_suggestion = _as_string(performance.get("repost_suggestion"))
    if repost_suggestion and repost_suggestion != "unknown":
        return _make_action(
            label="Review repost suggestion",
            action="review_repost_suggestion",
            priority="low",
            context_id=repost_suggestion,
            reason="Performance tracker flagged content worth reposting.",
        )

    return None


def _evaluate_growth_recommendations(
    trends: list,
    products: list,
    system_health: str,
) -> dict[str, str] | None:
    if not trends and not products:
        return _make_action(
            label="Run trend scan",
            action="run_trend_scan",
            priority="medium",
            context_id="trends",
            reason="No active trends or products — refresh signals to identify growth opportunities.",
        )

    if trends and not products:
        trend = trends[0] if isinstance(trends[0], dict) else {}
        return _make_action(
            label="Match products to trends",
            action="match_products_to_trends",
            priority="medium",
            context_id=_as_string(trend.get("id") or trend.get("summary") or trend.get("topic")),
            reason="Trends detected without matched products — connect catalog to capture demand.",
        )

    if system_health in ("degraded", "failing"):
        return _make_action(
            label="Review system health",
            action="review_system_health",
            priority="medium",
            context_id="system_health",
            reason=f"System health is {system_health} — address pipeline issues before scaling content.",
        )

    return None


def _build_content_growth_fallback(
    trends: list,
    products: list,
    content_queue: list,
) -> dict[str, str] | None:
    """Non-monetisation growth actions when commerce_mode is disabled."""
    if content_queue:
        return None

    queue_action = _evaluate_queue_optimisation(content_queue, products, trends)
    if queue_action:
        return queue_action

    if trends:
        trend = trends[0] if isinstance(trends[0], dict) else {}
        return _make_action(
            label="Create trend-based content",
            action="create_trend_content",
            priority="medium",
            context_id=_as_string(trend.get("id") or trend.get("summary") or trend.get("topic")),
            reason="Commerce mode off — focus on organic content growth around active trends.",
        )

    if products:
        product = products[0] if isinstance(products[0], dict) else {}
        return _make_action(
            label="Build audience with product content",
            action="create_product_content",
            priority="medium",
            context_id=_as_string(product.get("name") or product.get("product_name")),
            reason="Commerce mode off — create engaging content to grow audience around detected products.",
        )

    return None


def _collect_secondary_actions(
    *,
    inventory_prevention: list,
    trends: list,
    products: list,
    content_queue: list,
    performance: dict,
    commerce_mode: bool,
    primary_action: dict[str, str],
) -> list[dict[str, str]]:
    secondary: list[dict[str, str]] = []
    seen_actions: set[str] = {primary_action["action"]}

    def _add(action: dict[str, str] | None) -> None:
        if not action or action["action"] in seen_actions:
            return
        seen_actions.add(action["action"])
        secondary.append(action)

    for item in inventory_prevention:
        if not isinstance(item, dict):
            continue
        if not _is_high_demand_prevention(item):
            continue
        _add(_make_action(
            label="Review inventory alert",
            action="review_inventory_alert",
            priority="medium",
            context_id=_as_string(item.get("product_name") or item.get("product")),
            reason=_as_string(item.get("reason"), "Inventory prevention signal detected."),
        ))
        break

    if commerce_mode:
        _add(_evaluate_monetisation(trends, products, commerce_mode=True))

    _add(_evaluate_queue_optimisation(content_queue, products, trends))
    _add(_evaluate_repost_suggestions(performance))
    _add(_evaluate_growth_recommendations(trends, products, "healthy"))
    if products:
        product = products[0] if isinstance(products[0], dict) else {}
        _add(_make_action(
            label="Expand content around top product",
            action="expand_product_content",
            priority="low",
            context_id=_as_string(product.get("name") or product.get("product_name")),
            reason="Continue growth by creating more content variants around detected products.",
        ))

    return secondary[:5]


def generatePrimaryActions(live_state: dict[str, Any] | None) -> dict[str, Any]:
    """
    Convert system state into explicit user actions.

    Input (from live_state):
      - trends, products, inventory_prevention, content_queue / queue_status
      - performance, commerce_mode, user_role, admin_override

    Output contract:
      - primary_action: {label, action, priority, context_id, reason}
      - secondary_actions: list of same shape

    Only ONE primary action is returned — the highest-value next step.
    Never raises; never returns null actions.
    """
    try:
        state = _normalize_live_state(live_state)

        primary: dict[str, str] | None = None

        primary = _evaluate_inventory_prevention(state["inventory_prevention"])

        if primary is None and state["commerce_mode"]:
            primary = _evaluate_monetisation(
                state["trends"],
                state["products"],
                commerce_mode=True,
            )

        if primary is None:
            primary = _evaluate_queue_optimisation(
                state["content_queue"],
                state["products"],
                state["trends"],
            )

        if primary is None:
            primary = _evaluate_repost_suggestions(state["performance"])

        if primary is None:
            primary = _evaluate_growth_recommendations(
                state["trends"],
                state["products"],
                state["system_health"],
            )

        if primary is None and not state["commerce_mode"]:
            primary = _build_content_growth_fallback(
                state["trends"],
                state["products"],
                state["content_queue"],
            )

        if primary is None:
            primary = dict(CONTINUE_STRATEGY_ACTION)

        secondary = _collect_secondary_actions(
            inventory_prevention=state["inventory_prevention"],
            trends=state["trends"],
            products=state["products"],
            content_queue=state["content_queue"],
            performance=state["performance"],
            commerce_mode=state["commerce_mode"],
            primary_action=primary,
        )

        if state["admin_override"]:
            for admin_action in ADMIN_DEBUG_ACTIONS:
                if admin_action["action"] not in {a["action"] for a in secondary}:
                    secondary.append(dict(admin_action))

        return {
            "primary_action": primary,
            "secondary_actions": secondary,
        }

    except Exception as exc:
        logger.warning("generatePrimaryActions failed safely: %s", exc)
        return {
            "primary_action": dict(CONTINUE_STRATEGY_ACTION),
            "secondary_actions": [],
        }
