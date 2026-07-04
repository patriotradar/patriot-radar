"""
Tests for tiktok_system_snapshot_builder — snapshot capture and fail-safety.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tiktok_system_snapshot_builder import (
    buildSystemSnapshot,
    empty_system_snapshot,
)


class TestSnapshotBuilder(unittest.TestCase):
    def test_empty_snapshot_is_safe_default(self):
        snapshot = empty_system_snapshot()
        self.assertEqual(snapshot["trends_snapshot"]["trends"], [])
        self.assertEqual(snapshot["product_snapshot"]["emerging"], [])
        self.assertEqual(snapshot["inventory_snapshot"]["inventory_gaps"], [])
        self.assertEqual(snapshot["queue_snapshot"]["content_queue"], [])
        self.assertEqual(snapshot["approval_snapshot"]["approvals"], [])
        self.assertEqual(snapshot["performance_snapshot"]["performance"], {})
        self.assertEqual(snapshot["learning_snapshot"]["learning"], {})
        self.assertEqual(snapshot["system_health_snapshot"]["system_health"], "unknown")

    def test_build_never_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            snapshot = buildSystemSnapshot("")
        self.assertIsInstance(snapshot, dict)
        self.assertIn("snapshot_at", snapshot)

    def test_build_records_partial_failures_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            snapshot = buildSystemSnapshot("no_creds")
        self.assertIsInstance(snapshot["partial_failures"], list)

    def test_build_all_modules_at_once(self):
        snapshot = buildSystemSnapshot("acct_parallel")
        self.assertIn("trends_snapshot", snapshot)
        self.assertIn("product_snapshot", snapshot)
        self.assertIn("inventory_snapshot", snapshot)
        self.assertIn("queue_snapshot", snapshot)
        self.assertIn("approval_snapshot", snapshot)
        self.assertIn("performance_snapshot", snapshot)
        self.assertIn("learning_snapshot", snapshot)
        self.assertIn("system_health_snapshot", snapshot)


if __name__ == "__main__":
    unittest.main()
