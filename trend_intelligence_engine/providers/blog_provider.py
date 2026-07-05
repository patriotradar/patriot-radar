"""Blogs and niche websites via Google autocomplete (priority 6)."""

from __future__ import annotations

import logging
from typing import Any

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


class BlogProvider(TrendProvider):
    name = "blogs"
    display_name = "Blogs & Niche Sites"
    priority = 6
    source_key = "blogs"

    def is_available(self) -> bool:
        return True

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        config = config or {}
        if config.get("fast_mode"):
            return []
        results: list[NormalizedTrendResult] = []
        try:
            discovered, creator_insights = self._scan_autocomplete()
            for item in discovered:
                keyword = item.get("keyword", "")
                if not keyword:
                    continue
                results.append(
                    self.normalize_item(
                        trend=keyword,
                        keyword=keyword,
                        niche=niche,
                        raw={**item, "discovery_type": "blog_autocomplete"},
                        signal_type="blog_signal",
                    )
                )
            for insight in creator_insights or []:
                topic = insight.get("topic") or insight.get("keyword") or ""
                if topic:
                    results.append(
                        self.normalize_item(
                            trend=topic,
                            keyword=topic,
                            niche=niche,
                            raw={**insight, "discovery_type": "creator_insight"},
                            signal_type="creator_insight",
                            related_creators=[insight.get("creator", "")] if insight.get("creator") else [],
                        )
                    )
        except Exception as exc:
            logger.warning("Blog provider failed: %s", exc)
            self._last_warning = str(exc)
        return results[:20]

    def _scan_autocomplete(self):
        from trends import scan_autocomplete

        return scan_autocomplete()

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        return []
