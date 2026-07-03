"""Tests for final recommendation humanisation and repetition control."""

import json
import os
import tempfile
import unittest

from recommendation_output import (
    BANNED_TERMS,
    finalize_recommendation,
    humanise_next_post,
    load_recommendation_history,
    rank_recommendation_candidates,
    save_recommendation_history,
    select_recommendation_with_diversity,
    _build_recommendation_for_item,
    _humanise_hook,
    _is_generic_hook,
    _strip_analytics_language,
)


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
    "question": "Is British Pride being ignored in modern Britain? Yes or No?",
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
    "question": "Should we still honour Remembrance the same way? Yes or No?",
    "caption": "Remembrance caption",
    "product": "poppy pin",
}


class TestAnalyticsStripping(unittest.TestCase):
    def test_removes_banned_terms(self):
        raw = (
            "Content score is 72/100 with high opportunity. "
            "Engagement rate looks weak and viral momentum is rising."
        )
        cleaned = _strip_analytics_language(raw)
        lowered = cleaned.lower()
        for term in ("score", "engagement rate", "viral", "momentum"):
            self.assertNotIn(term, lowered)

    def test_generic_hook_detected(self):
        self.assertTrue(_is_generic_hook("Is British Pride being ignored? Yes or No?"))
        self.assertFalse(_is_generic_hook("Why younger Brits feel awkward about flag-waving"))


class TestHumanisation(unittest.TestCase):
    def test_hook_rewrites_generic_template(self):
        hook = _humanise_hook(
            "Is British Pride being ignored in modern Britain? Yes or No?",
            "british pride",
            SAMPLE_ITEM,
            "HEALTHY",
        )
        self.assertNotIn("Yes or No?", hook)
        self.assertNotIn("being ignored", hook.lower())

    def test_content_idea_is_specific(self):
        raw = "Double down on your best-performing angle for British Pride: refine the existing hook."
        post = humanise_next_post(
            {
                "hook": "generic",
                "content_idea": raw,
                "format": "Yes/No debate post",
                "reason_it_will_perform_better": "content score 72/100",
            },
            SAMPLE_ITEM,
            "HEALTHY",
        )
        idea = post["content_idea"].lower()
        self.assertNotIn("double down", idea)
        self.assertTrue(len(post["content_idea"]) > 50)

    def test_reason_is_short_and_human(self):
        post = humanise_next_post(
            {
                "hook": "test",
                "content_idea": "test idea",
                "format": "Yes/No debate post",
                "reason_it_will_perform_better": (
                    "Opportunity gap 7.5/10, content score 72/100, debate 19/25."
                ),
            },
            SAMPLE_ITEM,
            "HEALTHY",
        )
        reason = post["reason_it_will_perform_better"]
        self.assertLessEqual(len(reason.split(".")), 3)
        self.assertIn("audience", reason.lower())


class TestRepetitionControl(unittest.TestCase):
    def test_avoids_topic_format_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = os.path.join(tmp, "history.json")
            save_recommendation_history(
                {
                    "keyword": "british pride",
                    "format_family": "reaction",
                    "emotional_trigger": "curiosity",
                    "hook": "old hook",
                },
                path=history_path,
            )
            history = load_recommendation_history(history_path)
            results = [SAMPLE_ITEM, SAMPLE_ITEM_B]
            emerging = []

            selected_item, _, _ = select_recommendation_with_diversity(
                results,
                emerging,
                None,
                history,
                _build_recommendation_for_item,
            )
            self.assertEqual(selected_item["keyword"], "remembrance")

    def test_finalize_writes_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = os.path.join(tmp, "history.json")
            draft = _build_recommendation_for_item(SAMPLE_ITEM, None)
            final = finalize_recommendation(
                draft,
                [SAMPLE_ITEM],
                [],
                None,
                history_path=history_path,
            )
            self.assertTrue(os.path.exists(history_path))
            with open(history_path, encoding="utf-8") as f:
                history = json.load(f)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["keyword"], "british pride")
            for term in BANNED_TERMS:
                combined = " ".join(
                    [
                        final.get("insight_summary", ""),
                        final["next_post"].get("hook", ""),
                        final["next_post"].get("content_idea", ""),
                        final["next_post"].get("reason_it_will_perform_better", ""),
                    ]
                ).lower()
                if term in ("score", "trend", "viral", "momentum"):
                    self.assertNotIn(term, combined)


class TestCandidateRanking(unittest.TestCase):
    def test_ranks_by_opportunity_then_content(self):
        ranked = rank_recommendation_candidates([SAMPLE_ITEM_B], [SAMPLE_ITEM])
        self.assertEqual(ranked[0]["keyword"], "british pride")


if __name__ == "__main__":
    unittest.main()
