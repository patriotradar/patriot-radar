"""Normalized data types for the multi-source trend intelligence engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContentIntelligence:
    """Content recommendations derived from a trend signal."""

    content_angle: str = ""
    hook: str = ""
    target_audience: str = ""
    search_keywords: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    buying_signals: list[str] = field(default_factory=list)
    cta_suggestions: list[str] = field(default_factory=list)
    suggested_format: str = ""
    viral_potential_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_angle": self.content_angle,
            "hook": self.hook,
            "target_audience": self.target_audience,
            "search_keywords": self.search_keywords,
            "pain_points": self.pain_points,
            "questions": self.questions,
            "buying_signals": self.buying_signals,
            "cta_suggestions": self.cta_suggestions,
            "suggested_format": self.suggested_format,
            "viral_potential_score": self.viral_potential_score,
        }


@dataclass
class OpportunityScores:
    """Buying-intent opportunity breakdown (0–100 each)."""

    search_demand: int = 0
    buying_intent: int = 0
    competition: int = 0
    content_opportunity: int = 0
    affiliate_potential: int = 0
    product_potential: int = 0
    brand_opportunity: int = 0
    opportunity_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_demand": self.search_demand,
            "buying_intent": self.buying_intent,
            "competition": self.competition,
            "content_opportunity": self.content_opportunity,
            "affiliate_potential": self.affiliate_potential,
            "product_potential": self.product_potential,
            "brand_opportunity": self.brand_opportunity,
            "opportunity_score": self.opportunity_score,
        }


@dataclass
class NormalizedTrendResult:
    """Unified trend signal from any provider."""

    trend: str
    keyword: str
    source: str
    timestamp: str = field(default_factory=utc_now_iso)
    popularity: float = 0.0
    buying_intent: float = 0.0
    competition: float = 50.0
    category: str = "general"
    sentiment: str = "neutral"
    related_creators: list[str] = field(default_factory=list)
    recommended_content: dict[str, Any] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)
    opportunity: OpportunityScores = field(default_factory=OpportunityScores)
    content_intelligence: ContentIntelligence = field(default_factory=ContentIntelligence)
    niche: str = "general"
    signal_type: str = "trend"
    dedupe_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend": self.trend,
            "keyword": self.keyword,
            "source": self.source,
            "timestamp": self.timestamp,
            "popularity": self.popularity,
            "buying_intent": self.buying_intent,
            "competition": self.competition,
            "category": self.category,
            "sentiment": self.sentiment,
            "related_creators": self.related_creators,
            "recommended_content": self.recommended_content,
            "raw_data": self.raw_data,
            "opportunity": self.opportunity.to_dict(),
            "content_intelligence": self.content_intelligence.to_dict(),
            "niche": self.niche,
            "signal_type": self.signal_type,
            "dedupe_key": self.dedupe_key,
        }


@dataclass
class ProviderScanResult:
    """Result from a single provider scan attempt."""

    provider: str
    success: bool
    online: bool
    results: list[NormalizedTrendResult] = field(default_factory=list)
    warning: str | None = None
    error: str | None = None
    duration_ms: int = 0
    item_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "success": self.success,
            "online": self.online,
            "warning": self.warning,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "item_count": self.item_count,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class ScanReport:
    """Full multi-provider scan report."""

    niche: str
    timestamp: str = field(default_factory=utc_now_iso)
    providers_online: list[str] = field(default_factory=list)
    providers_offline: list[str] = field(default_factory=list)
    provider_results: list[ProviderScanResult] = field(default_factory=list)
    trends: list[NormalizedTrendResult] = field(default_factory=list)
    opportunities: list[NormalizedTrendResult] = field(default_factory=list)
    recommendations: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    stored: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "niche": self.niche,
            "timestamp": self.timestamp,
            "providers_online": self.providers_online,
            "providers_offline": self.providers_offline,
            "provider_results": [p.to_dict() for p in self.provider_results],
            "trends": [t.to_dict() for t in self.trends],
            "opportunities": [o.to_dict() for o in self.opportunities],
            "recommendations": self.recommendations,
            "warnings": self.warnings,
            "stored": self.stored,
            "trend_count": len(self.trends),
            "opportunity_count": len(self.opportunities),
        }
