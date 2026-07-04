"""
Tests for snapshot-driven live state architecture.

Validates contract guarantees, fail-safety, snapshot → assembler flow, and RBAC.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import tiktok_access_control as rbac
from tiktok_live_state_assembler import (
    assembleLiveState,
    getLiveState,
    reset_last_valid_state,
    _empty_contract,
)
from tiktok_system_snapshot_builder import (
    buildSystemSnapshot,
    empty_system_snapshot,
)


class TestSnapshotContract(unittest.TestCase):
    def test_empty_snapshot_has_all_keys(self):
        snapshot = empty_system_snapshot("acct_1")
        expected = {
            "account_id",
            "snapshot_at",
            "trends_snapshot",
            "product_snapshot",
            "inventory_snapshot",
            "queue_snapshot",
            "approval_snapshot",
            "performance_snapshot",
            "learning_snapshot",
            "system_health_snapshot",
            "partial_failures",
        }
        self.assertEqual(set(snapshot.keys()), expected)

    def test_build_never_raises_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            snapshot = buildSystemSnapshot("test_account")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["account_id"], "test_account")
        self.assertIsInstance(snapshot["trends_snapshot"], dict)
        self.assertIsInstance(snapshot["product_snapshot"], dict)
        self.assertIsInstance(snapshot["inventory_snapshot"], dict)

    def test_build_returns_all_eight_snapshots(self):
        snapshot = buildSystemSnapshot("acct_1")
        for key in (
            "trends_snapshot",
            "product_snapshot",
            "inventory_snapshot",
            "queue_snapshot",
            "approval_snapshot",
            "performance_snapshot",
            "learning_snapshot",
            "system_health_snapshot",
        ):
            self.assertIn(key, snapshot)
            self.assertIsInstance(snapshot[key], dict)


class TestLiveStateContract(unittest.TestCase):
    def setUp(self):
        reset_last_valid_state()

    def test_empty_contract_has_all_fields(self):
        state = _empty_contract()
        self.assertIn("today_flow", state)
        self.assertIn("trends", state)
        self.assertIn("products", state)
        self.assertIn("inventory_gaps", state)
        self.assertIn("inventory_prevention", state)
        self.assertIn("content_queue", state)
        self.assertIn("approvals", state)
        self.assertIn("performance", state)
        self.assertIn("alerts", state)
        self.assertIn("primary_action", state)
        self.assertIn("secondary_actions", state)
        self.assertIn("commerce_mode", state)
        self.assertIn("user_role", state)
        self.assertIn("admin_override", state)
        self.assertIn("system_health", state)
        self.assertIn("access", state)

    def test_today_flow_shape(self):
        state = _empty_contract()
        self.assertEqual(state["today_flow"]["step"], "trend → product → content → queue")
        self.assertIsInstance(state["today_flow"]["next_action"], str)
        self.assertIsInstance(state["today_flow"]["status"], str)

    def test_primary_action_shape(self):
        state = _empty_contract()
        for key in ("label", "action", "priority", "context_id", "reason"):
            self.assertIn(key, state["primary_action"])
            self.assertIsInstance(state["primary_action"][key], str)

    def test_assemble_from_empty_snapshot(self):
        snapshot = empty_system_snapshot("test_account")
        state = assembleLiveState(snapshot)
        self.assertIsNotNone(state)
        self.assertIsInstance(state["trends"], list)
        self.assertIsInstance(state["products"], list)
        self.assertIsInstance(state["performance"], dict)
        self.assertIsInstance(state["system_health"], str)

    def test_assemble_never_raises_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            state = assembleLiveState("test_account")
        self.assertIsNotNone(state)
        self.assertIsInstance(state["trends"], list)
        self.assertIsInstance(state["products"], list)
        self.assertIsInstance(state["performance"], dict)
        self.assertIsInstance(state["system_health"], str)
        self.assertIsInstance(state["secondary_actions"], list)

    def test_assemble_empty_account_id(self):
        state = assembleLiveState("")
        self.assertIsNotNone(state)
        self.assertIsInstance(state["today_flow"]["next_action"], str)
        self.assertIsInstance(state["today_flow"]["status"], str)

    def test_assemble_exact_top_level_keys(self):
        snapshot = empty_system_snapshot("acct_1")
        state = assembleLiveState(snapshot)
        self.assertEqual(set(state.keys()), rbac.LIVE_STATE_SCHEMA_KEYS | {"features"})

    def test_assemble_uses_action_orchestrator(self):
        state = assembleLiveState("acct_1", {"user_metadata": {"role": "admin"}})
        self.assertIn("priority", state["primary_action"])
        self.assertIn("reason", state["primary_action"])
        secondary_actions = {a["action"] for a in state["secondary_actions"]}
        self.assertIn("inspect_system_health", secondary_actions)

    def test_assemble_never_raises_on_invalid_snapshot(self):
        state = assembleLiveState(None)  # type: ignore[arg-type]
        self.assertIsNotNone(state)
        self.assertIsInstance(state["trends"], list)

    def test_assembler_returns_last_valid_state_on_failure(self):
        good_snapshot = empty_system_snapshot("acct_cache")
        good_snapshot["trends_snapshot"] = {
            "trends": [{"id": "t1", "summary": "cached trend", "type": "hook"}],
        }
        first = assembleLiveState(good_snapshot)
        self.assertEqual(len(first["trends"]), 1)

        bad_snapshot = {"account_id": "acct_cache", "invalid": True}
        second = assembleLiveState(bad_snapshot)
        self.assertEqual(len(second["trends"]), 1)

    def test_get_live_state_end_to_end(self):
        with patch.dict(os.environ, {}, clear=True):
            state = getLiveState("acct_e2e")
        self.assertIsNotNone(state)
        self.assertIsInstance(state["today_flow"]["next_action"], str)


class TestSnapshotDrivenFlow(unittest.TestCase):
    def setUp(self):
        reset_last_valid_state()

    def test_snapshot_then_assemble_deterministic(self):
        snapshot = {
            "account_id": "acct_det",
            "snapshot_at": "2026-07-04T12:00:00+00:00",
            "trends_snapshot": {
                "trends": [{"id": "t1", "summary": "Rising hook", "type": "hook"}],
            },
            "product_snapshot": {
                "emerging": [{"name": "Flag Pin", "signal_strength": 80, "source": "emerging"}],
                "trending": [],
                "products": [],
            },
            "inventory_snapshot": {
                "inventory_gaps": [],
                "inventory_prevention": [],
            },
            "queue_snapshot": {"content_queue": []},
            "approval_snapshot": {"approvals": []},
            "performance_snapshot": {"performance": {"snapshot_count": 0}},
            "learning_snapshot": {"learning": {}},
            "system_health_snapshot": {"system_health": "healthy"},
            "partial_failures": [],
        }
        state = assembleLiveState(snapshot, {"user_metadata": {"role": "admin"}}, commerce_mode=True)
        self.assertIn(
            state["today_flow"]["status"],
            ("ready_for_content", "trend_detected", "active"),
        )
        self.assertIn(
            state["primary_action"]["action"],
            ("create_product_content", "generate_content_from_products", "generate_content", "monetise_trending_product"),
        )
        self.assertEqual(state["products"][0]["name"], "Flag Pin")
        self.assertEqual(state["system_health"], "healthy")

    def test_inventory_gap_blocks_flow(self):
        snapshot = empty_system_snapshot("acct_blocked")
        snapshot["inventory_snapshot"] = {
            "inventory_gaps": [{"product_name": "Missing SKU", "status": "paused"}],
            "inventory_prevention": [],
        }
        state = assembleLiveState(snapshot, commerce_mode=True)
        self.assertEqual(state["today_flow"]["status"], "blocked")
        self.assertIn(
            state["primary_action"]["action"],
            ("resolve_inventory_gap", "prevent_inventory_stockout", "fix_inventory"),
        )


if __name__ == "__main__":
    unittest.main()
