"""Tests for AI Code Governance safety rules."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ai_governance_risk as risk
import ai_governance_safe_patch as patch


class TestBlockedPaths(unittest.TestCase):
    def test_api_routes_blocked(self):
        self.assertTrue(risk.is_blocked_path("api/tiktok-insights.js"))

    def test_sql_schema_blocked(self):
        self.assertTrue(risk.is_blocked_path("sql/trend_intelligence_feed.sql"))

    def test_scoring_file_blocked(self):
        self.assertTrue(risk.is_blocked_path("virality_scoring_engine.py"))

    def test_safe_utility_not_blocked(self):
        self.assertFalse(risk.is_blocked_path("system_health_monitor.py"))


class TestRiskClassification(unittest.TestCase):
    def test_null_guard_is_safe(self):
        diff = """--- a/foo.js
+++ b/foo.js
@@ -1,1 +1,1 @@
-const x = obj.value;
+const x = obj?.value;
"""
        result = risk.classify_risk(source_file="foo.js", proposed_fix=diff)
        self.assertEqual(result, "SAFE")

    def test_multi_file_is_blocked(self):
        diff = """--- a/foo.js
+++ b/foo.js
@@ -1 +1 @@
-x
+y
--- a/bar.js
+++ b/bar.js
@@ -1 +1 @@
-a
+b
"""
        result = risk.classify_risk(source_file="foo.js", proposed_fix=diff)
        self.assertEqual(result, "BLOCKED")

    def test_blocked_path_overrides_safe_diff(self):
        diff = """--- a/api/foo.js
+++ b/api/foo.js
@@ -1,1 +1,1 @@
-const x = obj.value;
+const x = obj?.value;
"""
        result = risk.classify_risk(source_file="api/foo.js", proposed_fix=diff)
        self.assertEqual(result, "BLOCKED")


class TestAutoApplicable(unittest.TestCase):
    def test_requires_safe_and_approved(self):
        self.assertTrue(
            risk.compute_auto_applicable(
                risk="SAFE", gemini_status="APPROVED", source_file="utils.js"
            )
        )
        self.assertFalse(
            risk.compute_auto_applicable(
                risk="REVIEW", gemini_status="APPROVED", source_file="utils.js"
            )
        )
        self.assertFalse(
            risk.compute_auto_applicable(
                risk="SAFE", gemini_status="REJECTED", source_file="utils.js"
            )
        )


class TestSafePatchEngine(unittest.TestCase):
    def test_rejects_non_approved(self):
        issue = {
            "risk": "SAFE",
            "gemini_status": "APPROVED",
            "admin_status": "pending",
            "source_file": "test.js",
            "proposed_fix": "",
        }
        with self.assertRaises(patch.PatchError):
            patch.apply_patch(issue)

    def test_applies_single_line_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sample.js"
            target.write_text("const x = obj.value;\n", encoding="utf-8")

            rel = "sample.js"
            diff = """--- a/sample.js
+++ b/sample.js
@@ -1,1 +1,1 @@
-const x = obj.value;
+const x = obj?.value;
"""
            issue = {
                "risk": "SAFE",
                "gemini_status": "APPROVED",
                "admin_status": "approved",
                "source_file": rel,
                "proposed_fix": diff,
            }

            with mock.patch.object(patch, "REPO_ROOT", Path(tmp)):
                result = patch.apply_patch(issue)
                self.assertTrue(result["success"])
                self.assertIn("?.", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
