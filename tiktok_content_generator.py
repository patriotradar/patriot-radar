"""
Content generation engine for the TikTok insights pipeline.

Generates captions, hashtags, and hook variations from emerging products and niche context.
Never raises; always returns a safe content pack structure.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_VIRAL_HASHTAGS = ["#fyp", "#viral", "#foryou", "#foryoupage", "#tiktokmademebuyit"]

_NICHE_HASHTAGS: dict[str, list[str]] = {
    "fitness": ["#fitness", "#gymtok", "#workout", "#fitnesstips", "#gymmotivation"],
    "beauty": ["#skincare", "#beautytok", "#makeup", "#skincareroutine", "#glowup"],
    "tech": ["#techtok", "#gadgets", "#techreview", "#techtips", "#innovation"],
    "finance": ["#moneytok", "#financetips", "#investing", "#personalfinance", "#wealth"],
    "gaming": ["#gaming", "#gamertok", "#gamingclips", "#esports", "#gamer"],
    "lifestyle": ["#lifestyle", "#aesthetic", "#dayinmylife", "#grwm", "#vlog"],
    "business": ["#businesstok", "#entrepreneur", "#sidehustle", "#marketing", "#smallbusiness"],
    "unknown": ["#trending", "#musthave", "#discover"],
}

_NICHE_CAPTION_TEMPLATES: dict[str, list[str]] = {
    "fitness": [
        "this changed my workouts",
        "nobody told me about this gym hack",
        "why is everyone using this for gains",
        "this is the fitness find of the year",
    ],
    "beauty": [
        "my skin has never looked like this",
        "this skincare find is going viral for a reason",
        "why did nobody tell me about this sooner",
        "the glow up is real with this one",
    ],
    "tech": [
        "this is blowing up for a reason",
        "the tech find everyone is talking about",
        "wait until you see what this does",
        "this gadget changed my daily routine",
    ],
    "finance": [
        "people are quietly using this",
        "the money hack nobody talks about",
        "this changed how I think about saving",
        "why smart people are switching to this",
    ],
    "gaming": [
        "this is the setup upgrade everyone needs",
        "gamers are obsessed with this right now",
        "why is nobody talking about this gear",
        "this changed my gaming sessions",
    ],
    "lifestyle": [
        "this small change made a huge difference",
        "the aesthetic find of the season",
        "everyone needs this in their routine",
        "why is this blowing up on my fyp",
    ],
    "business": [
        "this is how creators are scaling right now",
        "the business tool nobody talks about",
        "why entrepreneurs are switching to this",
        "this changed my content strategy",
    ],
    "unknown": [
        "this is blowing up for a reason",
        "why is everyone talking about this",
        "the find you need to see",
        "wait until you try this",
    ],
}

_NICHE_HOOK_TEMPLATES: dict[str, list[str]] = {
    "fitness": [
        "POV: you finally found the workout hack that actually works",
        "Stop scrolling — this fitness find is worth your time",
        "The gym secret nobody wants you to know",
    ],
    "beauty": [
        "POV: your skin after finding this product",
        "Dermatologists hate this viral skincare find",
        "The glow up hack taking over beauty TikTok",
    ],
    "tech": [
        "This gadget is going viral and here's why",
        "Tech TikTok is obsessed with this right now",
        "The device that changed everything for me",
    ],
    "finance": [
        "People are quietly making moves with this",
        "The money tip your feed isn't showing you",
        "Why smart savers are paying attention to this",
    ],
    "gaming": [
        "Gamers — you need to see this setup upgrade",
        "This is the gear everyone's switching to",
        "POV: you found the gaming hack of the year",
    ],
    "lifestyle": [
        "The aesthetic find that's taking over my fyp",
        "POV: you discovered the routine hack everyone uses",
        "This small change made my days so much better",
    ],
    "business": [
        "Creators are scaling with this — here's how",
        "The business hack nobody talks about on TikTok",
        "POV: you found the tool that changes everything",
    ],
    "unknown": [
        "POV: you found the viral product before everyone else",
        "Stop scrolling — this is worth your attention",
        "Why is nobody talking about this yet",
    ],
}


def _empty_content_pack() -> dict[str, Any]:
    return {"captions": [], "hashtags": [], "hook_variations": []}


def _niche_string(niche: Any) -> str:
    if isinstance(niche, dict):
        return str(niche.get("niche") or "unknown").strip().lower()
    return str(niche or "unknown").strip().lower()


def _product_slug(product: str) -> str:
    return "".join(c for c in product.lower().split()[:3] if c.isalnum())


def generateContentPack(
    emerging_products: list[dict[str, Any]] | None,
    niche: Any = "",
    apify_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate captions, hashtags, and hook variations for emerging products.

    Never raises; always returns {"captions": [], "hashtags": [], "hook_variations": []}.
    """
    try:
        niche_str = _niche_string(niche)
        if niche_str not in _NICHE_HASHTAGS:
            niche_str = "unknown"

        products = [p for p in (emerging_products or []) if isinstance(p, dict)]
        feedback = apify_feedback if isinstance(apify_feedback, dict) else {}

        captions: list[str] = []
        hashtags: list[str] = list(_VIRAL_HASHTAGS[:3])
        hashtags.extend(_NICHE_HASHTAGS.get(niche_str, _NICHE_HASHTAGS["unknown"])[:3])
        hooks: list[str] = []

        caption_templates = _NICHE_CAPTION_TEMPLATES.get(
            niche_str, _NICHE_CAPTION_TEMPLATES["unknown"]
        )
        hook_templates = _NICHE_HOOK_TEMPLATES.get(
            niche_str, _NICHE_HOOK_TEMPLATES["unknown"]
        )

        for i, product in enumerate(products[:5]):
            product_name = str(product.get("product") or "").strip()
            if not product_name:
                continue

            template = caption_templates[i % len(caption_templates)]
            captions.append(f"{template} — {product_name}")

            slug = _product_slug(product_name)
            if slug:
                hashtags.append(f"#{slug}")

            hook_base = hook_templates[i % len(hook_templates)]
            hooks.append(f"{hook_base} ({product_name})")

        if not captions:
            for template in caption_templates[:3]:
                captions.append(template)

        if not hooks:
            hooks.extend(hook_templates[:3])

        if feedback.get("data_source"):
            captions.append(f"trending on {feedback['data_source']} right now")

        seen_tags: set[str] = set()
        unique_hashtags: list[str] = []
        for tag in hashtags:
            lower = tag.lower()
            if lower not in seen_tags:
                seen_tags.add(lower)
                unique_hashtags.append(tag)

        return {
            "captions": captions[:8],
            "hashtags": unique_hashtags[:15],
            "hook_variations": hooks[:6],
        }
    except Exception as exc:
        logger.warning("generateContentPack failed: %s", exc)
        return _empty_content_pack()
