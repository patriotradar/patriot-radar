"""Base trend provider interface."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from trend_intelligence_engine.types import NormalizedTrendResult, ProviderScanResult, utc_now_iso

logger = logging.getLogger(__name__)


class TrendProvider(ABC):
    """
    Unified interface for all trend intelligence providers.

    Each provider must implement search, discovery, keyword extraction,
    popularity estimation, commercial intent estimation, and normalized output.
    """

    name: str = "base"
    display_name: str = "Base Provider"
    priority: int = 99
    source_key: str = "base"

    def __init__(self) -> None:
        self._last_warning: str | None = None
        self._last_error: str | None = None

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if provider can attempt a scan (credentials, deps, etc.)."""

    @abstractmethod
    def search_niche(self, niche: str, config: dict[str, Any] | None = None) -> list[NormalizedTrendResult]:
        """Search niche-specific trends."""

    @abstractmethod
    def discover_emerging_topics(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[NormalizedTrendResult]:
        """Discover emerging topics."""

    def extract_keywords(
        self, niche: str, config: dict[str, Any] | None = None
    ) -> list[str]:
        """Extract keywords from provider data."""
        results = self.search_niche(niche, config) + self.discover_emerging_topics(niche, config)
        keywords: list[str] = []
        seen: set[str] = set()
        for item in results:
            kw = (item.keyword or item.trend or "").strip().lower()
            if kw and kw not in seen:
                seen.add(kw)
                keywords.append(kw)
        return keywords

    def estimate_popularity(self, text: str, raw: dict[str, Any] | None = None) -> float:
        """Estimate popularity 0–100 from text and optional raw metadata."""
        raw = raw or {}
        if "viral_score" in raw:
            return float(min(100, max(0, raw["viral_score"])))
        if "rise_value" in raw:
            return float(min(100, max(0, raw["rise_value"] / 3)))
        if "rise_percent" in raw:
            return float(min(100, max(0, raw["rise_percent"])))
        if "signal_strength" in raw:
            return float(min(100, max(0, raw["signal_strength"])))
        return 40.0

    def estimate_commercial_intent(self, text: str) -> float:
        """Estimate commercial/buying intent 0–100."""
        from trend_intelligence_engine.buying_intent import estimate_buying_intent

        return estimate_buying_intent(text)

    def normalize_item(
        self,
        *,
        trend: str,
        keyword: str,
        niche: str,
        raw: dict[str, Any] | None = None,
        signal_type: str = "trend",
        related_creators: list[str] | None = None,
    ) -> NormalizedTrendResult:
        """Build a normalized result from provider-specific data."""
        raw = raw or {}
        text = f"{trend} {keyword}"
        popularity = self.estimate_popularity(text, raw)
        buying = self.estimate_commercial_intent(text)
        competition = float(raw.get("competition", raw.get("_tiktok_competition", 50)))
        dedupe = f"{self.source_key}:{keyword.lower()[:60]}:{signal_type}"

        return NormalizedTrendResult(
            trend=trend,
            keyword=keyword,
            source=self.source_key,
            timestamp=utc_now_iso(),
            popularity=popularity,
            buying_intent=buying,
            competition=competition,
            category=raw.get("category", "general"),
            sentiment=raw.get("sentiment", "neutral"),
            related_creators=related_creators or [],
            raw_data={**raw, "provider": self.name, "niche": niche},
            niche=niche,
            signal_type=signal_type,
            dedupe_key=dedupe,
        )

    def scan(self, niche: str, config: dict[str, Any] | None = None) -> ProviderScanResult:
        """
        Run full provider scan with fail-safe error handling.
        Never raises.
        """
        config = config or {}
        start = time.monotonic()
        self._last_warning = None
        self._last_error = None

        if not self.is_available():
            return ProviderScanResult(
                provider=self.name,
                success=False,
                online=False,
                warning=f"{self.display_name} unavailable (missing credentials or dependencies)",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        results: list[NormalizedTrendResult] = []
        try:
            search_results = self.search_niche(niche, config)
            emerging = self.discover_emerging_topics(niche, config)
            results = search_results + emerging

            # Deduplicate within provider
            seen: set[str] = set()
            unique: list[NormalizedTrendResult] = []
            for item in results:
                key = (item.dedupe_key or item.keyword or "").lower()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(item)
            results = unique

            duration = int((time.monotonic() - start) * 1000)
            warning = self._last_warning
            return ProviderScanResult(
                provider=self.name,
                success=True,
                online=True,
                results=results,
                warning=warning,
                duration_ms=duration,
                item_count=len(results),
            )
        except Exception as exc:
            logger.warning("Provider %s scan failed: %s", self.name, exc)
            self._last_error = str(exc)
            return ProviderScanResult(
                provider=self.name,
                success=False,
                online=True,
                error=str(exc),
                warning=f"{self.display_name} scan failed — continuing with other providers",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
