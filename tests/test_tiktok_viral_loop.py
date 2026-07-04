"""
Tests for the autonomous viral loop modules.

All tests run without Supabase or Apify credentials — modules must degrade gracefully.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from tiktok_content_publisher import queueContentForPosting, _build_queue_items, _queue_dedupe_key
from tiktok_learning_engine import updateContentStrategy, _compute_weights_from_performance
from tiktok_performance_tracker import trackContentPerformance, _compute_engagement_rate, _extract_performance_metrics


class TestContentPublisher(unittest.TestCase):
    def test_build_queue_items_from_content_pack(self):
        pack = {
            "captions": ["this changed my workouts — Protein Powder"],
            "hashtags": ["#fyp", "#fitness"],
            "hook_variations": ["POV: you found the workout hack"],
        }
        products = [{"product": "Protein Powder", "signal_strength": 0.8}]
        items = _build_queue_items("acct_1", pack, products)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["account_id"], "acct_1")
        self.assertEqual(items[0]["status"], "queued")
        self.assertEqual(items[0]["product_name"], "Protein Powder")

    def test_dedupe_key_is_stable(self):
        key1 = _queue_dedupe_key("acct", "caption", "hook", "product")
        key2 = _queue_dedupe_key("acct", "caption", "hook", "product")
        self.assertEqual(key1, key2)

    def test_queue_without_credentials_degrades(self):
        with patch.dict(os.environ, {}, clear=True):
            result = queueContentForPosting("acct_1", {"captions": ["test"]}, [])
        self.assertEqual(result["queued"], 0)
        self.assertIsNotNone(result.get("error"))

    def test_queue_missing_account_id(self):
        result = queueContentForPosting("", {"captions": ["test"]}, [])
        self.assertEqual(result["error"], "missing_account_id")


class TestPerformanceTracker(unittest.TestCase):
    def test_engagement_rate_computation(self):
        rate = _compute_engagement_rate({
            "play_count": 1000,
            "digg_count": 50,
            "share_count": 10,
            "comment_count": 20,
        })
        self.assertGreater(rate, 0)

    def test_extract_performance_metrics(self):
        metrics = _extract_performance_metrics({
            "url": "https://tiktok.com/@user/video/1",
            "caption": "test caption",
            "author": "user",
            "engagement": {"play_count": 5000, "digg_count": 200, "share_count": 30, "comment_count": 50},
        })
        self.assertEqual(metrics["views"], 5000)
        self.assertIn("engagement_rate", metrics)
        self.assertIn("watch_time", metrics)

    def test_track_without_credentials_degrades(self):
        with patch.dict(os.environ, {}, clear=True):
            result = trackContentPerformance("acct_1")
        self.assertEqual(result["tracked"], 0)
        self.assertIsNotNone(result.get("error"))


class TestLearningEngine(unittest.TestCase):
    def test_compute_weights_from_empty_records(self):
        weights = _compute_weights_from_performance([])
        self.assertIn("caption_style", weights)
        self.assertIn("hashtag_ranking", weights)
        self.assertEqual(weights["sample_count"], 0)

    def test_compute_weights_from_performance_records(self):
        records = [
            {
                "content": {
                    "caption": "POV: this serum changed everything",
                    "hashtags": ["#skincare", "#fyp"],
                    "product_name": "Vitamin C Serum",
                },
                "metrics": {"engagement_rate": 0.08},
            },
            {
                "content": {
                    "caption": "why is nobody talking about this?",
                    "hashtags": ["#beauty"],
                    "product_name": "Moisturizer",
                },
                "metrics": {"engagement_rate": 0.04},
            },
        ]
        weights = _compute_weights_from_performance(records)
        self.assertEqual(weights["sample_count"], 2)
        self.assertGreater(weights["caption_style"]["pov"], weights["caption_style"]["question"])

    def test_update_without_credentials_degrades(self):
        with patch.dict(os.environ, {}, clear=True):
            result = updateContentStrategy("acct_1")
        self.assertFalse(result["updated"])
        self.assertIsNotNone(result.get("error"))


class TestPipelineIntegration(unittest.TestCase):
    def test_pipeline_includes_viral_loop_fields(self):
        from tiktok_insights_pipeline import run_hardened_tiktok_pipeline

        sample_videos = [
            {
                "video_id": "v1",
                "url": "https://tiktok.com/@test/video/1",
                "caption": "this protein powder is amazing everyone needs it",
                "author": "testcreator",
                "engagement": {"play_count": 50000, "digg_count": 3000, "comment_count": 200},
                "comments": [
                    {"comment_text": "where did you get that protein powder", "comment_like_count": 10},
                    {"comment_text": "love this supplement routine", "comment_like_count": 5},
                ],
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

        self.assertTrue(result.get("success"))
        self.assertIn("content_queue", result)
        self.assertIn("performance_tracking", result)
        self.assertIn("strategy_update", result)


if __name__ == "__main__":
    unittest.main()
