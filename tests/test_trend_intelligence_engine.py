"""Tests for multi-source Trend Intelligence Engine."""

from __future__ import annotations

import unittest

from trend_intelligence_engine.buying_intent import (
    detect_buying_signals,
    enrich_with_opportunity,
    estimate_buying_intent,
    merge_cross_platform,
    score_opportunity,
)
from trend_intelligence_engine.content_intelligence import generate_content_intelligence
from trend_intelligence_engine.engine import TrendIntelligenceEngine
from trend_intelligence_engine.providers import get_all_providers
from trend_intelligence_engine.recommendations import build_recommendations
from trend_intelligence_engine.types import NormalizedTrendResult


class TestBuyingIntent(unittest.TestCase):
    def test_detect_best_review_patterns(self):
        signals = detect_buying_signals("best british army books review 2026")
        self.assertIn("best", signals)
        self.assertIn("review", signals)

    def test_estimate_buying_intent_high_for_purchase_query(self):
        score = estimate_buying_intent("where can I buy union jack flag alternative to amazon")
        self.assertGreaterEqual(score, 30)

    def test_opportunity_score_range(self):
        result = NormalizedTrendResult(
            trend="best veterans gifts",
            keyword="best veterans gifts",
            source="youtube",
            popularity=70,
            buying_intent=60,
            competition=40,
        )
        enriched = enrich_with_opportunity(result)
        self.assertGreaterEqual(enriched.opportunity.opportunity_score, 0)
        self.assertLessEqual(enriched.opportunity.opportunity_score, 100)

    def test_nan_buying_intent_guarded(self):
        result = NormalizedTrendResult(
            trend="test",
            keyword="test",
            source="news",
            popularity=float("nan"),
            buying_intent=float("nan"),
            competition=float("nan"),
        )
        enriched = enrich_with_opportunity(result)
        self.assertGreaterEqual(enriched.opportunity.opportunity_score, 0)
        self.assertLessEqual(enriched.opportunity.opportunity_score, 100)
        self.assertFalse(str(enriched.opportunity.opportunity_score) == "nan")


class TestContentIntelligence(unittest.TestCase):
    def test_generates_hook_and_format(self):
        result = NormalizedTrendResult(
            trend="best poppy brooch review",
            keyword="best poppy brooch review",
            source="google_trends",
            popularity=65,
            buying_intent=55,
        )
        ci = generate_content_intelligence(result)
        self.assertTrue(ci.hook)
        self.assertTrue(ci.suggested_format)
        self.assertGreater(ci.viral_potential_score, 0)


class TestProviderRegistry(unittest.TestCase):
    def test_all_providers_registered_in_priority_order(self):
        providers = get_all_providers()
        self.assertGreaterEqual(len(providers), 9)
        priorities = [p.priority for p in providers]
        self.assertEqual(priorities, sorted(priorities))
        names = {p.name for p in providers}
        self.assertIn("tiktok_apify", names)
        self.assertIn("google_trends", names)
        self.assertIn("historical", names)


class TestEngine(unittest.TestCase):
    def test_provider_status_never_raises(self):
        engine = TrendIntelligenceEngine()
        status = engine.provider_status()
        self.assertIn("providers_online", status)
        self.assertIn("providers_offline", status)

    def test_merge_cross_platform_boosts_duplicates(self):
        a = NormalizedTrendResult(trend="british pride", keyword="british pride", source="reddit", popularity=50)
        b = NormalizedTrendResult(trend="british pride", keyword="british pride", source="news", popularity=55)
        merged = merge_cross_platform([a, b])
        self.assertEqual(len(merged), 1)
        self.assertGreater(merged[0].popularity, 50)


class TestRecommendations(unittest.TestCase):
    def test_build_recommendations_structure(self):
        opp = enrich_with_opportunity(
            NormalizedTrendResult(
                trend="best remembrance gifts",
                keyword="best remembrance gifts",
                source="youtube",
                popularity=80,
                buying_intent=70,
            )
        )
        rec = build_recommendations([opp], [opp], niche="patriotic")
        self.assertIn("content_to_create_today", rec)
        self.assertIn("tiktok_ideas", rec)
        self.assertIn("primary_action", rec)


if __name__ == "__main__":
    unittest.main()
