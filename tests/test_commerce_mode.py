#!/usr/bin/env python3
"""Tests for commerce_mode feature flag and live state assembly."""

from __future__ import annotations

import unittest

from commerce import is_commerce_enabled, run_commerce_pipeline
from commerce.product_detection import detect_products_from_trends
from tiktok_live_state_assembler import assembleLiveState


class TestCommerceMode(unittest.TestCase):
    def test_default_commerce_mode_false(self):
        state = assembleLiveState("test-account", commerce_mode=False)
        self.assertFalse(state["features"]["commerce_mode"])
        self.assertEqual(state["today_flow"]["step"], "trend → content → plan → insights")
        self.assertEqual(state["products"], [])
        self.assertEqual(state["inventory_gaps"], [])

    def test_commerce_mode_true_enables_commerce_fields(self):
        state = assembleLiveState("test-account", commerce_mode=True)
        self.assertTrue(state["features"]["commerce_mode"])
        self.assertIn("product", state["today_flow"]["step"])
        self.assertIn("products", state)
        self.assertIn("revenue_suggestions", state)

    def test_core_state_never_null(self):
        for mode in (False, True):
            state = assembleLiveState("", commerce_mode=mode)
            self.assertIsInstance(state, dict)
            self.assertIn("features", state)
            self.assertIn("trends", state)
            self.assertIn("today_flow", state)

    def test_is_commerce_enabled(self):
        self.assertFalse(is_commerce_enabled(False))
        self.assertFalse(is_commerce_enabled(None))
        self.assertTrue(is_commerce_enabled(True))

    def test_product_detection_from_trends(self):
        trends = [{"keyword": "British Army history", "viral_score": 72}]
        products = detect_products_from_trends(trends)
        self.assertEqual(len(products), 1)
        self.assertIn("Army", products[0]["name"])

    def test_commerce_pipeline_fail_safe(self):
        result = run_commerce_pipeline("test", trends=[{"keyword": "skincare routine", "viral_score": 60}])
        self.assertIn("products", result)
        self.assertIn("inventory_gaps", result)
        self.assertIsInstance(result["products"], list)

    def test_core_works_when_commerce_pipeline_runs_empty(self):
        state = assembleLiveState("test", commerce_mode=False)
        self.assertEqual(state["primary_action"]["action"], "view_plan")


if __name__ == "__main__":
    unittest.main()
