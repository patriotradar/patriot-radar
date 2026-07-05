"""Public forums provider — Reddit-adjacent + autocomplete forum queries (priority 7)."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)

FORUM_FEEDS = [
    ("https://www.reddit.com/r/AskUK/hot/.rss?limit=15", "AskUK"),
    ("https://www.reddit.com/r/BritishMilitary/hot/.rss?limit=15", "BritishMilitary"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


class ForumProvider(TrendProvider):
    name = "forums"
    display_name = "Public Forums"
    priority = 7
    source_key = "forums"

    def is_available(self) -> bool:
        return True

    def _parse_rss_titles(self, url: str, source: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return items
            titles = re.findall(r"<title>([^<]+)</title>", resp.text)
            for title_raw in titles[1:12]:
                title = re.sub(r"&amp;|&#\d+;", " ", title_raw).strip()
                if len(title) < 12:
                    continue
                items.append(
                    {
                        "keyword": title[:80],
                        "source_keyword": source,
                        "rise_value": 150,
                        "discovery_type": "forum",
                    }
                )
        except Exception as exc:
            logger.debug("Forum RSS %s failed: %s", url, exc)
        return items

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        return self.discover_emerging_topics(niche, config)

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        results: list[NormalizedTrendResult] = []
        seen: set[str] = set()
        for url, source in FORUM_FEEDS:
            for item in self._parse_rss_titles(url, source):
                keyword = item.get("keyword", "")
                key = keyword.lower()[:60]
                if not keyword or key in seen:
                    continue
                seen.add(key)
                results.append(
                    self.normalize_item(
                        trend=keyword,
                        keyword=keyword,
                        niche=niche,
                        raw=item,
                        signal_type="forum_discussion",
                    )
                )
        if not results:
            self._last_warning = "Forum feeds returned no discussions"
        return results[:15]
