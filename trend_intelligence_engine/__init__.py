"""
Multi-source Trend Intelligence Engine for CreatorRadar.

Aggregates signals from TikTok, Google Trends, Reddit, YouTube, news, blogs,
forums, social platforms, and historical database. Never fails when a single
provider is unavailable.
"""

from trend_intelligence_engine.engine import TrendIntelligenceEngine, run_trend_intelligence_scan
from trend_intelligence_engine.types import NormalizedTrendResult, ProviderScanResult, ScanReport

__all__ = [
    "TrendIntelligenceEngine",
    "run_trend_intelligence_scan",
    "NormalizedTrendResult",
    "ProviderScanResult",
    "ScanReport",
]
