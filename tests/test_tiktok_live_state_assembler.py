"""
Tests for tiktok_live_state_assembler — contract guarantees and fail-safety.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tiktok_live_state_assembler import assembleLiveState, _empty_contract


class TestLiveStateContract(unittest.TestCase):
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
        state = assembleLiveState("acct_1")
        expected_keys = {
            "today_flow",
            "trends",
            "products",
            "inventory_gaps",
            "inventory_prevention",
            "content_queue",
            "approvals",
            "performance",
            "alerts",
            "primary_action",
            "secondary_actions",
            "commerce_mode",
            "user_role",
            "admin_override",
            "system_health",
        }
        self.assertEqual(set(state.keys()), expected_keys)

    def test_assemble_uses_action_orchestrator(self):
        state = assembleLiveState("acct_1", admin_override=True)
        self.assertIn("priority", state["primary_action"])
        self.assertIn("reason", state["primary_action"])
        secondary_actions = {a["action"] for a in state["secondary_actions"]}
        self.assertIn("inspect_system_health", secondary_actions)


if __name__ == "__main__":
    unittest.main()
