"""
Shared signal helpers for recommendation selection and humanisation.

Canonical definitions for format families, emotional triggers, and stable
indexing. Used by recommendation_selector and recommendation_output only.
"""

from __future__ import annotations

import hashlib

FORMAT_FAMILIES = (
    ("debate", ("yes/no", "debate", "comment-bait")),
    ("reaction", ("reaction", "news reaction", "trend-reaction")),
    ("explainer", ("explainer", "step-by-step", "educational", "carousel")),
    ("talking_head", ("talking-head", "talking head", "pov")),
    ("curiosity", ("curiosity-gap", "curiosity gap")),
)


def stable_index(seed: str, modulo: int) -> int:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def format_family(post_format: str) -> str:
    lowered = (post_format or "").lower()
    for family, markers in FORMAT_FAMILIES:
        if any(marker in lowered for marker in markers):
            return family
    if "carousel" in lowered:
        return "explainer"
    if "clip" in lowered:
        return "reaction"
    return "talking_head"


def dominant_emotion(item: dict | None) -> str:
    if not item:
        return "pride"
    emotion = int(item.get("emotion", 0) or 0)
    debate = int(item.get("debate", 0) or 0)
    british = int(item.get("british", 0) or 0)
    if debate >= emotion and debate >= 18:
        return "debate"
    if emotion >= 18:
        return "pride"
    if british >= 18:
        return "British identity"
    return "curiosity"


def emotional_trigger(item: dict, engagement_signal: str, post_format: str) -> str:
    signal_map = {
        "HOOK_OK_LOW_CONVERSION": "curiosity",
        "ATTENTION_WITHOUT_VALUE": "education",
        "DISTRIBUTION_LIMITED": "reach",
        "HEALTHY": dominant_emotion(item),
    }
    trigger = signal_map.get(engagement_signal, dominant_emotion(item))
    family = format_family(post_format)
    if family == "debate":
        return "debate"
    if family == "explainer":
        return "education"
    return trigger
