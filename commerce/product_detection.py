"""
Product detection — optional commerce pipeline step.

Matches trending keywords to product suggestions. Only invoked when commerce_mode=true.
"""

from __future__ import annotations

from typing import Any


def _suggest_product(keyword: str) -> str:
    """Keyword → product label heuristic (mirrors trends.make_product)."""
    keyword = (keyword or "").lower()
    if "army" in keyword:
        return "British Army history books"
    if "navy" in keyword:
        return "Royal Navy books and gifts"
    if "raf" in keyword or "air force" in keyword:
        return "RAF aviation books and memorabilia"
    if "veteran" in keyword or "military" in keyword:
        return "Military and veteran merchandise"
    if "flag" in keyword or "union jack" in keyword:
        return "Union Jack flags and patriotic gifts"
    if "churchill" in keyword or "ww2" in keyword or "history" in keyword:
        return "British history books"
    if "remembrance" in keyword or "poppy" in keyword:
        return "Remembrance poppy merchandise"
    if "royal" in keyword or "king" in keyword or "queen" in keyword:
        return "Royal family commemorative items"
    if "skincare" in keyword or "beauty" in keyword:
        return "Trending skincare products"
    if "fitness" in keyword or "gym" in keyword or "workout" in keyword:
        return "Fitness and workout gear"
    if "food" in keyword or "recipe" in keyword or "cooking" in keyword:
        return "Kitchen and cooking products"
    return ""


def detect_products_from_trends(trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Detect attachable products from trend signals.

    Returns empty list on invalid input; never raises.
    """
    if not isinstance(trends, list):
        return []

    products: list[dict[str, Any]] = []
    seen: set[str] = set()

    for trend in trends:
        if not isinstance(trend, dict):
            continue
        keyword = str(trend.get("keyword") or trend.get("summary") or trend.get("topic") or "").strip()
        if not keyword:
            continue
        existing = str(trend.get("product") or "").strip()
        product_name = existing or _suggest_product(keyword)
        if not product_name:
            continue
        key = product_name.lower()
        if key in seen:
            continue
        seen.add(key)
        products.append({
            "name": product_name,
            "keyword": keyword,
            "signal_strength": float(trend.get("viral_score") or trend.get("signal_strength") or 0),
            "source": "product_detection",
            "confidence": min(1.0, float(trend.get("viral_score") or 50) / 100),
            "evidence": [f"Trending keyword: {keyword}"],
        })

    return products
