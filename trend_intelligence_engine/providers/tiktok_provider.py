"""TikTok trend provider via Apify (priority 1)."""

from __future__ import annotations

import logging
import os
from typing import Any

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


class TikTokApifyProvider(TrendProvider):
    name = "tiktok_apify"
    display_name = "TikTok (Apify)"
    priority = 1
    source_key = "tiktok"

    def is_available(self) -> bool:
        token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
        if token:
            return True
        try:
            from trend_shift_engine import _DEFAULT_SAMPLE_INPUTS

            return _DEFAULT_SAMPLE_INPUTS.exists()
        except Exception:
            return False

    def _fetch_and_extract(self, niche: str, config: dict[str, Any]) -> list[dict[str, Any]]:
        from apify_tiktok_fetcher import fetch_tiktok_via_apify
        from tiktok_trend_extractor import extract_tiktok_trend_signals

        apify_result = fetch_tiktok_via_apify()
        if not apify_result.get("success"):
            self._last_warning = apify_result.get("error") or "Apify TikTok fetch failed"
            if not self.is_available():
                sample_path = config.get("sample_inputs_path")
                from trend_shift_engine import _load_sample_inputs

                inputs = _load_sample_inputs(sample_path)
                batch = extract_tiktok_trend_signals(inputs)
                return batch.get("extracted_items") or []
            return []

        items = apify_result.get("items") or []
        if not items:
            self._last_warning = "Apify returned zero TikTok items"
            return []

        batch = extract_tiktok_trend_signals(items)
        return batch.get("extracted_items") or []

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        config = config or {}
        items = self._fetch_and_extract(niche, config)
        results: list[NormalizedTrendResult] = []
        for item in items:
            topics = item.get("topics") or {}
            primary = topics.get("primary_topic") or item.get("caption_preview", "")[:60]
            hook = item.get("hook") or {}
            keyword = hook.get("hook_text") or primary or item.get("caption_preview", "")[:80]
            if not keyword:
                continue
            virality = item.get("virality") or {}
            raw = {
                **item,
                "signal_strength": int(float(virality.get("viral_strength_score", 0) or 0) * 100),
                "viral_score": float(virality.get("viral_strength_score", 0) or 0) * 100,
            }
            results.append(
                self.normalize_item(
                    trend=primary or keyword,
                    keyword=str(keyword)[:120],
                    niche=niche,
                    raw=raw,
                    signal_type="tiktok_video",
                    related_creators=[item.get("author", "")] if item.get("author") else [],
                )
            )
        return results

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        config = config or {}
        items = self._fetch_and_extract(niche, config)
        topic_counts: dict[str, int] = {}
        for item in items:
            topics = item.get("topics") or {}
            primary = topics.get("primary_topic")
            if primary:
                topic_counts[primary] = topic_counts.get(primary, 0) + 1
            for sec in topics.get("secondary_topics") or []:
                topic_counts[sec] = topic_counts.get(sec, 0) + 1

        emerging: list[NormalizedTrendResult] = []
        for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1])[:15]:
            raw = {"topic_count": count, "discovery_type": "tiktok_emerging"}
            emerging.append(
                self.normalize_item(
                    trend=topic,
                    keyword=topic,
                    niche=niche,
                    raw=raw,
                    signal_type="emerging_topic",
                )
            )
        return emerging
