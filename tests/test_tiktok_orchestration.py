"""
Tests for dashboard orchestration layer modules.

All tests run without Supabase credentials — modules must degrade gracefully.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from tiktok_automation_control import getAutomationMode, setAutomationMode
from tiktok_content_approval_engine import approveQueuedContent
from tiktok_live_dashboard_state import build_live_state, _empty_live_state
from tiktok_system_health import compute_system_health


class TestAutomationControl(unittest.TestCase):
    def test_default_mode_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(getAutomationMode("acct_1"), "queue_only")

    def test_auto_post_downgraded_without_flag(self):
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"mode": "auto_post"}]
        )
        with patch.dict(os.environ, {"SUPABASE_URL": "http://x", "SUPABASE_SERVICE_ROLE_KEY": "k"}, clear=False):
            with patch("tiktok_automation_control._get_supabase_client", return_value=mock_client):
                self.assertEqual(getAutomationMode("acct_1"), "queue_only")

    def test_set_mode_invalid(self):
        result = setAutomationMode("acct", "invalid_mode")
        self.assertFalse(result["updated"])
        self.assertEqual(result["error"], "invalid_mode")


class TestContentApproval(unittest.TestCase):
    def test_queue_decision_no_op(self):
        result = approveQueuedContent("id-1", "queue")
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "unchanged")

    def test_missing_content_id(self):
        result = approveQueuedContent("", "approve")
        self.assertEqual(result["error"], "missing_content_id")

    def test_approve_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            result = approveQueuedContent("id-1", "approve")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "missing_supabase_credentials")


class TestLiveDashboardState(unittest.TestCase):
    def test_empty_live_state_contract(self):
        state = _empty_live_state()
        self.assertEqual(state["automation_mode"], "queue_only")
        self.assertEqual(state["pending_posts"], [])
        self.assertEqual(state["system_health"], "degraded")

    def test_build_live_state_safe_default(self):
        with patch.dict(os.environ, {}, clear=True):
            state = build_live_state("acct_1")
        self.assertEqual(state["automation_mode"], "queue_only")
        self.assertIsInstance(state["queued_posts"], list)


class TestSystemHealth(unittest.TestCase):
    def test_failing_without_supabase(self):
        with patch("tiktok_system_health._check_supabase_available", return_value=False):
            self.assertEqual(compute_system_health(), "failing")

    def test_healthy_with_good_signals(self):
        with patch("tiktok_system_health._check_supabase_available", return_value=True):
            with patch("tiktok_system_health._get_supabase_client", return_value=MagicMock()):
                with patch("tiktok_system_health._queue_failure_rate", return_value=0.0):
                    with patch("tiktok_system_health._learning_success_rate", return_value=1.0):
                        self.assertEqual(
                            compute_system_health(apify_feedback={"success": True}),
                            "healthy",
                        )


class TestPipelineLiveState(unittest.TestCase):
    def test_pipeline_includes_live_state(self):
        from tiktok_insights_pipeline import run_hardened_tiktok_pipeline

        sample_videos = [
            {
                "video_id": "v1",
                "url": "https://tiktok.com/@test/video/1",
                "caption": "this protein powder is amazing",
                "author": "testcreator",
                "engagement": {"play_count": 50000, "digg_count": 3000, "comment_count": 200},
                "comments": [{"comment_text": "where did you get that protein powder"}],
            }
        ]

        with patch("tiktok_content_publisher._get_supabase_client", return_value=None):
            with patch("tiktok_performance_tracker._get_supabase_client", return_value=None):
                with patch("tiktok_learning_engine._get_supabase_client", return_value=None):
                    result = run_hardened_tiktok_pipeline(
                        account_id="testcreator",
                        video_inputs=sample_videos,
                        use_apify=False,
                    )

        self.assertIn("live_state", result)
        self.assertEqual(result["live_state"]["automation_mode"], "queue_only")


if __name__ == "__main__":
    unittest.main()
