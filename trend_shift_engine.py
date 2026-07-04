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
from keyword_diversity import fetch_historical_keyword_roots
from tiktok_pipeline_hardening import compute_trend_scores, validate_videos
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
    historical_keywords: set[str] | None = None,
) -> dict[str, Any]:
    """
    Run TikTok trend extraction and return read-only external signals.

    Safe to call with None or empty input — always returns a structured object.
    """
    try:
        if not tiktok_inputs:
            return dict(_EMPTY_TIKTOK_SIGNALS)
        return extract_tiktok_trend_signals(tiktok_inputs, historical_keywords=historical_keywords)
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
        historical_keywords: set[str] | None = None,
    ) -> dict[str, Any]:
        """Ingest TikTok content and store as external_tiktok_signals."""
        self.external_tiktok_signals = ingest_external_tiktok_signals(
            tiktok_inputs,
            historical_keywords=historical_keywords,
        )
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
    historical_keywords: set[str] | None = None,
) -> tuple[list[str | dict[str, Any]], dict[str, Any]]:
    """
    Resolve TikTok scan inputs: explicit inputs > Apify fetch > sample file.

    Returns (inputs, apify_fetch_result).
    """
    historical = historical_keywords if historical_keywords is not None else fetch_historical_keyword_roots()

    if tiktok_inputs:
        logger.info("Using %d explicit TikTok input(s) (Apify skipped).", len(tiktok_inputs))
        return tiktok_inputs, {"success": False, "skipped": True, "reason": "explicit_inputs_provided", "data_source": "explicit"}

    apify_result: dict[str, Any] = {"success": False, "items": [], "item_count": 0, "error": None}
    if use_apify:
        apify_result = fetch_tiktok_via_apify(historical_keywords=historical)
        if apify_result.get("success") and apify_result.get("items"):
            items = apify_result["items"]
            logger.info("Using %d TikTok item(s) from Apify.", len(items))
            apify_result["data_source"] = "apify"
            return items, apify_result

        if apify_result.get("token_present"):
            logger.error(
                "Apify fetch failed with APIFY_API_TOKEN configured (error=%s). "
                "Refusing sample-data fallback — fix Apify integration or token.",
                apify_result.get("error"),
            )
            apify_result["data_source"] = "apify_failed"
            apify_result["fallback_refused"] = True
            return [], apify_result

        logger.warning(
            "APIFY_API_TOKEN not configured; falling back to sample inputs."
        )

    sample_inputs = _load_sample_inputs(sample_inputs_path)
    logger.info("Using %d sample TikTok input(s) from fallback.", len(sample_inputs))
    apify_result["data_source"] = "sample_fallback"
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
        historical = fetch_historical_keyword_roots()
        logger.info("Keyword dedup: %d historical roots loaded.", len(historical))

        inputs, apify_result = _resolve_scan_inputs(
            tiktok_inputs=tiktok_inputs,
            sample_inputs_path=sample_inputs_path,
            use_apify=use_apify,
            historical_keywords=historical,
        )

        data_source = apify_result.get("data_source", "explicit" if tiktok_inputs else "unknown")
        if apify_result.get("fallback_refused"):
            return {
                "success": False,
                "signals": dict(_EMPTY_TIKTOK_SIGNALS),
                "store_result": {"stored": 0, "skipped": 0, "error": apify_result.get("error") or "apify_fetch_failed"},
                "item_count": 0,
                "apify_fetch": apify_result,
                "data_source": data_source,
                "insight_summary": "",
            }

        if not inputs:
            logger.error("No TikTok inputs available after resolution step.")
            return {
                "success": False,
                "signals": dict(_EMPTY_TIKTOK_SIGNALS),
                "store_result": {"stored": 0, "skipped": 0, "error": "no_inputs"},
                "item_count": 0,
                "apify_fetch": apify_result,
                "data_source": data_source,
                "insight_summary": "",
            }

        engine = TrendShiftEngine()
        signals = engine.load_tiktok_signals(inputs, historical_keywords=historical)

        store_result = {"stored": 0, "skipped": 0, "error": None}
        extracted_count = len(signals.get("extracted_items") or [])
        extracted_items = signals.get("extracted_items") or []
        virality_scores = [
            (item.get("virality") or {}).get("virality_score", 0)
            for item in extracted_items
        ]
        avg_virality = (
            round(sum(virality_scores) / len(virality_scores), 1)
            if virality_scores else 0
        )

        trend_scores = [
            item.get("trend_score")
            for item in extracted_items
            if item.get("trend_score")
        ]
        if not trend_scores:
            try:
                gate = validate_videos(inputs if all(isinstance(i, dict) for i in inputs) else [])
                trend_scores = compute_trend_scores(gate.get("accepted") or [])
            except Exception:
                trend_scores = []

        logger.info(
            "Extraction complete: source=%s input_count=%d extracted=%d avg_virality=%.1f",
            data_source,
            len(inputs),
            extracted_count,
            avg_virality,
        )

        if persist and extracted_count:
            store_result = engine.store_external_tiktok_signals(signals)
            probe = store_result.get("table_probe") or {}
            logger.info(
                "Supabase upsert complete: stored=%d skipped=%d error=%s feed_row_count=%s",
                store_result.get("stored", 0),
                store_result.get("skipped", 0),
                store_result.get("error"),
                probe.get("row_count"),
            )
            if store_result.get("stored", 0) == 0 and not store_result.get("error"):
                store_result["error"] = "zero_rows_stored"
                logger.error("Supabase upsert stored 0 rows despite %d extracted items.", extracted_count)
        elif persist and not extracted_count:
            logger.warning("No extracted items to persist to trend_intelligence_feed.")

        return {
            "success": True,
            "signals": signals,
            "store_result": store_result,
            "item_count": extracted_count,
            "apify_fetch": apify_result,
            "data_source": data_source,
            "avg_virality_score": avg_virality,
            "insight_summary": signals.get("insight_summary", ""),
            "trend_scores": trend_scores,
            "videos": [],
            "insights": [],
            "recommended_posts": [],
            "errors": [],
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
