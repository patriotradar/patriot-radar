"""Public social platforms — Twitter trends + autocomplete (priority 8)."""

from __future__ import annotations

import logging
from typing import Any

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


class SocialProvider(TrendProvider):
    name = "social"
    display_name = "Social Platforms"
    priority = 8
    source_key = "social"

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401
            from pytrends.request import TrendReq  # noqa: F401
            return True
        except ImportError:
            return False

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        config = config or {}
        if config.get("fast_mode"):
            return self._fast_social_scan(niche)
        results: list[NormalizedTrendResult] = []
        try:
            from trends import scan_twitter_trends, scan_autocomplete

            twitter = scan_twitter_trends()
            autocomplete, _insights = scan_autocomplete()
            for item in twitter + autocomplete[:10]:
                keyword = item.get("keyword", "")
                if not keyword:
                    continue
                results.append(
                    self.normalize_item(
                        trend=keyword,
                        keyword=keyword,
                        niche=niche,
                        raw=item,
                        signal_type="social_trend",
                    )
                )
        except Exception as exc:
            logger.warning("Social provider failed: %s", exc)
            self._last_warning = str(exc)
        return results[:20]

    def _fast_social_scan(self, niche: str) -> list[NormalizedTrendResult]:
        results: list[NormalizedTrendResult] = []
        try:
            from trends import scan_twitter_trends

            for item in scan_twitter_trends():
                keyword = item.get("keyword", "")
                if keyword:
                    results.append(
                        self.normalize_item(
                            trend=keyword,
                            keyword=keyword,
                            niche=niche,
                            raw=item,
                            signal_type="social_trend",
                        )
                    )
        except Exception as exc:
            self._last_warning = str(exc)
        return results[:10]

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        return []
