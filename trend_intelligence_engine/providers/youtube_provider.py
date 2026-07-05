"""YouTube search suggestions provider (priority 4)."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)

YOUTUBE_SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}


class YouTubeProvider(TrendProvider):
    name = "youtube"
    display_name = "YouTube Search"
    priority = 4
    source_key = "youtube"

    def is_available(self) -> bool:
        return True

    def _fetch_suggestions(self, query: str) -> list[str]:
        try:
            resp = requests.get(
                YOUTUBE_SUGGEST_URL,
                params={"client": "youtube", "q": query, "hl": "en", "gl": "GB"},
                headers=HEADERS,
                timeout=8,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                return []
            suggestions = []
            for entry in data[1]:
                if isinstance(entry, list) and entry:
                    suggestions.append(str(entry[0]))
                elif isinstance(entry, str):
                    suggestions.append(entry)
            return suggestions[:10]
        except Exception as exc:
            logger.debug("YouTube suggest failed for %s: %s", query, exc)
            return []

    def _seeds(self, niche: str) -> list[str]:
        niche = (niche or "general").strip()
        return [
            niche,
            f"{niche} uk",
            f"best {niche}",
            f"{niche} review",
            f"how to {niche}",
            f"{niche} tutorial",
        ]

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        results: list[NormalizedTrendResult] = []
        seen: set[str] = set()
        for seed in self._seeds(niche):
            for suggestion in self._fetch_suggestions(seed):
                key = suggestion.lower().strip()
                if not key or key in seen or len(key) < 4:
                    continue
                seen.add(key)
                raw = {"discovery_type": "youtube_suggest", "seed": seed}
                results.append(
                    self.normalize_item(
                        trend=suggestion,
                        keyword=suggestion,
                        niche=niche,
                        raw=raw,
                        signal_type="youtube_search",
                    )
                )
        if not results:
            self._last_warning = "YouTube suggestions returned no results"
        return results[:25]

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        buying_seeds = [
            f"best {niche}",
            f"{niche} alternative",
            f"{niche} vs",
            f"is {niche} worth it",
            f"{niche} recommendation",
        ]
        results: list[NormalizedTrendResult] = []
        seen: set[str] = set()
        buying_pattern = re.compile(
            r"\b(best|review|alternative|vs|worth|recommend|buy|tried|looking for)\b",
            re.I,
        )
        for seed in buying_seeds:
            for suggestion in self._fetch_suggestions(seed):
                key = suggestion.lower().strip()
                if not key or key in seen:
                    continue
                if buying_pattern.search(suggestion):
                    seen.add(key)
                    results.append(
                        self.normalize_item(
                            trend=suggestion,
                            keyword=suggestion,
                            niche=niche,
                            raw={"discovery_type": "youtube_buying_intent", "seed": seed},
                            signal_type="buying_intent",
                        )
                    )
        return results[:15]
