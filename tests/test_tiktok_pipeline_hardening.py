"""Tests for TikTok pipeline hardening layer."""

from __future__ import annotations

import unittest

from tiktok_pipeline_hardening import (
    build_safe_pipeline_response,
    clean_comments,
    compute_trend_score,
    empty_pipeline_response,
    generate_insights,
    generate_post_recommendations,
    validate_insights,
    validate_videos,
)


class TestValidateVideos(unittest.TestCase):
    def test_rejects_empty_engagement_without_caption(self):
        result = validate_videos([{"url": "https://tiktok.com/@x/video/1"}])
        self.assertEqual(result["stats"]["accepted_count"], 0)

    def test_accepts_video_with_engagement(self):
        video = {
            "video_id": "123",
            "url": "https://tiktok.com/@x/video/123",
            "caption": "Fitness tips",
            "engagement": {"play_count": 1000, "digg_count": 50, "comment_count": 10},
        }
        result = validate_videos([video])
        self.assertEqual(result["stats"]["accepted_count"], 1)
        self.assertGreater(result["accepted"][0]["quality_score"], 0.4)

    def test_accepts_manual_caption_without_engagement(self):
        video = {"caption": "Nobody is talking about British pride on TikTok right now."}
        result = validate_videos([video])
        self.assertEqual(result["stats"]["accepted_count"], 1)


class TestTrendScore(unittest.TestCase):
    def test_trend_score_components(self):
        video = {
            "video_id": "1",
            "url": "https://tiktok.com/@x/video/1",
            "engagement": {"play_count": 1000, "digg_count": 100, "comment_count": 50},
            "create_time": 1700000000,
        }
        score = compute_trend_score(video)
        self.assertIn("velocity_score", score)
        self.assertIn("engagement_score", score)
        self.assertIn("freshness_score", score)
        self.assertGreater(score["trend_score"], 0)

    def test_missing_age_marks_low_confidence(self):
        video = {
            "video_id": "1",
            "engagement": {"play_count": 500, "digg_count": 10, "comment_count": 5},
        }
        score = compute_trend_score(video)
        self.assertTrue(score["low_confidence"])
        self.assertEqual(score["age_hours"], 168.0)


class TestCleanComments(unittest.TestCase):
    def test_removes_short_and_duplicate_comments(self):
        comments = [
            {"text": "ok"},
            {"text": "How do I stay consistent with gym workouts"},
            {"text": "How do I stay consistent with gym workouts"},
            {"text": "🔥🔥🔥"},
        ]
        cleaned = clean_comments(comments)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["text"], "how do i stay consistent with gym workouts")


class TestInsights(unittest.TestCase):
    def test_generates_evidence_based_insights(self):
        comments = [
            {"text": "how do i stay consistent after week 2", "video_id": "1"},
            {"text": "why does nobody talk about consistency", "video_id": "1"},
            {"text": "how do i stay consistent after week 2", "video_id": "2"},
            {"text": "beginners struggle with gym consistency", "video_id": "2"},
        ]
        videos = [
            {"video_id": "1", "caption": "fitness routine", "comments": comments[:2]},
            {"video_id": "2", "caption": "gym tips", "comments": comments[2:]},
        ]
        cleaned = clean_comments(comments)
        insights = generate_insights(videos, cleaned, niche="fitness")
        self.assertTrue(insights)
        for insight in insights:
            self.assertGreater(insight["evidence_count"], 0)
            self.assertIn(insight["confidence"], ("high", "medium", "low"))
            self.assertTrue(insight["based_on_examples"])

    def test_validate_insights_filters_weak_signals(self):
        insights = [
            {
                "insight": "beginners struggle with consistency after week 2",
                "evidence_count": 1,
                "confidence": "low",
                "based_on_examples": ["only once"],
                "phrase": "week 2",
                "video_count": 1,
            },
            {
                "insight": "viewers ask questions about progressive overload",
                "evidence_count": 12,
                "confidence": "high",
                "based_on_examples": ["a", "b", "c"],
                "phrase": "progressive overload",
                "video_count": 3,
            },
        ]
        comments = [{"text": "progressive overload progressive overload"} for _ in range(5)]
        validated = validate_insights(insights, comments, [])
        self.assertTrue(any(i["evidence_count"] >= 10 for i in validated))


class TestRecommendations(unittest.TestCase):
    def test_empty_insights_returns_empty_posts(self):
        result = generate_post_recommendations([], [])
        self.assertEqual(result["recommended_posts"], [])

    def test_maps_to_real_insights(self):
        insights = [{
            "insight": "beginners in fitness struggle to stay consistent after week 2",
            "evidence_count": 5,
            "confidence": "medium",
            "based_on_examples": ["how do i stay consistent"],
        }]
        result = generate_post_recommendations(insights, [])
        self.assertTrue(result["recommended_posts"])
        post = result["recommended_posts"][0]
        self.assertIn("hook", post)
        self.assertIn("format", post)
        self.assertTrue(post["based_on"])


class TestSafeResponse(unittest.TestCase):
    def test_empty_response_has_no_nulls(self):
        resp = empty_pipeline_response()
        for key in ("videos", "insights", "recommended_posts", "trend_scores", "errors"):
            self.assertIn(key, resp)
            self.assertIsNotNone(resp[key])

    def test_build_safe_pipeline_response(self):
        resp = build_safe_pipeline_response(
            videos=[{"id": 1}],
            insights=[{"insight": "test", "evidence_count": 3, "confidence": "medium", "based_on_examples": []}],
        )
        self.assertEqual(len(resp["videos"]), 1)
        self.assertEqual(len(resp["insights"]), 1)


if __name__ == "__main__":
    unittest.main()
