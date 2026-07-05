"""Historical database provider — reads prior CreatorRadar trend data (priority 9)."""

from __future__ import annotations

import logging
import os
from typing import Any

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


class HistoricalProvider(TrendProvider):
    name = "historical"
    display_name = "CreatorRadar History"
    priority = 9
    source_key = "historical"

    def is_available(self) -> bool:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
        return bool(url and key)

    def _query_table(self, table: str, select: str, order: str, limit: int = 50) -> list[dict]:
        try:
            from trend_intelligence_engine.historical_store import query_supabase_table

            return query_supabase_table(table, select=select, order=order, limit=limit)
        except Exception as exc:
            logger.warning("Historical query %s failed: %s", table, exc)
            self._last_warning = str(exc)
            return []

    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        results: list[NormalizedTrendResult] = []
        feed_table = os.getenv("SUPABASE_FEED_TABLE", "trend_intelligence_feed")
        history_table = os.getenv("TREND_HISTORY_TABLE", "trend_intelligence_history")

        for table, source_label in ((history_table, "history"), (feed_table, "feed")):
            rows = self._query_table(
                table,
                select="keyword,trend,source,popularity,buying_intent,competition,category,sentiment,summary,signal_strength,virality_score,created_at,raw_data",
                order="created_at.desc",
                limit=40,
            )
            for row in rows:
                keyword = row.get("keyword") or row.get("summary") or row.get("trend") or ""
                if not keyword:
                    raw = row.get("raw_data") or {}
                    keyword = raw.get("keyword") or raw.get("content_key") or ""
                if not keyword:
                    continue
                niche_l = (niche or "").lower()
                if niche_l and niche_l != "general":
                    if niche_l not in keyword.lower() and niche_l not in str(row.get("trend", "")).lower():
                        continue
                raw = dict(row.get("raw_data") or {})
                raw.update(
                    {
                        "signal_strength": row.get("signal_strength") or row.get("popularity"),
                        "viral_score": row.get("virality_score") or row.get("popularity"),
                        "historical_source": source_label,
                    }
                )
                results.append(
                    self.normalize_item(
                        trend=row.get("trend") or keyword,
                        keyword=str(keyword)[:120],
                        niche=niche,
                        raw=raw,
                        signal_type="historical",
                    )
                )
        return results[:30]

    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        return []
