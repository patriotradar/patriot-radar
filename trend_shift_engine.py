"""
Trend shift detection engine — read-only external signal aggregation.

Consumes external platform signals (e.g. TikTok) for early pattern detection.
Does NOT feed into scoring, final_recommendation_selector, calibration, or captions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tiktok_trend_extractor import extract_tiktok_trend_signals
from trend_intelligence_store import store_external_tiktok_signals

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

_DEFAULT_SAMPLE_INPUTS = Path(__file__).resolve().parent / "data" / "tiktok_sample_inputs.json"


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


def _load_sample_inputs(path: str | Path | None = None) -> list[str | dict[str, Any]]:
    sample_path = Path(path) if path else _DEFAULT_SAMPLE_INPUTS
    try:
        if sample_path.exists():
            with open(sample_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return [
        "Nobody is talking about British pride on TikTok right now.",
        "Is it just me or is patriotism becoming acceptable again? Yes or No?",
    ]


class TrendShiftEngine:
    """
    Aggregates external trend signals for shift detection.

    Output is observational only — it must not influence recommendation
    selection or internal scoring pipelines.
    """

    def __init__(self) -> None:
        self.external_tiktok_signals: dict[str, Any] = dict(_EMPTY_TIKTOK_SIGNALS)
        self.last_store_result: dict[str, Any] = {"stored": 0, "skipped": 0, "error": None}

    def load_tiktok_signals(
        self,
        tiktok_inputs: list[str | dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ingest TikTok content and store as external_tiktok_signals."""
        self.external_tiktok_signals = ingest_external_tiktok_signals(tiktok_inputs)
        return self.external_tiktok_signals

    def store_external_tiktok_signals(
        self,
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Persist external TikTok signals to trend_intelligence_feed.

        Uses current signals when none are passed. Idempotent per video/url.
        """
        try:
            payload = signals if signals is not None else self.external_tiktok_signals
            self.last_store_result = store_external_tiktok_signals(payload)
            return self.last_store_result
        except Exception as exc:
            self.last_store_result = {"stored": 0, "skipped": 0, "error": str(exc)}
            return self.last_store_result

    def get_external_signals(self) -> dict[str, Any]:
        """Return all external signals currently held by the engine."""
        return {
            "external_tiktok_signals": self.external_tiktok_signals,
            "last_store_result": self.last_store_result,
        }

    def get_shift_summary(self) -> str:
        """Natural-language summary of detected external trend shifts."""
        signals = self.external_tiktok_signals
        if not signals.get("extracted_items"):
            return ""
        return signals.get("insight_summary", "")


def run_tiktok_trend_scan(
    tiktok_inputs: list[str | dict[str, Any]] | None = None,
    sample_inputs_path: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Admin/testing entry point: extract TikTok signals and optionally persist.

    Uses sample URLs/captions when no inputs are provided. Never raises.
  """
    try:
        inputs = tiktok_inputs
        if not inputs:
            inputs = _load_sample_inputs(sample_inputs_path)

        engine = TrendShiftEngine()
        signals = engine.load_tiktok_signals(inputs)

        store_result = {"stored": 0, "skipped": 0, "error": None}
        if persist and signals.get("extracted_items"):
            store_result = engine.store_external_tiktok_signals(signals)

        return {
            "success": True,
            "signals": signals,
            "store_result": store_result,
            "item_count": len(signals.get("extracted_items") or []),
            "insight_summary": signals.get("insight_summary", ""),
        }
    except Exception as exc:
        return {
            "success": False,
            "signals": dict(_EMPTY_TIKTOK_SIGNALS),
            "store_result": {"stored": 0, "skipped": 0, "error": str(exc)},
            "item_count": 0,
            "insight_summary": "",
        }
