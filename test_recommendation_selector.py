"""Tests for single-decision recommendation selector."""

import unittest

from recommendation_selector import (
    compute_base_score,
    compute_viral_potential_signal,
    final_recommendation_selector,
    gather_candidates,
    repetition_penalty_signal,
    _compose_final_score,
    _score_candidate,
)
from recommendation_output import _build_recommendation_for_item


SAMPLE_ITEM = {
    "keyword": "british pride",
    "category": "content",
    "content_score": 72,
    "viral_score": 45,
    "opportunity_gap": 7.5,
    "opportunity_label": "High Opportunity",
    "rise_percent": 22,
    "emotion": 20,
    "debate": 19,
    "british": 22,
    "fresh": 15,
    "discovery_type": "reddit",
    "platform_count": 2,
    "question": "Is British Pride being ignored?",
    "caption": "Test caption",
    "product": "union jack mug",
}

SAMPLE_ITEM_B = {
    "keyword": "remembrance",
    "category": "emerging",
    "content_score": 68,
    "viral_score": 40,
    "opportunity_gap": 6.8,
    "opportunity_label": "Good Opportunity",
    "rise_percent": 18,
    "emotion": 22,
    "debate": 14,
    "british": 20,
    "fresh": 12,
    "discovery_type": "news",
    "platform_count": 1,
    "question": "Should we still honour Remembrance?",
    "caption": "Remembrance caption",
    "product": "poppy pin",
}


class TestSignalProviders(unittest.TestCase):
    def test_gather_candidates_does_not_rank(self):
        candidates = gather_candidates([SAMPLE_ITEM_B], [SAMPLE_ITEM])
        self.assertEqual(len(candidates), 2)

    def test_base_score_is_signal_only(self):
        score = compute_base_score(SAMPLE_ITEM)
        self.assertGreater(score, 0)

    def test_viral_signal_does_not_reject(self):
        signal = compute_viral_potential_signal(SAMPLE_ITEM)
        self.assertIn("viral_potential_score", signal)
        self.assertIn("low_confidence", signal)

    def test_repetition_penalty_not_rejection(self):
        history = [
            {
                "keyword": "british pride",
                "format_family": "reaction",
                "emotional_trigger": "curiosity",
            }
        ]
        penalty = repetition_penalty_signal(
            "british pride",
            "News reaction clip with bold on-screen headline",
            "pride",
            history,
        )
        self.assertGreater(penalty, 0)


class TestFinalSelectorAuthority(unittest.TestCase):
    def test_only_selector_picks_winner(self):
        item, draft, trigger = final_recommendation_selector(
            [SAMPLE_ITEM, SAMPLE_ITEM_B],
            [],
            None,
            {},
            [],
            _build_recommendation_for_item,
        )
        self.assertIsNotNone(item)
        self.assertIn(item["keyword"], ("british pride", "remembrance"))
        self.assertIn("next_post", draft)
        self.assertTrue(trigger)

    def test_repetition_penalty_can_change_winner(self):
        history = [
            {
                "keyword": "british pride",
                "format_family": "reaction",
                "emotional_trigger": "pride",
            }
        ]
        scored_a = _score_candidate(
            SAMPLE_ITEM, "HEALTHY", {}, history, _build_recommendation_for_item, None
        )
        scored_b = _score_candidate(
            SAMPLE_ITEM_B, "HEALTHY", {}, history, _build_recommendation_for_item, None
        )
        self.assertGreater(scored_a.repetition_penalty, scored_b.repetition_penalty)

        item, _, _ = final_recommendation_selector(
            [SAMPLE_ITEM, SAMPLE_ITEM_B],
            [],
            None,
            {},
            history,
            _build_recommendation_for_item,
        )
        self.assertEqual(item["keyword"], "remembrance")

    def test_fallback_when_no_candidates(self):
        fallback = {"state": "NO_TRACTION", "engagement_signal": "HEALTHY", "next_post": {}}
        item, draft, trigger = final_recommendation_selector(
            [],
            [],
            None,
            {},
            [],
            _build_recommendation_for_item,
            structural_fallback=fallback,
        )
        self.assertIsNone(item)
        self.assertEqual(draft, fallback)
        self.assertEqual(trigger, "curiosity")

    def test_compose_final_score_formula(self):
        score = _compose_final_score(
            base_score=5.0,
            calibration_boost=1.0,
            repetition_penalty=2.0,
            viral_potential_score=2.0,
        )
        self.assertAlmostEqual(score, 5.0 + 2.5 - 2.0 + 1.5)


if __name__ == "__main__":
    unittest.main()
