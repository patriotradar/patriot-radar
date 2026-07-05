"""Google Trends and autocomplete provider (priority 2)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


class GoogleTrendsProvider(TrendProvider):
    name = "google_trends"
    display_name = "Google Trends"
    priority = 2
    source_key = "google_trends"

    def is_available(self) -> bool:
        try:
            import pytrends  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_pytrends(self):
        from pytrends.request import TrendReq

        return TrendReq(hl="en-GB", tz=0)

    def _niche_seeds(self, niche: str) -> list[str]:
        niche_l = (niche or "general").lower()
        seeds = [niche, f"{niche} uk", f"british {niche}", f"{niche} 2026"]
        if "patriot" in niche_l or niche_l == "general":
            try:
                from trends import CONTENT_KEYWORDS

                seeds.extend(CONTENT_KEYWORDS[:8])
            except ImportError:
                seeds.extend(["british pride", "patriotism uk", "british army", "royal family"])
        return list(dict.fromkeys(s.strip() for s in seeds if s.strip()))[:12]

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        config = config or {}
        if config.get("fast_mode"):
            return []
        results: list[NormalizedTrendResult] = []
        try:
            from trends import analyse_keywords, PRODUCT_KEYWORDS

            pytrends = self._get_pytrends()
            seeds = self._niche_seeds(niche)
            content = analyse_keywords(pytrends, seeds[:10], "content")
            for item in content[:15]:
                keyword = item.get("keyword", "")
                if not keyword:
                    continue
                results.append(
                    self.normalize_item(
                        trend=keyword,
                        keyword=keyword,
                        niche=niche,
                        raw=item,
                        signal_type="google_trends",
                    )
                )
            if config.get("include_products", True):
                products = analyse_keywords(pytrends, PRODUCT_KEYWORDS[:5], "product")
                for item in products[:8]:
                    keyword = item.get("keyword", "")
                    if keyword:
                        results.append(
                            self.normalize_item(
                                trend=keyword,
                                keyword=keyword,
                                niche=niche,
                                raw={**item, "category": "product"},
                                signal_type="product_trend",
                            )
                        )
        except Exception as exc:
            logger.warning("Google Trends search_niche failed: %s", exc)
            self._last_warning = str(exc)
        return results

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        config = config or {}
        results: list[NormalizedTrendResult] = []
        fast_mode = bool(config.get("fast_mode"))
        try:
            from trends import (
                discover_related_keywords,
                discover_trending_searches,
                score_discovered_keyword,
            )

            pytrends = self._get_pytrends()
            seeds = self._niche_seeds(niche)

            if fast_mode:
                trending = discover_trending_searches(pytrends)
                discovered = trending
            else:
                related = discover_related_keywords(pytrends, seeds)
                trending = discover_trending_searches(pytrends)
                discovered = related + trending

            for item in discovered[:6 if fast_mode else 12]:
                keyword = item.get("keyword", "")
                if not keyword:
                    continue
                if not fast_mode:
                    try:
                        time.sleep(random.uniform(2, 5))
                        scores = score_discovered_keyword(pytrends, keyword)
                        if scores:
                            item = {**item, **scores}
                    except Exception:
                        pass
                results.append(
                    self.normalize_item(
                        trend=keyword,
                        keyword=keyword,
                        niche=niche,
                        raw=item,
                        signal_type="emerging_topic",
                    )
                )
        except Exception as exc:
            logger.warning("Google Trends discover failed: %s", exc)
            self._last_warning = str(exc)
        return results
