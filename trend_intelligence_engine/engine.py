"""Multi-source Trend Intelligence Engine orchestrator."""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from trend_intelligence_engine.buying_intent import merge_cross_platform, rank_opportunities
from trend_intelligence_engine.content_intelligence import enrich_all
from trend_intelligence_engine.historical_store import (
    fetch_latest_recommendations,
    fetch_latest_scan,
    normalized_to_feed_rows,
    store_history_rows,
    store_recommendations,
    store_scan_metadata,
)
from trend_intelligence_engine.providers import get_all_providers
from trend_intelligence_engine.recommendations import build_recommendations
from trend_intelligence_engine.types import NormalizedTrendResult, ProviderScanResult, ScanReport, utc_now_iso

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "trend_intelligence_cache.json"
DEFAULT_PROVIDER_TIMEOUT_SEC = int(os.getenv("TREND_PROVIDER_TIMEOUT_SEC", "30"))
FAST_PROVIDER_TIMEOUT_SEC = int(os.getenv("TREND_FAST_PROVIDER_TIMEOUT_SEC", "15"))


def _dedupe_results(results: list[NormalizedTrendResult]) -> list[NormalizedTrendResult]:
    """Post-processing dedupe by keyword/dedupe_key without changing provider output."""
    seen: set[str] = set()
    unique: list[NormalizedTrendResult] = []
    for item in results:
        key = (item.dedupe_key or item.keyword or item.trend or "").strip().lower()[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _scan_provider_with_timeout(provider, niche: str, config: dict[str, Any], timeout_sec: int):
    """Run provider.scan with a hard timeout."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(provider.scan, niche, config)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeoutError:
            return ProviderScanResult(
                provider=provider.name,
                success=False,
                online=provider.is_available(),
                warning=f"{provider.display_name} timed out after {timeout_sec}s",
                error="provider_timeout",
            )


class TrendIntelligenceEngine:
    """
    Orchestrates all trend providers in priority order.
    Continues when individual providers fail; never raises from scan().
    """

    def __init__(self, providers=None) -> None:
        self.providers = providers if providers is not None else get_all_providers()
        self.last_report: ScanReport | None = None

    def provider_status(self) -> dict[str, Any]:
        """Return online/offline status for each provider without scanning."""
        online = []
        offline = []
        for provider in self.providers:
            entry = {
                "name": provider.name,
                "display_name": provider.display_name,
                "priority": provider.priority,
                "source_key": provider.source_key,
                "available": provider.is_available(),
            }
            if provider.is_available():
                online.append(entry)
            else:
                offline.append(entry)
        return {
            "providers_online": [p["name"] for p in online],
            "providers_offline": [p["name"] for p in offline],
            "online": online,
            "offline": offline,
            "timestamp": utc_now_iso(),
        }

    def scan(
        self,
        niche: str = "general",
        *,
        config: dict[str, Any] | None = None,
        persist: bool = True,
        store_feed: bool = True,
    ) -> ScanReport:
        """
        Run all providers, merge results, score opportunities, generate recommendations.
        """
        config = config or {}
        niche = (niche or "general").strip() or "general"
        if "fast_mode" not in config:
            config["fast_mode"] = os.getenv("TREND_INTELLIGENCE_FAST_MODE", "").lower() in (
                "1",
                "true",
                "yes",
            )
        report = ScanReport(niche=niche, timestamp=utc_now_iso())

        all_results: list[NormalizedTrendResult] = []
        timeout_sec = int(
            config.get(
                "provider_timeout_sec",
                FAST_PROVIDER_TIMEOUT_SEC if config.get("fast_mode") else DEFAULT_PROVIDER_TIMEOUT_SEC,
            )
        )
        for provider in self.providers:
            result: ProviderScanResult = _scan_provider_with_timeout(
                provider, niche, config, timeout_sec
            )
            report.provider_results.append(result)

            if result.online and result.success:
                all_results.extend(result.results)

            if result.online and result.success and result.item_count > 0:
                report.providers_online.append(provider.name)
            elif result.online:
                report.providers_offline.append(provider.name)
            else:
                report.providers_offline.append(provider.name)

            if result.warning:
                report.warnings.append(f"{provider.display_name}: {result.warning}")
            if result.error:
                report.warnings.append(f"{provider.display_name} error: {result.error}")

        merged = merge_cross_platform(all_results)
        enriched = _dedupe_results(enrich_all(merged))
        opportunities = [r for r in rank_opportunities(enriched) if r.opportunity.opportunity_score >= 35]
        trends = enriched[:50]

        report.trends = trends
        report.opportunities = opportunities[:30]
        report.recommendations = build_recommendations(trends, opportunities, niche=niche)

        if persist:
            report.stored = self._persist(report, store_feed=store_feed)

        self._write_cache(report)
        self.last_report = report
        return report

    def _persist(self, report: ScanReport, *, store_feed: bool) -> dict[str, Any]:
        stored: dict[str, Any] = {}

        history_result = store_history_rows(report.trends + report.opportunities)
        stored["history"] = history_result

        scan_result = store_scan_metadata(
            niche=report.niche,
            providers_online=report.providers_online,
            providers_offline=report.providers_offline,
            trend_count=len(report.trends),
            opportunity_count=len(report.opportunities),
            warnings=report.warnings,
        )
        stored["scan"] = scan_result

        rec_result = store_recommendations(report.recommendations, report.niche)
        stored["recommendations"] = rec_result

        if store_feed:
            try:
                from trend_intelligence_store import store_trend_intelligence_rows

                feed_rows = normalized_to_feed_rows(report.trends + report.opportunities)
                stored["feed"] = store_trend_intelligence_rows(feed_rows)
            except Exception as exc:
                logger.warning("Feed store failed: %s", exc)
                stored["feed"] = {"stored": 0, "error": str(exc)}

        return stored

    def _write_cache(self, report: ScanReport) -> None:
        """Local JSON cache for API fallback when Supabase unavailable."""
        try:
            payload = {
                "timestamp": report.timestamp,
                "niche": report.niche,
                "providers_online": report.providers_online,
                "providers_offline": report.providers_offline,
                "warnings": report.warnings,
                "trend_count": len(report.trends),
                "opportunity_count": len(report.opportunities),
                "trends": [t.to_dict() for t in report.trends[:30]],
                "opportunities": [o.to_dict() for o in report.opportunities[:20]],
                "recommendations": report.recommendations,
            }
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            logger.warning("Cache write failed: %s", exc)

    @staticmethod
    def load_cache() -> dict[str, Any] | None:
        try:
            if CACHE_PATH.exists():
                with open(CACHE_PATH, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    @staticmethod
    def load_status() -> dict[str, Any]:
        """Load combined status from Supabase + local cache."""
        status: dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "providers_online": [],
            "providers_offline": [],
            "last_scan_time": None,
            "health_status": "unknown",
            "warnings": [],
        }

        engine = TrendIntelligenceEngine()
        provider_status = engine.provider_status()
        status["providers_online"] = provider_status["providers_online"]
        status["providers_offline"] = provider_status["providers_offline"]
        status["provider_details"] = provider_status

        latest_scan = fetch_latest_scan()
        if latest_scan:
            status["last_scan_time"] = latest_scan.get("scanned_at")
            status["providers_online"] = latest_scan.get("providers_online") or status["providers_online"]
            status["providers_offline"] = latest_scan.get("providers_offline") or status["providers_offline"]
            status["health_status"] = latest_scan.get("health_status", "healthy")
            status["warnings"] = latest_scan.get("warnings") or []
            status["trend_count"] = latest_scan.get("trend_count", 0)
            status["opportunity_count"] = latest_scan.get("opportunity_count", 0)
        else:
            cache = TrendIntelligenceEngine.load_cache()
            if cache:
                status["last_scan_time"] = cache.get("timestamp")
                status["providers_online"] = cache.get("providers_online", [])
                status["providers_offline"] = cache.get("providers_offline", [])
                status["health_status"] = "degraded" if cache.get("providers_offline") else "healthy"
                status["warnings"] = cache.get("warnings", [])
                status["from_cache"] = True

        if status["providers_online"] and not status["providers_offline"]:
            status["health_status"] = "healthy"
        elif status["providers_online"]:
            status["health_status"] = "degraded"
        elif not status["providers_online"]:
            status["health_status"] = "offline"

        rec = fetch_latest_recommendations()
        if rec:
            status["latest_recommendations"] = rec.get("recommendations")

        return status


def run_trend_intelligence_scan(
    niche: str = "general",
    *,
    persist: bool = True,
    store_feed: bool = True,
) -> dict[str, Any]:
    """CLI/CI entry point. Returns JSON-serializable report."""
    try:
        engine = TrendIntelligenceEngine()
        report = engine.scan(niche=niche, persist=persist, store_feed=store_feed)
        return report.to_dict()
    except Exception as exc:
        logger.exception("run_trend_intelligence_scan failed: %s", exc)
        return ScanReport(
            niche=niche or "general",
            warnings=[f"Scan failed: {exc}"],
        ).to_dict()
