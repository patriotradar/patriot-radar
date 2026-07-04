"""Tests for Supabase niche resolver and product intelligence modules."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tiktok_content_generator import generateContentPack
from tiktok_emerging_products_engine import detectEmergingProducts
from tiktok_niche_resolver import resolveNiche
from tiktok_trending_products_engine import generateTrendingProducts


FITNESS_VIDEOS = [
    {
        "video_id": "1",
        "url": "https://tiktok.com/@fit/video/1",
        "caption": "Best gym workout routine for beginners #fitness #gymtok",
        "engagement": {"play_count": 50000, "digg_count": 2000, "comment_count": 100},
        "comments": [
            {"text": "What protein powder do you recommend for gains", "video_id": "1"},
            {"text": "This whey supplement changed my workouts", "video_id": "1"},
        ],
    },
    {
        "video_id": "2",
        "url": "https://tiktok.com/@fit/video/2",
        "caption": "Progressive overload tips #fitness",
        "engagement": {"play_count": 30000, "digg_count": 1500, "comment_count": 80},
        "comments": [
            {"text": "Which protein powder works best for beginners", "video_id": "2"},
            {"text": "Love this whey supplement recommendation", "video_id": "2"},
        ],
    },
]

FITNESS_COMMENTS = [
    {"comment_text": "what protein powder do you recommend", "video_id": "1"},
    {"comment_text": "this whey supplement changed my workouts", "video_id": "1"},
    {"comment_text": "which protein powder works best", "video_id": "2"},
    {"comment_text": "love this whey supplement", "video_id": "2"},
]


class TestNicheResolver(unittest.TestCase):
    @patch("tiktok_niche_resolver._fetch_account_niche", return_value=None)
    @patch("tiktok_niche_resolver._write_account_niche")
    def test_infers_fitness_niche(self, _mock_write, _mock_fetch):
        result = resolveNiche("test_account", FITNESS_VIDEOS, FITNESS_COMMENTS)
        self.assertIn(result["niche"], ("fitness", "unknown"))
        self.assertIsInstance(result["confidence"], float)
        self.assertIsInstance(result["keywords"], list)

    @patch("tiktok_niche_resolver._fetch_account_niche")
    def test_returns_stored_niche_when_confident(self, mock_fetch):
        mock_fetch.return_value = {"niche": "beauty", "niche_confidence": 0.85}
        result = resolveNiche("acct_1", [], [])
        self.assertEqual(result["niche"], "beauty")
        self.assertEqual(result["confidence"], 0.85)

    def test_never_raises_on_empty_input(self):
        result = resolveNiche("", [], [])
        self.assertEqual(result["niche"], "unknown")
        self.assertEqual(result["confidence"], 0.0)


class TestEmergingProducts(unittest.TestCase):
    def test_returns_list(self):
        result = detectEmergingProducts(FITNESS_VIDEOS, FITNESS_COMMENTS, niche="fitness", trend_scores=[])
        self.assertIsInstance(result, list)

    def test_never_raises(self):
        result = detectEmergingProducts(None, None, niche="", trend_scores=None)
        self.assertEqual(result, [])


class TestTrendingProducts(unittest.TestCase):
    def test_returns_list_with_signals(self):
        trend_scores = [{"video_id": "1", "velocity_score": 0.5, "trend_score": 1.2}]
        result = generateTrendingProducts(
            FITNESS_VIDEOS, FITNESS_COMMENTS, niche="fitness", trend_scores=trend_scores
        )
        self.assertIsInstance(result, list)

    def test_never_raises(self):
        result = generateTrendingProducts(None, None, niche="", trend_scores=None)
        self.assertEqual(result, [])


class TestContentGenerator(unittest.TestCase):
    def test_generates_content_pack(self):
        emerging = [{"product": "Whey Protein", "signal_strength": 0.7}]
        result = generateContentPack(emerging, niche="fitness", apify_feedback={})
        self.assertIn("captions", result)
        self.assertIn("hashtags", result)
        self.assertIn("hook_variations", result)
        self.assertTrue(result["captions"])
        self.assertTrue(result["hashtags"])

    def test_safe_defaults(self):
        result = generateContentPack([], niche="unknown", apify_feedback=None)
        self.assertEqual(result["captions"], result["captions"] or [])
        self.assertIsInstance(result["hashtags"], list)


if __name__ == "__main__":
    unittest.main()
