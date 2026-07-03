"""
Read-only TikTok trend signal extraction layer.

Converts TikTok video URLs or pre-fetched metadata into structured trend
intelligence signals. Does not modify scoring, recommendations, or persistence.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from keyword_diversity import dedupe_keywords, dedupe_phrases

PLATFORM = "tiktok"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIKTOK_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:tiktok\.com|vm\.tiktok\.com)/[^\s\"']+",
    re.IGNORECASE,
)

HOOK_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("curiosity", "nobody is talking about", re.compile(r"nobody(?:'s| is) talking about", re.I)),
    ("curiosity", "you need to hear this", re.compile(r"you need to (?:hear|know|see) this", re.I)),
    ("curiosity", "wait until the end", re.compile(r"wait until (?:the end|you see)", re.I)),
    ("question", "is it just me", re.compile(r"is it just me (?:or|that)", re.I)),
    ("question", "am i the only one", re.compile(r"am i the only one", re.I)),
    ("question", "why does nobody", re.compile(r"why (?:does|do) nobody", re.I)),
    ("controversy", "controversial", re.compile(r"(?:might be |this is )?controversial", re.I)),
    ("controversy", "unpopular opinion", re.compile(r"unpopular opinion", re.I)),
    ("controversy", "hot take", re.compile(r"hot take", re.I)),
    ("opinion", "i think", re.compile(r"\bi think\b", re.I)),
    ("opinion", "in my opinion", re.compile(r"\b(?:in my opinion|imo)\b", re.I)),
    ("storytime", "story time", re.compile(r"story\s*time", re.I)),
    ("storytime", "let me tell you", re.compile(r"let me tell you", re.I)),
]

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "politics": (
        "politics", "government", "election", "parliament", "vote", "brexit",
        "immigration", "policy", "minister", "labour", "conservative", "reform",
        "border", "tax", "nhs", "westminster",
    ),
    "culture": (
        "culture", "tradition", "heritage", "history", "british", "england",
        "royal", "monarchy", "flag", "patriot", "national", "identity",
        "remembrance", "veteran", "military", "churchill",
    ),
    "lifestyle": (
        "lifestyle", "daily", "routine", "morning", "habit", "home", "family",
        "relationship", "dating", "parenting", "food", "travel",
    ),
    "identity": (
        "identity", "proud", "pride", "who am i", "belong", "roots", "generation",
        "millennial", "gen z", "working class", "northern", "scouse", "geordie",
    ),
    "fitness": (
        "fitness", "gym", "workout", "training", "health", "diet", "protein",
        "running", "weight", "muscle",
    ),
    "finance": (
        "finance", "money", "salary", "mortgage", "cost of living", "inflation",
        "invest", "savings", "debt", "budget", "rent",
    ),
    "entertainment": (
        "movie", "film", "music", "celebrity", "tv show", "netflix", "sport",
        "football", "cricket", "rugby",
    ),
}

EMOTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pride": ("proud", "pride", "honour", "honor", "best country", "greatest", "hero"),
    "outrage": ("outrage", "disgusting", "unacceptable", "furious", "angry", "sick of", "enough"),
    "curiosity": ("curious", "secret", "hidden", "nobody knows", "did you know", "wait for"),
    "nostalgia": ("remember", "back in the day", "used to", "childhood", "golden age", "miss"),
    "shock": ("shocked", "can't believe", "insane", "wild", "mind blown", "unreal"),
    "inspiration": ("inspire", "motivat", "never give up", "you can", "dream", "achieve"),
}

FORMAT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("yes_no_debate", re.compile(r"\byes or no\b|\? yes or no", re.I), 0.9),
    ("hot_take", re.compile(r"hot take|unpopular opinion|controversial", re.I), 0.85),
    ("storytime", re.compile(r"story\s*time|let me tell you|so this happened", re.I), 0.8),
    ("educational_breakdown", re.compile(r"here(?:'s| is) (?:why|how)|break(?:ing)? down|explained", re.I), 0.75),
    ("unpopular_opinion", re.compile(r"unpopular opinion", re.I), 0.9),
    ("list_format", re.compile(r"\b\d+\s+(?:things|reasons|ways|signs|tips)\b", re.I), 0.8),
]

SLANG_PATTERNS = re.compile(
    r"\b(?:lowkey|highkey|delulu|rizz|ate|slay|npc|main character|"
    r"it's giving|no cap|cap|based|red flag|green flag|ick|vibe check)\b",
    re.I,
)
STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "is", "it", "this", "that", "with", "you", "your", "my", "me", "i", "we",
    "they", "are", "was", "be", "have", "has", "had", "do", "does", "did",
    "not", "no", "yes", "so", "if", "just", "about", "from", "as", "by",
})


def _empty_batch() -> dict[str, Any]:
    return {
        "platform": PLATFORM,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "extracted_items": [],
        "aggregated_signals": {
            "dominant_hooks": [],
            "dominant_formats": [],
            "emotional_distribution": {},
            "rising_topics": [],
            "keyword_velocity_signals": [],
            "viral_pattern_summary": "",
        },
        "insight_summary": "",
    }


def _is_tiktok_url(value: str) -> bool:
    return bool(TIKTOK_URL_PATTERN.match(value.strip()))


def _normalize_text(*parts: str | None) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def _fetch_tiktok_metadata(url: str) -> dict[str, Any] | None:
    """Best-effort metadata fetch via TikTok oEmbed. Returns None on failure."""
    try:
        resp = requests.get(
            "https://www.tiktok.com/oembed",
            params={"url": url},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        title = data.get("title") or ""
        author = data.get("author_name") or ""
        return {
            "url": url,
            "caption": title,
            "description": title,
            "author": author,
            "title": title,
            "source": "oembed",
        }
    except Exception:
        return None


def _resolve_item(raw: str | dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        caption = _normalize_text(
            raw.get("caption"),
            raw.get("description"),
            raw.get("title"),
        )
        if not caption:
            return None
        return {
            "url": raw.get("url", ""),
            "caption": caption,
            "description": raw.get("description", caption),
            "author": raw.get("author", ""),
            "title": raw.get("title", caption),
            "source": raw.get("source", "metadata"),
        }

    if not isinstance(raw, str):
        return None

    value = raw.strip()
    if not value:
        return None

    if _is_tiktok_url(value):
        fetched = _fetch_tiktok_metadata(value)
        if fetched:
            return fetched
        return {
            "url": value,
            "caption": "",
            "description": "",
            "author": "",
            "title": "",
            "source": "url_only",
        }

    # Fallback mode: treat plain strings as manual captions/descriptions.
    return {
        "url": "",
        "caption": value,
        "description": value,
        "author": "",
        "title": value,
        "source": "manual_caption",
    }


def _first_sentence(text: str, max_len: int = 120) -> str:
    if not text:
        return ""
    match = re.split(r"[.!?\n]", text, maxsplit=1)
    hook = match[0].strip()
    if len(hook) > max_len:
        hook = hook[: max_len - 3].rstrip() + "..."
    return hook


def _detect_hook(text: str) -> dict[str, str]:
    for hook_type, _label, pattern in HOOK_PATTERNS:
        if pattern.search(text):
            return {"hook_text": _first_sentence(text), "hook_type": hook_type}

    if "?" in text[:80]:
        return {"hook_text": _first_sentence(text), "hook_type": "question"}

    return {"hook_text": _first_sentence(text), "hook_type": "opinion"}


def _score_topics(text: str) -> tuple[str, list[str]]:
    lowered = text.lower()
    scores: dict[str, int] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        scores[topic] = sum(1 for kw in keywords if kw in lowered)

    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    primary = ranked[0][0] if ranked[0][1] > 0 else "other"
    secondary = [t for t, s in ranked[1:4] if s > 0]
    return primary, secondary


def _detect_emotions(text: str) -> dict[str, Any]:
    lowered = text.lower()
    scores: dict[str, float] = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits:
            scores[emotion] = hits

    if not scores:
        return {"dominant_emotion": "curiosity", "emotion_mixture": {"curiosity": 1.0}}

    total = sum(scores.values())
    mixture = {k: round(v / total, 2) for k, v in scores.items()}
    dominant = max(scores, key=scores.get)
    return {"dominant_emotion": dominant, "emotion_mixture": mixture}


def _detect_format(text: str) -> dict[str, Any]:
    best_type = "talking_head"
    best_score = 0.35
    for fmt_type, pattern, strength in FORMAT_PATTERNS:
        if pattern.search(text):
            if strength > best_score:
                best_type = fmt_type
                best_score = strength
    return {"format_type": best_type, "format_strength_score": round(best_score, 2)}


def _engagement_virality_boost(engagement: dict[str, Any] | None) -> float:
    """Lightweight engagement-based virality boost from Apify metrics (0.0–0.4)."""
    if not engagement:
        return 0.0
    plays = float(engagement.get("play_count") or 0)
    diggs = float(engagement.get("digg_count") or 0)
    shares = float(engagement.get("share_count") or 0)
    comments = float(engagement.get("comment_count") or 0)
    if plays <= 0 and diggs <= 0:
        return 0.0

    import math
    play_score = min(0.15, math.log10(max(plays, 1)) / 7)
    engagement_rate = (diggs + shares * 2 + comments * 1.5) / max(plays, 1)
    rate_score = min(0.15, engagement_rate * 50)
    share_score = min(0.1, math.log10(max(shares, 1)) / 5)
    return round(play_score + rate_score + share_score, 2)


def _sentiment_intensity(emotion: dict[str, Any]) -> float:
    """0.0–0.2 boost from dominant emotion mixture intensity."""
    mixture = emotion.get("emotion_mixture") or {}
    if not mixture:
        return 0.0
    top = max(mixture.values())
    return round(min(0.2, top * 0.2), 2)


def _detect_virality(
    text: str,
    hook: dict[str, str],
    fmt: dict[str, Any],
    emotion: dict[str, Any] | None = None,
    engagement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lowered = text.lower()
    hook_words = len(hook.get("hook_text", "").split())
    fast_hook = hook_words > 0 and hook_words <= 12

    controversy_markers = ("controversial", "unpopular", "hot take", "debate", "wrong")
    controversy = sum(1 for m in controversy_markers if m in lowered)
    controversy_level = min(1.0, 0.2 + controversy * 0.25)

    relatability_markers = (
        "is it just me", "anyone else", "we all", "relatable", "everyone",
        "british people", "uk ", "england",
    )
    relatability = sum(1 for m in relatability_markers if m in lowered)
    relatability_level = min(1.0, 0.15 + relatability * 0.2)

    share_triggers = []
    if "?" in text:
        share_triggers.append("question_prompt")
    if fmt["format_type"] in ("yes_no_debate", "hot_take", "unpopular_opinion"):
        share_triggers.append("debate_bait")
    if hook["hook_type"] in ("curiosity", "controversy"):
        share_triggers.append("hook_tension")
    if re.search(r"\b(tag|share|duet|stitch)\b", lowered):
        share_triggers.append("explicit_cta")

    viral_strength = (
        (0.25 if fast_hook else 0.0)
        + controversy_level * 0.3
        + relatability_level * 0.25
        + (0.2 if share_triggers else 0.05)
        + fmt["format_strength_score"] * 0.2
        + _engagement_virality_boost(engagement)
        + _sentiment_intensity(emotion or {})
    )

    return {
        "virality_signals": {
            "fast_hook": fast_hook,
            "controversy_level": round(controversy_level, 2),
            "relatability_level": round(relatability_level, 2),
            "shareability_triggers": share_triggers,
            "engagement_boost": _engagement_virality_boost(engagement),
            "sentiment_intensity": _sentiment_intensity(emotion or {}),
        },
        "viral_strength_score": round(min(1.0, viral_strength), 2),
        "virality_score": int(round(min(1.0, viral_strength) * 100)),
    }


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z']{3,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def _extract_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    for hook_type, label, pattern in HOOK_PATTERNS:
        if pattern.search(text):
            phrases.append(label)
    for fmt_type, pattern, _ in FORMAT_PATTERNS:
        match = pattern.search(text)
        if match:
            phrases.append(match.group(0).lower())
    for match in SLANG_PATTERNS.finditer(text):
        phrases.append(match.group(0).lower())
    return list(dict.fromkeys(phrases))


def _cluster_keywords(
    keywords: list[str],
    historical: set[str] | None = None,
    batch_seen: set[str] | None = None,
) -> list[dict[str, Any]]:
    hist = set(historical or [])
    seen = batch_seen if batch_seen is not None else set()
    diverse = dedupe_keywords(keywords, hist, seen, max_count=8)
    if not diverse:
        return []
    counts = Counter(kw for kw in keywords if kw in diverse)
    total = max(len(keywords), 1)
    return [
        {
            "keyword": kw,
            "frequency": counts.get(kw, 1),
            "velocity_signal": round(counts.get(kw, 1) / total, 2),
        }
        for kw in diverse
    ]


def _extract_single_item(
    meta: dict[str, Any],
    historical: set[str] | None = None,
    batch_seen: set[str] | None = None,
) -> dict[str, Any] | None:
    text = _normalize_text(meta.get("caption"), meta.get("description"), meta.get("title"))
    if not text and meta.get("source") == "url_only":
        return {
            "url": meta.get("url", ""),
            "source": meta.get("source"),
            "extraction_status": "metadata_unavailable",
            "hook": {"hook_text": "", "hook_type": "opinion"},
            "topics": {"primary_topic": "other", "secondary_topics": []},
            "emotion": {"dominant_emotion": "curiosity", "emotion_mixture": {}},
            "format": {"format_type": "unknown", "format_strength_score": 0.0},
            "virality": {
                "virality_signals": {
                    "fast_hook": False,
                    "controversy_level": 0.0,
                    "relatability_level": 0.0,
                    "shareability_triggers": [],
                },
                "viral_strength_score": 0.0,
                "virality_score": 0,
            },
            "linguistics": {"keyword_clusters": [], "phrase_patterns": []},
        }

    if not text:
        return None

    hist = set(historical or [])
    seen = batch_seen if batch_seen is not None else set()

    hook = _detect_hook(text)
    primary_topic, secondary_topics = _score_topics(text)
    emotion = _detect_emotions(text)
    fmt = _detect_format(text)
    engagement = meta.get("engagement")
    virality = _detect_virality(text, hook, fmt, emotion=emotion, engagement=engagement)
    keywords = _extract_keywords(text)
    phrases = dedupe_phrases(_extract_phrases(text), hist, seen)

    return {
        "url": meta.get("url", ""),
        "source": meta.get("source"),
        "author": meta.get("author", ""),
        "caption_preview": text[:200],
        "extraction_status": "complete",
        "hook": hook,
        "topics": {"primary_topic": primary_topic, "secondary_topics": secondary_topics},
        "emotion": emotion,
        "format": fmt,
        "virality": virality,
        "linguistics": {
            "keyword_clusters": _cluster_keywords(keywords, historical=hist, batch_seen=seen),
            "phrase_patterns": phrases,
        },
    }


def _aggregate_signals(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return _empty_batch()["aggregated_signals"]

    hook_types = [i["hook"]["hook_type"] for i in items if i.get("hook")]
    format_types = [i["format"]["format_type"] for i in items if i.get("format")]
    emotions = [i["emotion"]["dominant_emotion"] for i in items if i.get("emotion")]
    topics = [i["topics"]["primary_topic"] for i in items if i.get("topics")]

    emotion_dist: dict[str, float] = {}
    if emotions:
        emotion_counts = Counter(emotions)
        total = len(emotions)
        emotion_dist = {k: round(v / total, 2) for k, v in emotion_counts.items()}

    all_keywords: list[str] = []
    for item in items:
        for cluster in item.get("linguistics", {}).get("keyword_clusters", []):
            all_keywords.extend([cluster["keyword"]] * cluster.get("frequency", 1))

    keyword_velocity = [
        {"keyword": kw, "mentions": count, "velocity": round(count / len(items), 2)}
        for kw, count in Counter(all_keywords).most_common(10)
    ]

    hook_counter = Counter(hook_types)
    format_counter = Counter(format_types)
    topic_counter = Counter(topics)

    fast_hooks = sum(
        1 for i in items
        if i.get("virality", {}).get("virality_signals", {}).get("fast_hook")
    )
    avg_viral = sum(i.get("virality", {}).get("viral_strength_score", 0) for i in items) / len(items)

    summary_parts = []
    if hook_counter:
        top_hook = hook_counter.most_common(1)[0][0]
        summary_parts.append(f"{top_hook} hooks dominate")
    if format_counter:
        top_fmt = format_counter.most_common(1)[0][0]
        summary_parts.append(f"{top_fmt.replace('_', ' ')} formats are rising")
    if emotion_dist:
        top_emotion = max(emotion_dist, key=emotion_dist.get)
        summary_parts.append(f"{top_emotion} is the primary emotional driver")
    summary_parts.append(f"{fast_hooks}/{len(items)} items use fast hooks")
    summary_parts.append(f"avg viral strength {avg_viral:.2f}")

    return {
        "dominant_hooks": [h for h, _ in hook_counter.most_common(5)],
        "dominant_formats": [f for f, _ in format_counter.most_common(5)],
        "emotional_distribution": emotion_dist,
        "rising_topics": [t for t, _ in topic_counter.most_common(5)],
        "keyword_velocity_signals": keyword_velocity,
        "viral_pattern_summary": "; ".join(summary_parts),
    }


def _build_insight_summary(aggregated: dict[str, Any], item_count: int) -> str:
    if item_count == 0:
        return "No TikTok content provided for signal extraction."

    hooks = aggregated.get("dominant_hooks", [])
    formats = aggregated.get("dominant_formats", [])
    topics = aggregated.get("rising_topics", [])
    emotions = aggregated.get("emotional_distribution", {})

    hook_str = ", ".join(hooks[:3]) if hooks else "mixed"
    format_str = ", ".join(f.replace("_", " ") for f in formats[:3]) if formats else "varied"
    topic_str = ", ".join(topics[:3]) if topics else "niche-general"
    emotion_str = ", ".join(
        f"{k} ({v:.0%})" for k, v in sorted(emotions.items(), key=lambda x: -x[1])[:3]
    ) if emotions else "neutral"

    return (
        f"Analysed {item_count} TikTok item(s). Emerging patterns: "
        f"{hook_str} hooks, {format_str} formats, topics leaning toward {topic_str}. "
        f"Emotional mix: {emotion_str}. "
        f"{aggregated.get('viral_pattern_summary', '')}"
    )


def extract_tiktok_trend_signals(
    inputs: list[str | dict[str, Any]] | None,
    historical_keywords: set[str] | None = None,
) -> dict[str, Any]:
    """
    Extract structured trend intelligence from TikTok URLs or metadata.

    Fails silently: returns an empty structured object when input is missing
    or invalid. Never raises to callers.

    historical_keywords: roots of all previously stored keywords for dedup.
    """
    try:
        if not inputs:
            return _empty_batch()

        historical = set(historical_keywords or [])
        batch_seen: set[str] = set()

        resolved: list[dict[str, Any]] = []
        for raw in inputs:
            item = _resolve_item(raw)
            if item:
                resolved.append(item)

        extracted_items: list[dict[str, Any]] = []
        for meta in resolved:
            extracted = _extract_single_item(meta, historical=historical, batch_seen=batch_seen)
            if extracted:
                extracted_items.append(extracted)

        aggregated = _aggregate_signals(extracted_items)
        batch = {
            "platform": PLATFORM,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "extracted_items": extracted_items,
            "aggregated_signals": aggregated,
            "insight_summary": _build_insight_summary(aggregated, len(extracted_items)),
        }
        return batch
    except Exception:
        return _empty_batch()
