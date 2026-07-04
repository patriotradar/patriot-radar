"""Tests for TikTok RBAC access control layer."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tiktok_access_control as rbac


class TestGetUserRole(unittest.TestCase):
    def test_defaults_to_creator_when_unknown(self):
        self.assertEqual(rbac.getUserRole("acct-1", None), "creator")
        self.assertEqual(rbac.getUserRole("acct-1", {}), "creator")

    def test_metadata_role_viewer(self):
        user = {"user_metadata": {"role": "viewer"}}
        self.assertEqual(rbac.getUserRole("acct-1", user), "viewer")

    def test_metadata_role_test(self):
        user = {"user_metadata": {"user_role": "test"}}
        self.assertEqual(rbac.getUserRole("acct-1", user), "test")

    def test_invalid_role_defaults_creator(self):
        user = {"user_metadata": {"role": "superuser"}}
        self.assertEqual(rbac.getUserRole("acct-1", user), "creator")

    @mock.patch.dict(os.environ, {"TIKTOK_ADMIN_EMAILS": "admin@example.com"})
    def test_admin_email_allowlist(self):
        user = {"email": "admin@example.com"}
        self.assertEqual(rbac.getUserRole("acct-1", user), "admin")

    def test_metadata_admin_role(self):
        user = {"user_metadata": {"role": "admin"}}
        self.assertEqual(rbac.getUserRole("acct-1", user), "admin")


class TestAdminOverride(unittest.TestCase):
    def test_admin_override_only_for_admin(self):
        self.assertTrue(rbac.getAdminOverride("admin"))
        self.assertFalse(rbac.getAdminOverride("creator"))
        self.assertFalse(rbac.getAdminOverride("viewer"))
        self.assertFalse(rbac.getAdminOverride("test"))


class TestVisibleModules(unittest.TestCase):
    def test_admin_sees_all_modules(self):
        modules = rbac.resolveVisibleModules("admin")
        self.assertEqual(set(modules), set(rbac.ALL_MODULES))

    def test_creator_follows_feature_flags(self):
        flags = {
            "trends": True,
            "products": True,
            "inventory_system": True,
            "prediction_engine": True,
            "analytics": True,
            "system_health": False,
            "raw_logs": False,
            "hidden_alerts": False,
            "commerce_mode": False,
        }
        modules = rbac.resolveVisibleModules("creator", flags, commerce_mode=False)
        self.assertIn("trends", modules)
        self.assertNotIn("products", modules)
        self.assertNotIn("inventory_system", modules)
        self.assertNotIn("system_health", modules)

    def test_commerce_mode_unlocks_products_for_creator(self):
        flags = {
            "trends": True,
            "products": True,
            "inventory_system": True,
            "prediction_engine": True,
            "analytics": True,
            "system_health": False,
            "raw_logs": False,
            "hidden_alerts": False,
            "commerce_mode": True,
        }
        modules = rbac.resolveVisibleModules("creator", flags, commerce_mode=True)
        self.assertIn("products", modules)
        self.assertIn("inventory_system", modules)


class TestAccessContext(unittest.TestCase):
    def test_build_access_context_shape(self):
        ctx = rbac.buildAccessContext("acct-1", {"user_metadata": {"role": "viewer"}})
        self.assertEqual(ctx["role"], "viewer")
        self.assertFalse(ctx["admin_override"])
        self.assertIsInstance(ctx["visible_modules"], list)


class TestFilterLiveState(unittest.TestCase):
    def test_non_admin_strips_sensitive_fields(self):
        state = {
            "system_health": "failing",
            "raw_logs": [{"line": "secret"}],
            "hidden_alerts": [{"level": "hidden", "message": "x"}],
            "alerts": [{"level": "hidden", "message": "x"}, {"level": "warning", "message": "y"}],
            "products": [{"name": "p1"}],
            "inventory_gaps": [{"product_name": "g1"}],
            "performance": {"total_views": 100},
        }
        access = {"admin_override": False, "visible_modules": ["trends"]}
        filtered = rbac.filterLiveStateForAccess(state, access)
        self.assertEqual(filtered["system_health"], "restricted")
        self.assertEqual(filtered["raw_logs"], [])
        self.assertEqual(filtered["hidden_alerts"], [])
        self.assertEqual(len(filtered["alerts"]), 1)
        self.assertEqual(filtered["products"], [])
        self.assertEqual(filtered["performance"], {})

    def test_admin_keeps_all_fields(self):
        state = {"system_health": "failing", "raw_logs": [{"line": "secret"}]}
        access = {"admin_override": True, "visible_modules": list(rbac.ALL_MODULES)}
        filtered = rbac.filterLiveStateForAccess(state, access)
        self.assertEqual(filtered["system_health"], "failing")
        self.assertEqual(len(filtered["raw_logs"]), 1)


class TestLiveStateAssembler(unittest.TestCase):
    def test_assemble_includes_access_block(self):
        from tiktok_live_state_assembler import assembleLiveState

        state = assembleLiveState("test-acct", {"user_metadata": {"role": "creator"}})
        self.assertIn("access", state)
        self.assertEqual(state["access"]["role"], "creator")
        self.assertFalse(state["access"]["admin_override"])
        self.assertIsInstance(state["access"]["visible_modules"], list)

    def test_admin_assembler_sees_sensitive_fields(self):
        from tiktok_live_state_assembler import assembleLiveState

        state = assembleLiveState("test-acct", {"user_metadata": {"role": "admin"}})
        self.assertTrue(state["access"]["admin_override"])
        self.assertEqual(len(state["access"]["visible_modules"]), len(rbac.ALL_MODULES))


if __name__ == "__main__":
    unittest.main()
