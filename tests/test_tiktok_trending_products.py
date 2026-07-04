"""Tests for trending products detection engine and pipeline integration."""

from __future__ import annotations

import unittest

from tiktok_insights_pipeline import run_hardened_pipeline_from_raw_rows
from tiktok_pipeline_hardening import build_safe_pipeline_response, empty_pipeline_response
from tiktok_trending_products_engine import generateTrendingProducts


class TestTrendingProductsEmptyInput(unittest.TestCase):
    def test_empty_input_returns_list(self):
        result = generateTrendingProducts(None, None, "", None)
        self.assertEqual(result, [])
        self.assertIsInstance(result, list)

    def test_empty_videos_and_comments(self):
        result = generateTrendingProducts([], [], "fitness", [])
        self.assertEqual(result, [])


class TestTrendingProductsAggregation(unittest.TestCase):
    def test_duplicate_aggregation(self):
        comments = [
            {"text": "love this collagen protein powder", "video_id": "1"},
            {"text": "where to buy collagen protein powder", "video_id": "1"},
            {"text": "collagen protein powder works great", "video_id": "2"},
        ]
        videos = [
            {
                "video_id": "1",
                "engagement": {"play_count": 5000, "digg_count": 200, "comment_count": 3},
            },
            {
                "video_id": "2",
                "engagement": {"play_count": 8000, "digg_count": 400, "comment_count": 2},
            },
        ]
        trend_scores = [
            {"video_id": "1", "velocity_score": 100.0, "engagement_score": 0.04},
            {"video_id": "2", "velocity_score": 200.0, "engagement_score": 0.05},
        ]
        result = generateTrendingProducts(videos, comments, niche="fitness", trend_scores=trend_scores)
        self.assertTrue(result)
        top = result[0]
        self.assertIn("name", top)
        self.assertGreaterEqual(top["mention_count"], 2)
        self.assertGreaterEqual(top["video_count"], 1)
        self.assertIn("score", top)
        self.assertIn("evidence", top)
        self.assertIsInstance(top["evidence"], list)


class TestTrendingProductsScoringThreshold(unittest.TestCase):
    def test_no_comments_returns_empty(self):
        videos = [{"video_id": "1", "engagement": {"play_count": 100, "digg_count": 1, "comment_count": 1}}]
        result = generateTrendingProducts(videos, [], niche="", trend_scores=[])
        self.assertEqual(result, [])

    def test_high_score_included(self):
        comments = [
            {"text": "vitamin serum routine amazing", "video_id": "1"},
            {"text": "vitamin serum routine best", "video_id": "2"},
            {"text": "vitamin serum routine love", "video_id": "2"},
        ]
        videos = [
            {"video_id": "1", "engagement": {"play_count": 50000, "digg_count": 5000, "comment_count": 10}},
            {"video_id": "2", "engagement": {"play_count": 80000, "digg_count": 8000, "comment_count": 15}},
        ]
        trend_scores = [
            {"video_id": "1", "velocity_score": 500.0},
            {"video_id": "2", "velocity_score": 800.0},
        ]
        result = generateTrendingProducts(videos, comments, niche="skincare", trend_scores=trend_scores)
        self.assertTrue(result)
        for product in result:
            self.assertGreaterEqual(product["score"], 0.0)
            self.assertLessEqual(product["score"], 1.0)
            passed_filter = (
                product["mention_count"] >= 2
                or product["video_count"] >= 2
                or product["score"] >= 0.6
            )
            self.assertTrue(passed_filter)


class TestTrendingProductsFailSafe(unittest.TestCase):
    def test_invalid_inputs_never_raise(self):
        result = generateTrendingProducts(
            videos=[{"bad": object()}],
            comments=[None, "not a dict", {"text": ""}],
            niche=None,
            trend_scores=[None],
        )
        self.assertIsInstance(result, list)


class TestPipelineIntegration(unittest.TestCase):
    def test_pipeline_includes_trending_products(self):
        raw_rows = [
            {
                "video_id": "v1",
                "video_url": "https://tiktok.com/@x/video/1",
                "video_caption": "skincare routine",
                "video_author": "creator",
                "comment_text": "love this vitamin serum product",
            },
            {
                "video_id": "v1",
                "video_url": "https://tiktok.com/@x/video/1",
                "video_caption": "skincare routine",
                "video_author": "creator",
                "comment_text": "vitamin serum product works great",
            },
            {
                "video_id": "v2",
                "video_url": "https://tiktok.com/@x/video/2",
                "video_caption": "morning skincare",
                "video_author": "creator2",
                "comment_text": "vitamin serum product recommend",
            },
        ]
        result = run_hardened_pipeline_from_raw_rows(raw_rows, niche="skincare")
        self.assertIn("trending_products", result)
        self.assertIsInstance(result["trending_products"], list)
        self.assertIsNotNone(result["trending_products"])


class TestSafeResponseContract(unittest.TestCase):
    def test_empty_response_includes_trending_products(self):
        resp = empty_pipeline_response()
        self.assertIn("trending_products", resp)
        self.assertEqual(resp["trending_products"], [])

    def test_build_safe_pipeline_response_includes_trending_products(self):
        products = [{
            "name": "Test Product",
            "mention_count": 3,
            "video_count": 2,
            "trend_velocity": 0.5,
            "niche_relevance": 0.4,
            "confidence": 0.6,
            "evidence": ["example"],
            "score": 0.7,
        }]
        resp = build_safe_pipeline_response(trending_products=products)
        self.assertEqual(len(resp["trending_products"]), 1)
        self.assertEqual(resp["trending_products"][0]["name"], "Test Product")

    def test_build_safe_pipeline_response_defaults_empty_trending_products(self):
        resp = build_safe_pipeline_response()
        self.assertIn("trending_products", resp)
        self.assertEqual(resp["trending_products"], [])


if __name__ == "__main__":
    unittest.main()
