"""News and UK media RSS provider (priority 5)."""

from __future__ import annotations

import logging
from typing import Any

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


class NewsProvider(TrendProvider):
    name = "news"
    display_name = "News Sources"
    priority = 5
    source_key = "news"

    def is_available(self) -> bool:
        return True

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        return self.discover_emerging_topics(niche, config)

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        config = config or {}
        if config.get("fast_mode"):
            return []
        results: list[NormalizedTrendResult] = []
        try:
            from trends import scan_uk_news, scan_twitter_trends

            news = scan_uk_news()
            twitter = scan_twitter_trends()
            for item in news + twitter:
                keyword = item.get("keyword", "")
                if not keyword:
                    continue
                results.append(
                    self.normalize_item(
                        trend=keyword,
                        keyword=keyword,
                        niche=niche,
                        raw=item,
                        signal_type=item.get("discovery_type", "news"),
                    )
                )
        except Exception as exc:
            logger.warning("News provider failed: %s", exc)
            self._last_warning = str(exc)
        return results
