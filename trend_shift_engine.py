"""
Trend shift detection engine — read-only external signal aggregation.

Consumes external platform signals (e.g. TikTok) for early pattern detection.
Does NOT feed into scoring, final_recommendation_selector, calibration, or captions.
"""

from __future__ import annotations

from typing import Any

from tiktok_trend_extractor import extract_tiktok_trend_signals

_EMPTY_TIKTOK_SIGNALS: dict[str, Any] = {
    "platform": "tiktok",
    "timestamp": "",
    "extracted_items": [],
    "aggregated_signals": {
        "dominant_hooks": [],
        "dominant_formats": [],
        "emotional_distribution": {},
        "rising_topics": [],
        "keyword_velocity_signals": [],
        "viral_pattern_summary": "",
    },
    "insight_summary": "",
}


def ingest_external_tiktok_signals(
    tiktok_inputs: list[str | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Run TikTok trend extraction and return read-only external signals.

    Safe to call with None or empty input — always returns a structured object.
    """
    try:
        if not tiktok_inputs:
            return dict(_EMPTY_TIKTOK_SIGNALS)
        return extract_tiktok_trend_signals(tiktok_inputs)
    except Exception:
        return dict(_EMPTY_TIKTOK_SIGNALS)


class TrendShiftEngine:
    """
    Aggregates external trend signals for shift detection.

    Output is observational only — it must not influence recommendation
    selection or internal scoring pipelines.
    """

    def __init__(self) -> None:
        self.external_tiktok_signals: dict[str, Any] = dict(_EMPTY_TIKTOK_SIGNALS)

    def load_tiktok_signals(
        self,
        tiktok_inputs: list[str | dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ingest TikTok content and store as external_tiktok_signals."""
        self.external_tiktok_signals = ingest_external_tiktok_signals(tiktok_inputs)
        return self.external_tiktok_signals

    def get_external_signals(self) -> dict[str, Any]:
        """Return all external signals currently held by the engine."""
        return {
            "external_tiktok_signals": self.external_tiktok_signals,
        }

    def get_shift_summary(self) -> str:
        """Natural-language summary of detected external trend shifts."""
        signals = self.external_tiktok_signals
        if not signals.get("extracted_items"):
            return ""
        return signals.get("insight_summary", "")
