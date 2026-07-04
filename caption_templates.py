"""
Universal caption assembly layer.

Deterministic template-based captions for any niche, with optional AI polish.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Literal, Optional, TypedDict

CaptionFormat = Literal["debate", "opinion", "curiosity", "contrarian"]
CaptionEmotion = Literal["pride", "outrage", "nostalgia", "curiosity"]

VALID_FORMATS = ("debate", "opinion", "curiosity", "contrarian")
VALID_EMOTIONS = ("pride", "outrage", "nostalgia", "curiosity")


class CaptionRequest(TypedDict, total=False):
    topic: str
    format: CaptionFormat
    emotion: CaptionEmotion
    audience_context: Optional[str]


CAPTION_TEMPLATES: dict[str, list[str]] = {
    "debate": [
        "Is {topic} still relevant in 2026? Yes or No?",
        "Should we still accept {topic} today?",
        "Has {topic} gone too far?",
    ],
    "opinion": [
        "Hot take: people are wrong about {topic}.",
        "Unpopular opinion: {topic} needs to change.",
        "We need to talk about {topic} honestly.",
    ],
    "curiosity": [
        "Why is nobody talking about {topic}?",
        "What's really happening with {topic}?",
        "This changes how you see {topic}...",
    ],
    "contrarian": [
        "Everyone believes this about {topic} — but they're wrong.",
        "Most people misunderstand {topic}.",
        "The truth about {topic} is not what you think.",
    ],
}

# Subtle wording variations keyed by emotion. Same structure, same placeholders.
EMOTION_VARIANTS: dict[str, dict[str, list[str]]] = {
    "debate": {
        "pride": [
            "Is {topic} still worth standing up for in 2026? Yes or No?",
            "Should we still celebrate {topic} today?",
            "Has {topic} been given the respect it deserves?",
        ],
        "outrage": [
            "Is {topic} still acceptable in 2026? Yes or No?",
            "Should we still tolerate {topic} today?",
            "Has {topic} gone too far?",
        ],
        "nostalgia": [
            "Is {topic} still relevant in 2026? Yes or No?",
            "Should we still hold onto {topic} today?",
            "Has {topic} lost what made it matter?",
        ],
        "curiosity": [
            "Is {topic} still relevant in 2026? Yes or No?",
            "Should we still accept {topic} today?",
            "Has {topic} gone too far?",
        ],
    },
    "opinion": {
        "pride": [
            "Hot take: people underestimate {topic}.",
            "Unpopular opinion: {topic} deserves more respect.",
            "We need to talk about {topic} with pride.",
        ],
        "outrage": [
            "Hot take: people are wrong about {topic}.",
            "Unpopular opinion: {topic} needs to change.",
            "We need to talk about {topic} honestly.",
        ],
        "nostalgia": [
            "Hot take: we've forgotten what {topic} meant.",
            "Unpopular opinion: {topic} isn't what it used to be.",
            "We need to talk about {topic} before it's too late.",
        ],
        "curiosity": [
            "Hot take: people are wrong about {topic}.",
            "Unpopular opinion: {topic} needs to change.",
            "We need to talk about {topic} honestly.",
        ],
    },
    "curiosity": {
        "pride": [
            "Why is nobody celebrating {topic}?",
            "What's really happening with {topic}?",
            "This changes how you see {topic}...",
        ],
        "outrage": [
            "Why is nobody talking about {topic}?",
            "What's really happening with {topic}?",
            "This changes how you see {topic}...",
        ],
        "nostalgia": [
            "Why does nobody remember {topic}?",
            "What happened to {topic}?",
            "This changes how you see {topic}...",
        ],
        "curiosity": [
            "Why is nobody talking about {topic}?",
            "What's really happening with {topic}?",
            "This changes how you see {topic}...",
        ],
    },
    "contrarian": {
        "pride": [
            "Everyone overlooks this about {topic} — but they're missing the point.",
            "Most people misunderstand {topic}.",
            "The truth about {topic} is not what you think.",
        ],
        "outrage": [
            "Everyone believes this about {topic} — but they're wrong.",
            "Most people misunderstand {topic}.",
            "The truth about {topic} is not what you think.",
        ],
        "nostalgia": [
            "Everyone remembers {topic} wrong — and they're mistaken.",
            "Most people misunderstand {topic}.",
            "The truth about {topic} is not what you think.",
        ],
        "curiosity": [
            "Everyone believes this about {topic} — but they're wrong.",
            "Most people misunderstand {topic}.",
            "The truth about {topic} is not what you think.",
        ],
    },
}


def _normalize_topic(topic: str) -> str:
    cleaned = " ".join((topic or "").strip().split())
    if not cleaned:
        return "this topic"
    return cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()


def _stable_index(key: str, size: int) -> int:
    if size <= 0:
        return 0
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest, 16) % size


def _select_template(
    topic: str,
    caption_format: CaptionFormat,
    emotion: CaptionEmotion,
) -> str:
    variants = EMOTION_VARIANTS.get(caption_format, {}).get(emotion)
    templates = variants or CAPTION_TEMPLATES[caption_format]
    idx = _stable_index(f"{topic.lower()}:{caption_format}:{emotion}", len(templates))
    return templates[idx]


def build_caption(
    topic: str,
    caption_format: CaptionFormat,
    emotion: CaptionEmotion,
    audience_context: Optional[str] = None,
) -> str:
    """
    Assemble a deterministic caption from universal templates.

    Selects a template by format, injects the topic, and applies subtle
    emotional wording variation without changing structure or meaning.
    """
    if caption_format not in VALID_FORMATS:
        caption_format = "debate"
    if emotion not in VALID_EMOTIONS:
        emotion = "curiosity"

    normalized_topic = _normalize_topic(topic)
    template = _select_template(normalized_topic, caption_format, emotion)
    caption = template.format(topic=normalized_topic)

    if audience_context:
        context = " ".join(audience_context.strip().split())
        if context:
            caption = f"{caption} ({context})"

    return caption


def _local_polish(caption: str) -> str:
    """Deterministic cleanup that never changes meaning or structure."""
    polished = re.sub(r"\s+", " ", caption.strip())
    polished = re.sub(r"\s+([?.!,])", r"\1", polished)
    polished = re.sub(r"\.{2,}", "...", polished)
    return polished


def polish_caption(caption: str) -> str:
    """
    Optional polish layer. May use AI for flow/tone only.

    On API errors or rate limits, returns the original caption unchanged.
    """
    if not caption:
        return caption

    cleaned = _local_polish(caption)
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CAPTION_POLISH_API_KEY")
    if not api_key:
        return cleaned

    try:
        import requests

        response = requests.post(
            os.environ.get(
                "CAPTION_POLISH_API_URL",
                "https://api.openai.com/v1/chat/completions",
            ),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.environ.get("CAPTION_POLISH_MODEL", "gpt-4o-mini"),
                "temperature": 0.2,
                "max_tokens": 120,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You polish social media captions. You may ONLY improve natural "
                            "language flow, remove repetition, and slightly adjust tone. "
                            "Do NOT change meaning, structure, add new ideas, or replace "
                            "the topic. Return only the polished caption text."
                        ),
                    },
                    {"role": "user", "content": cleaned},
                ],
            },
            timeout=12,
        )

        if response.status_code == 429:
            return cleaned

        if response.status_code >= 400:
            return cleaned

        payload = response.json()
        polished = payload["choices"][0]["message"]["content"].strip()
        if not polished:
            return cleaned
        return _local_polish(polished)
    except Exception:
        return cleaned


def derive_format_from_item(item: dict) -> CaptionFormat:
    """Map recommendation scores to a caption format without niche branching."""
    debate = int(item.get("debate", 0) or 0)
    emotion = int(item.get("emotion", 0) or 0)
    fresh = int(item.get("fresh", 0) or 0)

    scores = {
        "debate": debate,
        "opinion": emotion,
        "curiosity": fresh,
        "contrarian": (debate + emotion) // 2,
    }
    top_score = max(scores.values())
    candidates = [name for name, score in scores.items() if score == top_score]
    keyword = (item.get("keyword") or "").lower()
    idx = _stable_index(keyword, len(candidates))
    return candidates[idx]  # type: ignore[return-value]


def derive_emotion_from_item(item: dict) -> CaptionEmotion:
    """Map recommendation scores to an emotion label without niche branching."""
    emotion_score = int(item.get("emotion", 0) or 0)
    debate_score = int(item.get("debate", 0) or 0)
    fresh_score = int(item.get("fresh", 0) or 0)
    keyword = (item.get("keyword") or "").lower()

    if emotion_score >= debate_score and emotion_score >= fresh_score:
        pool = ("pride", "outrage")
    elif fresh_score >= debate_score:
        pool = ("curiosity", "nostalgia")
    else:
        pool = ("nostalgia", "curiosity")

    idx = _stable_index(f"{keyword}:emotion", len(pool))
    return pool[idx]  # type: ignore[return-value]


def build_caption_from_item(
    item: dict,
    audience_context: Optional[str] = None,
    enable_polish: bool = False,
) -> str:
    """Build a caption from a ranked recommendation item."""
    topic = item.get("keyword") or item.get("topic") or "this topic"
    caption_format = item.get("format") or derive_format_from_item(item)
    emotion = item.get("emotion_label") or derive_emotion_from_item(item)

    caption = build_caption(
        topic=topic,
        caption_format=caption_format,
        emotion=emotion,
        audience_context=audience_context or item.get("audience_context"),
    )

    if enable_polish:
        return polish_caption(caption)
    return caption


def apply_caption_pipeline(
    items: list[dict],
    enable_polish: bool = False,
    audience_context: Optional[str] = None,
) -> list[dict]:
    """
    Apply deterministic caption assembly to ranked recommendation items.

    Intended for use after recommendation scoring and before output persistence.
    """
    for item in items:
        item["caption"] = build_caption_from_item(
            item,
            audience_context=audience_context,
            enable_polish=enable_polish,
        )
        item["caption_format"] = item.get("format") or derive_format_from_item(item)
        item["caption_emotion"] = item.get("emotion_label") or derive_emotion_from_item(item)
    return items


def example_outputs() -> dict[str, list[str]]:
    """Example captions across three niches using the universal schema."""
    examples = {
        "politics": [],
        "fitness": [],
        "culture": [],
    }

    scenarios = {
        "politics": [
            {"topic": "immigration policy", "format": "debate", "emotion": "outrage"},
            {"topic": "election turnout", "format": "opinion", "emotion": "pride"},
            {"topic": "parliamentary reform", "format": "curiosity", "emotion": "curiosity"},
        ],
        "fitness": [
            {"topic": "creatine supplementation", "format": "debate", "emotion": "curiosity"},
            {"topic": "HIIT training", "format": "contrarian", "emotion": "outrage"},
            {"topic": "sleep recovery", "format": "curiosity", "emotion": "nostalgia"},
        ],
        "culture": [
            {"topic": "streaming exclusives", "format": "opinion", "emotion": "outrage"},
            {"topic": "vinyl revival", "format": "opinion", "emotion": "nostalgia"},
            {"topic": "festival culture", "format": "debate", "emotion": "pride"},
        ],
    }

    for niche, requests in scenarios.items():
        for req in requests:
            examples[niche].append(
                build_caption(
                    topic=req["topic"],
                    caption_format=req["format"],
                    emotion=req["emotion"],
                )
            )

    return examples


if __name__ == "__main__":
    print("Universal caption examples\n" + "=" * 40)
    for niche, captions in example_outputs().items():
        print(f"\n{niche.upper()}")
        for caption in captions:
            print(f"  - {caption}")
