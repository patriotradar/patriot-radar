"""Tests for per-user adaptive calibration layer."""

import os
import tempfile
import unittest

from user_calibration import (
    GLOBAL_DEFAULT_BASELINE,
    breakout_multiplier,
    build_calibration_context,
    build_pattern_affinity,
    calibrated_selection_boost,
    classify_post_performance,
    compute_user_baseline,
    detect_baseline_shift,
    flatten_performance_posts,
    load_performance_posts,
    pattern_key_from_candidate,
)


def _posts_for_baseline(views: int, count: int = 25) -> list[dict]:
    return [
        {
            "keyword": "british pride",
            "views": views,
            "likes": max(1, views // 50),
            "comments": 1,
            "shares": 0,
            "format": "Yes/No Debate",
            "emotionalTrigger": "Pride",
        }
        for _ in range(count)
    ]


class TestBaseline(unittest.TestCase):
    def test_uses_global_default_without_posts(self):
        baseline = compute_user_baseline([])
        self.assertEqual(baseline["source"], "global_default")
        self.assertTrue(baseline["insufficient"])

    def test_user_baseline_from_rolling_window(self):
        posts = _posts_for_baseline(500, 30)
        baseline = compute_user_baseline(posts)
        self.assertEqual(baseline["source"], "user_posts")
        self.assertAlmostEqual(baseline["views"], 500.0)
        self.assertFalse(baseline["insufficient"])

    def test_breakout_multiplier_scales_with_dataset(self):
        self.assertEqual(breakout_multiplier(5), 2.0)
        self.assertEqual(breakout_multiplier(15), 2.5)
        self.assertEqual(breakout_multiplier(30), 3.0)


class TestClassification(unittest.TestCase):
    def test_relative_classification_labels(self):
        baseline = {"views": 1000.0, "engagement": 2.0, "post_count": 20}
        self.assertEqual(
            classify_post_performance({"views": 400, "likes": 2, "comments": 0, "shares": 0}, baseline),
            "BELOW_EXPECTATION",
        )
        self.assertEqual(
            classify_post_performance({"views": 1100, "likes": 25, "comments": 2, "shares": 1}, baseline),
            "STRONG",
        )
        self.assertEqual(
            classify_post_performance({"views": 3200, "likes": 120, "comments": 10, "shares": 5}, baseline),
            "BREAKOUT",
        )


class TestShiftDetection(unittest.TestCase):
    def test_detects_recent_underperformance_shift(self):
        baseline = {"views": 1000.0, "engagement": 2.0, "post_count": 20}
        strong = [{"views": 1200, "likes": 30, "comments": 2, "shares": 0, "keyword": "a", "format": "Debate"}] * 12
        weak = [{"views": 300, "likes": 1, "comments": 0, "shares": 0, "keyword": "b", "format": "Debate"}] * 8
        shift = detect_baseline_shift(strong + weak, baseline)
        self.assertTrue(shift["shift_detected"])
        self.assertGreater(shift["recent_weight"], shift["legacy_weight"])


class TestPatternAffinity(unittest.TestCase):
    def test_prefers_strong_patterns_over_weak(self):
        baseline = {"views": 1000.0, "engagement": 2.0, "post_count": 20}
        posts = [
            {
                "keyword": "british pride",
                "views": 3500,
                "likes": 140,
                "comments": 8,
                "shares": 2,
                "format": "Yes/No Debate",
                "emotionalTrigger": "Pride",
            },
            {
                "keyword": "remembrance",
                "views": 350,
                "likes": 2,
                "comments": 0,
                "shares": 0,
                "format": "Story/Nostalgia",
                "emotionalTrigger": "Nostalgia",
            },
        ]
        affinity = build_pattern_affinity(posts, baseline, detect_baseline_shift(posts, baseline))
        pride_key = "british pride|debate|pride"
        self.assertIn(pride_key, affinity)
        self.assertGreater(affinity[pride_key], 0)

    def test_calibrated_boost_favors_historically_strong_topic(self):
        performance = {
            "british pride": [
                {
                    "views": 4000,
                    "likes": 180,
                    "comments": 12,
                    "shares": 4,
                    "format": "Yes/No Debate",
                    "emotionalTrigger": "Pride",
                }
            ]
            * 12,
            "remembrance": [
                {
                    "views": 250,
                    "likes": 1,
                    "comments": 0,
                    "shares": 0,
                    "format": "Story/Nostalgia",
                    "emotionalTrigger": "Nostalgia",
                }
            ]
            * 12,
        }
        context = build_calibration_context(performance)
        pride_item = {
            "keyword": "british pride",
            "content_score": 60,
            "opportunity_gap": 5,
            "viral_score": 30,
            "debate": 20,
            "emotion": 18,
        }
        remembrance_item = {
            "keyword": "remembrance",
            "content_score": 70,
            "opportunity_gap": 7,
            "viral_score": 40,
            "debate": 12,
            "emotion": 20,
        }
        pride_boost = calibrated_selection_boost(pride_item, context, "HEALTHY")
        remembrance_boost = calibrated_selection_boost(remembrance_item, context, "HEALTHY")
        self.assertGreater(pride_boost, remembrance_boost)


class TestPerformanceLoading(unittest.TestCase):
    def test_flattens_keyword_keyed_performance(self):
        raw = {
            "british pride": [{"views": 100, "likes": 5, "format": "Debate"}],
            "remembrance": [{"views": 200, "likes": 8, "format": "Story"}],
        }
        posts = flatten_performance_posts(raw)
        self.assertEqual(len(posts), 2)
        keywords = {p["keyword"] for p in posts}
        self.assertIn("british pride", keywords)
        self.assertIn("remembrance", keywords)

    def test_load_performance_posts_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "performance_posts.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"british pride": [{"views": 900, "likes": 20, "format": "Debate"}]}')
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                posts = load_performance_posts()
                self.assertEqual(len(posts), 1)
                self.assertEqual(posts[0]["keyword"], "british pride")
            finally:
                os.chdir(cwd)


class TestCandidatePatterns(unittest.TestCase):
    def test_candidate_pattern_key_uses_item_signals(self):
        item = {"keyword": "veterans", "debate": 20, "emotion": 10}
        key = pattern_key_from_candidate(item, "HEALTHY")
        self.assertIn("veterans", key)
        self.assertIn("debate", key)


if __name__ == "__main__":
    unittest.main()
