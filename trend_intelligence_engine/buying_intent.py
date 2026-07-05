"""Buying intent detection and opportunity scoring."""

from __future__ import annotations

import math
import re
from typing import Any

from trend_intelligence_engine.types import NormalizedTrendResult, OpportunityScores

BUYING_INTENT_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("best", re.compile(r"\bbest\b", re.I), 18),
    ("review", re.compile(r"\breview(s|ed|ing)?\b", re.I), 20),
    ("alternative", re.compile(r"\balternative(s)?\s+to\b", re.I), 22),
    ("versus", re.compile(r"\bvs\.?\b|\bversus\b", re.I), 16),
    ("worth_it", re.compile(r"\bworth\s+it\b", re.I), 19),
    ("how_do_i", re.compile(r"\bhow\s+(do|can|to)\s+i\b", re.I), 17),
    ("recommendation", re.compile(r"\brecommend(ation|ed|s)?\b", re.I), 18),
    ("where_buy", re.compile(r"\bwhere\s+(can\s+i\s+)?buy\b", re.I), 24),
    ("problem", re.compile(r"\bproblem(s)?\s+with\b", re.I), 15),
    ("anyone_tried", re.compile(r"\banyone\s+tried\b", re.I), 21),
    ("looking_for", re.compile(r"\blooking\s+for\b", re.I), 20),
    ("should_i_buy", re.compile(r"\bshould\s+i\s+buy\b", re.I), 23),
    ("comparison", re.compile(r"\bcompar(e|ison|ing)\b", re.I), 17),
    ("deal", re.compile(r"\bdeal(s)?\b|\bdiscount\b|\bsale\b", re.I), 14),
    ("price", re.compile(r"\bprice(s|d)?\b|\bcost\b|\bcheap(est)?\b", re.I), 13),
]

PRODUCT_CATEGORY_HINTS = [
    ("clothing", ("hoodie", "shirt", "jacket", "clothing", "apparel", "merch")),
    ("flags", ("flag", "union jack", "banner")),
    ("gifts", ("gift", "souvenir", "memorabilia")),
    ("books", ("book", "biography", "history")),
    ("accessories", ("pin", "brooch", "badge", "patch")),
]


def _safe_score(value: Any, default: float = 0.0) -> float:
    """Clamp numeric score to 0–100; treat None/NaN as default."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(n):
        return default
    return float(min(100.0, max(0.0, n)))


def detect_buying_signals(text: str) -> list[str]:
    """Return matched buying-intent signal labels for text."""
    if not text:
        return []
    signals: list[str] = []
    for label, pattern, _weight in BUYING_INTENT_PATTERNS:
        if pattern.search(text):
            signals.append(label)
    return signals


def estimate_buying_intent(text: str) -> float:
    """Estimate buying intent score 0–100 from text."""
    if not text:
        return 0.0
    score = 0.0
    for _label, pattern, weight in BUYING_INTENT_PATTERNS:
        if pattern.search(text):
            score += weight
    return _safe_score(score, 0.0)


def infer_category(keyword: str) -> str:
    kw = (keyword or "").lower()
    for category, hints in PRODUCT_CATEGORY_HINTS:
        if any(h in kw for h in hints):
            return category
    if any(w in kw for w in ("army", "navy", "raf", "military", "veteran")):
        return "military"
    if any(w in kw for w in ("royal", "king", "monarchy", "crown")):
        return "royalty"
    if any(w in kw for w in ("history", "heritage", "tradition")):
        return "heritage"
    return "general"


def score_opportunity(
    result: NormalizedTrendResult,
    *,
    platform_count: int = 1,
) -> OpportunityScores:
    """Compute full opportunity scores for a normalized trend result."""
    text = f"{result.trend} {result.keyword}"
    buying = int(_safe_score(max(_safe_score(result.buying_intent), estimate_buying_intent(text))))
    popularity = int(_safe_score(result.popularity))
    competition = int(_safe_score(result.competition, 50.0))

    search_demand = int(min(100, popularity * 0.6 + platform_count * 8))
    content_opportunity = int(min(100, max(0, 100 - competition * 0.7 + popularity * 0.2)))
    affiliate_potential = int(min(100, buying * 0.7 + (30 if infer_category(result.keyword) != "general" else 10)))
    product_potential = int(min(100, buying * 0.5 + affiliate_potential * 0.4))
    brand_opportunity = int(min(100, popularity * 0.4 + content_opportunity * 0.3))

    weights = {
        "search_demand": 0.20,
        "buying_intent": 0.25,
        "competition": 0.10,
        "content_opportunity": 0.20,
        "affiliate_potential": 0.10,
        "product_potential": 0.10,
        "brand_opportunity": 0.05,
    }
    competition_bonus = max(0, 100 - competition)
    opportunity_score = int(
        min(
            100,
            round(
                search_demand * weights["search_demand"]
                + buying * weights["buying_intent"]
                + competition_bonus * weights["competition"]
                + content_opportunity * weights["content_opportunity"]
                + affiliate_potential * weights["affiliate_potential"]
                + product_potential * weights["product_potential"]
                + brand_opportunity * weights["brand_opportunity"]
            ),
        )
    )

    return OpportunityScores(
        search_demand=search_demand,
        buying_intent=buying,
        competition=competition,
        content_opportunity=content_opportunity,
        affiliate_potential=affiliate_potential,
        product_potential=product_potential,
        brand_opportunity=brand_opportunity,
        opportunity_score=opportunity_score,
    )


def enrich_with_opportunity(
    result: NormalizedTrendResult,
    *,
    platform_count: int = 1,
) -> NormalizedTrendResult:
    """Attach opportunity scores and buying signals to a result."""
    text = f"{result.trend} {result.keyword}"
    signals = detect_buying_signals(text)
    if signals and not result.buying_intent:
        result.buying_intent = estimate_buying_intent(text)
    if not result.category or result.category == "general":
        result.category = infer_category(result.keyword)
    result.opportunity = score_opportunity(result, platform_count=platform_count)
    if signals:
        result.raw_data.setdefault("buying_signals", signals)
    return result


def rank_opportunities(results: list[NormalizedTrendResult]) -> list[NormalizedTrendResult]:
    """Sort results by opportunity score descending."""
    enriched = [enrich_with_opportunity(r) for r in results]
    enriched.sort(key=lambda r: r.opportunity.opportunity_score, reverse=True)
    return enriched


def merge_cross_platform(
    results: list[NormalizedTrendResult],
) -> list[NormalizedTrendResult]:
    """Merge duplicate keywords across providers, boosting cross-platform signals."""
    by_key: dict[str, dict[str, Any]] = {}
    for item in results:
        key = (item.keyword or item.trend or "").strip().lower()[:80]
        if not key:
            continue
        if key not in by_key:
            by_key[key] = {"item": item, "sources": set(), "count": 0}
        by_key[key]["sources"].add(item.source)
        by_key[key]["count"] += 1
        if item.popularity > by_key[key]["item"].popularity:
            by_key[key]["item"].popularity = item.popularity

    merged: list[NormalizedTrendResult] = []
    for entry in by_key.values():
        item = entry["item"]
        platform_count = len(entry["sources"])
        if platform_count > 1:
            item.popularity = min(100.0, item.popularity * (1 + 0.15 * (platform_count - 1)))
            item.raw_data["platforms"] = sorted(entry["sources"])
            item.raw_data["platform_count"] = platform_count
        merged.append(enrich_with_opportunity(item, platform_count=platform_count))

    merged.sort(key=lambda r: r.opportunity.opportunity_score, reverse=True)
    return merged
