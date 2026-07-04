"""
Tests for action_orchestrator — deterministic action generation and fail-safety.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from action_orchestrator import (
    CONTINUE_STRATEGY_ACTION,
    generatePrimaryActions,
)


def _action_keys(action: dict) -> set[str]:
    return set(action.keys())


class TestActionContract(unittest.TestCase):
    def test_empty_state_returns_growth_action(self):
        result = generatePrimaryActions({})
        self.assertIn("primary_action", result)
        self.assertIn("secondary_actions", result)
        self.assertEqual(result["primary_action"]["action"], "run_trend_scan")
        self.assertIsInstance(result["secondary_actions"], list)

    def test_stable_state_returns_continue_strategy(self):
        live_state = {
            "commerce_mode": False,
            "trends": [{"id": "t1", "summary": "Fitness"}],
            "products": [{"name": "Protein", "signal_strength": 0.5}],
            "content_queue": [{"id": "q1", "status": "queued", "scheduled_time": "2026-07-04T12:00:00Z"}],
            "system_health": "healthy",
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "continue_current_strategy")

    def test_null_state_never_returns_null(self):
        result = generatePrimaryActions(None)
        self.assertIsNotNone(result["primary_action"])
        self.assertIsInstance(result["secondary_actions"], list)

    def test_primary_action_shape(self):
        result = generatePrimaryActions({})
        action = result["primary_action"]
        self.assertEqual(
            _action_keys(action),
            {"label", "action", "priority", "context_id", "reason"},
        )
        self.assertIn(action["priority"], ("high", "medium", "low"))

    def test_exception_fail_safe(self):
        with patch("action_orchestrator._normalize_live_state", side_effect=RuntimeError("boom")):
            result = generatePrimaryActions({"trends": []})
        self.assertEqual(result["primary_action"]["action"], CONTINUE_STRATEGY_ACTION["action"])
        self.assertEqual(result["secondary_actions"], [])


class TestPriorityOrder(unittest.TestCase):
    def test_inventory_prevention_beats_monetisation(self):
        live_state = {
            "commerce_mode": True,
            "inventory_prevention": [{
                "product_name": "Protein Powder",
                "demand_score": 0.95,
                "priority": "high",
                "available": False,
                "reason": "Trend spike expected",
            }],
            "products": [{"name": "Affiliate Kit", "signal_strength": 0.99}],
            "trends": [{"id": "t1", "signal_strength": 0.99}],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "prevent_inventory_stockout")
        self.assertEqual(result["primary_action"]["priority"], "high")

    def test_monetisation_when_commerce_mode_true(self):
        live_state = {
            "commerce_mode": True,
            "products": [{"name": "LED Ring Light", "signal_strength": 0.82}],
            "trends": [],
            "inventory_prevention": [],
            "content_queue": [{"id": "q1", "status": "queued", "scheduled_time": "2026-07-04T12:00:00Z"}],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "monetise_trending_product")

    def test_queue_optimisation_without_commerce(self):
        live_state = {
            "commerce_mode": False,
            "products": [{"name": "LED Ring Light", "signal_strength": 0.82}],
            "content_queue": [],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "generate_content_from_products")

    def test_repost_suggestion_priority(self):
        live_state = {
            "commerce_mode": False,
            "content_queue": [{"id": "q1", "status": "queued", "scheduled_time": "2026-07-04T12:00:00Z"}],
            "performance": {
                "underperformers": [{"content_id": "post-99", "engagement_rate": 0.01}],
            },
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "suggest_content_repost")

    def test_growth_recommendation_fallback(self):
        live_state = {
            "commerce_mode": False,
            "trends": [{"id": "summer-fitness", "summary": "Summer fitness"}],
            "products": [],
            "content_queue": [{"id": "q1", "status": "queued", "scheduled_time": "2026-07-04T12:00:00Z"}],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "match_products_to_trends")


class TestCommerceModeRule(unittest.TestCase):
    def test_no_monetisation_when_commerce_mode_false(self):
        live_state = {
            "commerce_mode": False,
            "products": [{"name": "Shop Item", "signal_strength": 0.95}],
            "trends": [{"id": "viral-trend", "signal_strength": 0.95}],
            "content_queue": [{"id": "q1", "status": "queued", "scheduled_time": "2026-07-04T12:00:00Z"}],
        }
        result = generatePrimaryActions(live_state)
        self.assertNotIn(
            result["primary_action"]["action"],
            ("monetise_trending_product", "monetise_trending_topic"),
        )

    def test_business_role_enables_commerce_mode(self):
        live_state = {
            "user_role": "business",
            "products": [{"name": "Shop Item", "signal_strength": 0.9}],
            "content_queue": [{"id": "q1", "status": "queued", "scheduled_time": "2026-07-04T12:00:00Z"}],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "monetise_trending_product")


class TestAdminModeRule(unittest.TestCase):
    def test_admin_debug_actions_in_secondary_only(self):
        live_state = {
            "admin_override": True,
            "commerce_mode": False,
            "trends": [{"id": "t1", "summary": "Fitness"}],
            "products": [{"name": "Protein", "signal_strength": 0.5}],
            "content_queue": [{"id": "q1", "status": "queued", "scheduled_time": "2026-07-04T12:00:00Z"}],
            "system_health": "healthy",
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "continue_current_strategy")
        secondary_actions = {a["action"] for a in result["secondary_actions"]}
        self.assertIn("inspect_system_health", secondary_actions)
        self.assertIn("view_debug_state", secondary_actions)

    def test_admin_does_not_change_primary_logic(self):
        live_state = {
            "admin_override": True,
            "commerce_mode": False,
            "inventory_prevention": [{
                "product_name": "Creatine",
                "demand_score": 0.9,
                "available": False,
                "reason": "Stockout risk",
            }],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "prevent_inventory_stockout")


class TestQueueOptimisation(unittest.TestCase):
    def test_blocked_queue_item(self):
        live_state = {
            "content_queue": [{"id": "blocked-1", "status": "blocked"}],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "resolve_queue_block")

    def test_pending_approval(self):
        live_state = {
            "content_queue": [{"id": "pending-1", "status": "pending"}],
        }
        result = generatePrimaryActions(live_state)
        self.assertEqual(result["primary_action"]["action"], "approve_queued_content")


if __name__ == "__main__":
    unittest.main()
