"""
Trend shift detection engine — read-only external signal aggregation.

Consumes external platform signals (e.g. TikTok) for early pattern detection.
Does NOT feed into scoring, final_recommendation_selector, calibration, or captions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apify_tiktok_fetcher import fetch_tiktok_via_apify
from tiktok_trend_extractor import extract_tiktok_trend_signals
from trend_intelligence_store import store_external_tiktok_signals

logger = logging.getLogger(__name__)

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


def _resolve_scan_inputs(
    tiktok_inputs: list[str | dict[str, Any]] | None = None,
    sample_inputs_path: str | Path | None = None,
    use_apify: bool = True,
) -> tuple[list[str | dict[str, Any]], dict[str, Any]]:
    """
    Resolve TikTok scan inputs: explicit inputs > Apify fetch > sample file.

    Returns (inputs, apify_fetch_result).
    """
    if tiktok_inputs:
        logger.info("Using %d explicit TikTok input(s) (Apify skipped).", len(tiktok_inputs))
        return tiktok_inputs, {"success": False, "skipped": True, "reason": "explicit_inputs_provided"}

    apify_result: dict[str, Any] = {"success": False, "items": [], "item_count": 0, "error": None}
    if use_apify:
        apify_result = fetch_tiktok_via_apify()
        if apify_result.get("success") and apify_result.get("items"):
            items = apify_result["items"]
            logger.info("Using %d TikTok item(s) from Apify.", len(items))
            return items, apify_result

        if apify_result.get("token_present"):
            logger.warning(
                "Apify fetch did not return usable items (error=%s); falling back to sample inputs.",
                apify_result.get("error"),
            )
        else:
            logger.warning(
                "APIFY_API_TOKEN not configured; falling back to sample inputs."
            )

    sample_inputs = _load_sample_inputs(sample_inputs_path)
    logger.info("Using %d sample TikTok input(s) from fallback.", len(sample_inputs))
    return sample_inputs, apify_result


def run_tiktok_trend_scan(
    tiktok_inputs: list[str | dict[str, Any]] | None = None,
    sample_inputs_path: str | Path | None = None,
    persist: bool = True,
    use_apify: bool = True,
) -> dict[str, Any]:
    """
    Admin/testing entry point: extract TikTok signals and optionally persist.

    Fetches live TikTok data via Apify when APIFY_API_TOKEN is set, otherwise
    uses explicit inputs or sample captions. Never raises.
    """
    try:
        inputs, apify_result = _resolve_scan_inputs(
            tiktok_inputs=tiktok_inputs,
            sample_inputs_path=sample_inputs_path,
            use_apify=use_apify,
        )

        engine = TrendShiftEngine()
        signals = engine.load_tiktok_signals(inputs)

        store_result = {"stored": 0, "skipped": 0, "error": None}
        extracted_count = len(signals.get("extracted_items") or [])
        if persist and extracted_count:
            store_result = engine.store_external_tiktok_signals(signals)
            logger.info(
                "Supabase upsert complete: stored=%d skipped=%d error=%s",
                store_result.get("stored", 0),
                store_result.get("skipped", 0),
                store_result.get("error"),
            )
        elif persist and not extracted_count:
            logger.warning("No extracted items to persist to trend_intelligence_feed.")

        return {
            "success": True,
            "signals": signals,
            "store_result": store_result,
            "item_count": extracted_count,
            "apify_fetch": apify_result,
            "insight_summary": signals.get("insight_summary", ""),
        }
    except Exception as exc:
        logger.exception("TikTok trend scan failed: %s", exc)
        return {
            "success": False,
            "signals": dict(_EMPTY_TIKTOK_SIGNALS),
            "store_result": {"stored": 0, "skipped": 0, "error": str(exc)},
            "item_count": 0,
            "apify_fetch": {"success": False, "error": str(exc)},
            "insight_summary": "",
        }
