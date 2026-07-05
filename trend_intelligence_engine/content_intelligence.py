"""Content intelligence generation for discovered trends."""

from __future__ import annotations

import re
from typing import Any

from trend_intelligence_engine.buying_intent import detect_buying_signals, infer_category
from trend_intelligence_engine.types import ContentIntelligence, NormalizedTrendResult

FORMAT_BY_INTENT: dict[str, str] = {
    "best": "listicle / comparison video",
    "review": "honest review / unboxing",
    "alternative": "versus / alternative roundup",
    "versus": "side-by-side comparison",
    "worth_it": "value verdict short-form",
    "how_do_i": "tutorial / how-to",
    "recommendation": "recommendation carousel",
    "where_buy": "buying guide / affiliate link post",
    "problem": "problem-solution explainer",
    "anyone_tried": "community poll / testimonial stitch",
    "looking_for": "buyer's guide",
}

AUDIENCE_BY_CATEGORY: dict[str, str] = {
    "military": "British veterans, military families, and patriotic supporters",
    "royalty": "Royal watchers and British heritage enthusiasts",
    "heritage": "History buffs and proud Britons",
    "flags": "Patriotic homeowners and event organisers",
    "gifts": "Gift shoppers seeking meaningful British products",
    "clothing": "Style-conscious patriots and merch buyers",
    "books": "Readers interested in British history and leadership",
    "general": "UK creators and patriotic audience on TikTok/YouTube",
}


def _title_case_keyword(keyword: str) -> str:
    text = (keyword or "this topic").strip()
    if not text:
        return "This Topic"
    return text[0].upper() + text[1:]


def _generate_hook(keyword: str, signals: list[str]) -> str:
    kw = _title_case_keyword(keyword)
    if "best" in signals:
        return f"Stop scrolling — here's the best {kw} nobody is talking about"
    if "review" in signals or "worth_it" in signals:
        return f"Is {kw} actually worth it? Here's the honest truth"
    if "alternative" in signals or "versus" in signals:
        return f"{kw} — which option wins? I tested them all"
    if "how_do_i" in signals:
        return f"How to nail {kw} (the way creators won't tell you)"
    if "problem" in signals:
        return f"The problem with {kw} that everyone ignores"
    if "looking_for" in signals:
        return f"If you're looking for {kw}, watch this first"
    return f"Nobody is talking about {kw} — and that's your opportunity"


def _generate_angle(keyword: str, category: str, signals: list[str]) -> str:
    kw = keyword.lower()
    if signals:
        primary = signals[0]
        return f"Capitalise on {primary.replace('_', ' ')} intent around '{keyword}' in the {category} space"
    if "should" in kw or "?" in kw:
        return f"Debate-driven patriot content: '{keyword}'"
    if category in ("military", "heritage", "royalty"):
        return f"Emotional British pride angle on {keyword}"
    return f"Trend-jacking {keyword} with authentic creator POV"


def _pain_points(keyword: str, signals: list[str]) -> list[str]:
    points = [
        f"Hard to find trustworthy information about {keyword}",
        "Creators oversaturate generic patriotic content",
    ]
    if "where_buy" in signals:
        points.append("Shoppers struggle to find authentic UK sellers")
    if "problem" in signals:
        points.append(f"Frustration and confusion around {keyword}")
    if "alternative" in signals or "versus" in signals:
        points.append("Too many options, unclear winner")
    return points[:4]


def _questions(keyword: str) -> list[str]:
    kw = keyword.strip()
    return [
        f"What is the best {kw}?",
        f"Is {kw} worth buying in 2026?",
        f"How do I get started with {kw}?",
        f"What do people regret about {kw}?",
    ]


def _cta_suggestions(signals: list[str]) -> list[str]:
    ctas = ["Follow for daily British trend alerts", "Save this before it trends"]
    if "where_buy" in signals or "best" in signals:
        ctas.append("Link in bio for our top pick")
    if "review" in signals:
        ctas.append("Comment REVIEW for the full breakdown")
    if "how_do_i" in signals:
        ctas.append("DM GUIDE for the step-by-step")
    return ctas[:4]


def generate_content_intelligence(result: NormalizedTrendResult) -> ContentIntelligence:
    """Build content intelligence block for a trend result."""
    keyword = result.keyword or result.trend
    text = f"{result.trend} {keyword}"
    signals = detect_buying_signals(text) or result.raw_data.get("buying_signals", [])
    category = result.category or infer_category(keyword)

    suggested_format = "short-form TikTok / Reels"
    for sig in signals:
        if sig in FORMAT_BY_INTENT:
            suggested_format = FORMAT_BY_INTENT[sig]
            break
    if result.source == "youtube":
        suggested_format = "YouTube Short or long-form explainer"
    elif result.source == "reddit":
        suggested_format = "community reaction / stitch video"
    elif result.source in ("news", "google_trends"):
        suggested_format = "news reaction / hot take"

    viral_base = int(min(100, max(0, result.popularity)))
    intent_boost = int(min(20, result.buying_intent * 0.2))
    viral_score = min(100, viral_base + intent_boost)

    search_kws = [keyword]
    for token in re.findall(r"[a-z]{4,}", keyword.lower())[:3]:
        if token not in search_kws:
            search_kws.append(token)

    return ContentIntelligence(
        content_angle=_generate_angle(keyword, category, signals),
        hook=_generate_hook(keyword, signals),
        target_audience=AUDIENCE_BY_CATEGORY.get(category, AUDIENCE_BY_CATEGORY["general"]),
        search_keywords=search_kws[:6],
        pain_points=_pain_points(keyword, signals),
        questions=_questions(keyword),
        buying_signals=signals,
        cta_suggestions=_cta_suggestions(signals),
        suggested_format=suggested_format,
        viral_potential_score=viral_score,
    )


def enrich_with_content_intelligence(result: NormalizedTrendResult) -> NormalizedTrendResult:
    """Attach content intelligence and recommended content payload."""
    ci = generate_content_intelligence(result)
    result.content_intelligence = ci
    result.recommended_content = {
        "hook": ci.hook,
        "format": ci.suggested_format,
        "angle": ci.content_angle,
        "platforms": _platform_recommendations(result),
    }
    return result


def _platform_recommendations(result: NormalizedTrendResult) -> dict[str, str]:
    keyword = result.keyword or result.trend
    hook = result.content_intelligence.hook if result.content_intelligence.hook else _generate_hook(keyword, [])
    return {
        "tiktok": f"TikTok: {hook[:80]}",
        "youtube": f"YouTube: Deep dive — {keyword}",
        "instagram": f"Instagram: Carousel on {keyword}",
        "blog": f"Blog/SEO: Ultimate guide to {keyword}",
        "newsletter": f"Newsletter: This week's {keyword} opportunity",
    }


def enrich_all(results: list[NormalizedTrendResult]) -> list[NormalizedTrendResult]:
    return [enrich_with_content_intelligence(r) for r in results]
