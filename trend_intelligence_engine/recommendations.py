"""AI and rule-based recommendations from trend intelligence."""

from __future__ import annotations

import logging
import os
from typing import Any

from trend_intelligence_engine.types import NormalizedTrendResult

logger = logging.getLogger(__name__)


def build_recommendations(
    trends: list[NormalizedTrendResult],
    opportunities: list[NormalizedTrendResult],
    *,
    niche: str = "general",
) -> dict[str, Any]:
    """
    Generate actionable recommendations without requiring AI.
    Optionally enriches with Groq/Gemini when keys are present.
    """
    top_opps = opportunities[:10] if opportunities else trends[:10]
    content_today = []
    products = []
    affiliates = []
    newsletter = []
    youtube = []
    tiktok = []
    instagram = []
    blog = []
    seo = []

    for item in top_opps:
        ci = item.content_intelligence
        platforms = item.recommended_content.get("platforms", {}) if item.recommended_content else {}
        score = item.opportunity.opportunity_score if item.opportunity else int(item.popularity)

        entry = {
            "keyword": item.keyword,
            "opportunity_score": score,
            "hook": ci.hook,
            "format": ci.suggested_format,
            "source": item.source,
        }
        content_today.append(entry)

        if item.opportunity and item.opportunity.affiliate_potential >= 50:
            affiliates.append({**entry, "affiliate_potential": item.opportunity.affiliate_potential})
        if item.opportunity and item.opportunity.product_potential >= 45:
            products.append({**entry, "product_potential": item.opportunity.product_potential})
        if platforms.get("newsletter"):
            newsletter.append({"topic": item.keyword, "angle": platforms["newsletter"]})
        if platforms.get("youtube"):
            youtube.append({"idea": platforms["youtube"], "score": score})
        if platforms.get("tiktok"):
            tiktok.append({"idea": platforms["tiktok"], "score": score})
        if platforms.get("instagram"):
            instagram.append({"idea": platforms["instagram"], "score": score})
        if platforms.get("blog"):
            blog.append({"topic": item.keyword, "title": platforms["blog"]})
        if ci.search_keywords:
            seo.append(
                {
                    "keyword": item.keyword,
                    "search_keywords": ci.search_keywords,
                    "opportunity_score": score,
                }
            )

    rec = {
        "content_to_create_today": content_today[:5],
        "products_to_promote": products[:5],
        "affiliate_opportunities": affiliates[:5],
        "newsletter_topics": newsletter[:5],
        "youtube_ideas": youtube[:5],
        "tiktok_ideas": tiktok[:5],
        "instagram_ideas": instagram[:5],
        "blog_topics": blog[:5],
        "seo_opportunities": seo[:8],
        "primary_action": _primary_action(top_opps),
        "generated_at": trends[0].timestamp if trends else None,
        "niche": niche,
        "ai_enriched": False,
    }

    ai_rec = _try_ai_enrichment(rec, top_opps, niche)
    if ai_rec:
        rec.update(ai_rec)
        rec["ai_enriched"] = True

    return rec


def _primary_action(opportunities: list[NormalizedTrendResult]) -> dict[str, Any]:
    if not opportunities:
        return {
            "label": "Run trend intelligence scan",
            "action": "run_scan",
            "context": "No opportunities detected yet",
            "opportunity_score": 0,
        }
    top = opportunities[0]
    score = 0
    if top.opportunity:
        score = int(min(100, max(0, top.opportunity.opportunity_score or 0)))
    return {
        "label": f"Create content: {top.keyword[:60]}",
        "action": "create_content",
        "context": top.content_intelligence.hook or top.keyword,
        "opportunity_score": score,
    }


def _try_ai_enrichment(
    base: dict[str, Any],
    opportunities: list[NormalizedTrendResult],
    niche: str,
) -> dict[str, Any] | None:
    """Optional Groq/Gemini enrichment — never blocks on failure."""
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not groq_key and not gemini_key:
        return None

    keywords = [o.keyword for o in opportunities[:5]]
    if not keywords:
        return None

    prompt = (
        f"You are CreatorRadar AI. Niche: {niche}. Top opportunities: {', '.join(keywords)}. "
        "Return one sentence insight for today's best content move. Be specific and actionable."
    )

    try:
        import requests

        if groq_key:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 120,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                insight = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if insight:
                    return {"ai_insight": insight}

        if gemini_key:
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": gemini_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                insight = parts[0].get("text", "").strip() if parts else ""
                if insight:
                    return {"ai_insight": insight}
    except Exception as exc:
        logger.warning("AI recommendation enrichment failed: %s", exc)

    return None
