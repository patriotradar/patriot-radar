"""Reddit discussions provider (priority 3)."""

from __future__ import annotations

import logging
from typing import Any

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


class RedditProvider(TrendProvider):
    name = "reddit"
    display_name = "Reddit"
    priority = 3
    source_key = "reddit"

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401
            from pytrends.request import TrendReq  # noqa: F401
            return True
        except ImportError:
            return False

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        return self.discover_emerging_topics(niche, config)

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        results: list[NormalizedTrendResult] = []
        try:
            from trends import scan_reddit

            discovered = scan_reddit()
            for item in discovered:
                keyword = item.get("keyword", "")
                if not keyword:
                    continue
                results.append(
                    self.normalize_item(
                        trend=keyword,
                        keyword=keyword,
                        niche=niche,
                        raw=item,
                        signal_type="reddit_discussion",
                    )
                )
        except Exception as exc:
            logger.warning("Reddit provider failed: %s", exc)
            self._last_warning = str(exc)
        return results
