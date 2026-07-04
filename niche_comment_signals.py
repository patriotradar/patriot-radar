"""
Niche-Aware Comment Signal processor.

Computes lightweight comment-based virality signals per video:
  - comment velocity (growth rate)
  - repetition score (repeated phrases)
  - curiosity/confusion indicators
  - niche relevance score

Standalone module — does not modify existing TikTok trend extraction.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from niche_comment_config import load_niche_config

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "is", "it", "this", "that", "with", "as", "be", "are", "was",
    "were", "i", "you", "he", "she", "they", "we", "my", "your", "so",
})


def _tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def _ngrams(tokens: list[str], n: int) -> list[str]:
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _comment_velocity(comments: list[dict[str, Any]], comment_count: int) -> float:
    """
    Estimate comment growth rate (comments per hour) from timestamps.
    Returns 0–100 normalized score.
    """
    timestamps = [
        int(c["create_time"])
        for c in comments
        if c.get("create_time") is not None
    ]
    count = max(len(comments), comment_count, 1)

    if len(timestamps) >= 2:
        span_seconds = max(max(timestamps) - min(timestamps), 60)
        rate_per_hour = count / (span_seconds / 3600.0)
    elif len(timestamps) == 1:
        # Single timestamp — assume comments arrived within last hour
        rate_per_hour = float(count)
    else:
        # No timestamps — use count as weak proxy (assume 24h window)
        rate_per_hour = count / 24.0

    # Normalize: 50+ comments/hour → ~100 score
    normalized = min(100.0, (rate_per_hour / 50.0) * 100.0)
    return round(normalized, 2)


def _repetition_score(comments: list[dict[str, Any]]) -> float:
    """
    Score repeated phrases (2–3 word n-grams) across comments.
    Returns 0–100.
    """
    if not comments:
        return 0.0

    phrase_counts: Counter[str] = Counter()
    for comment in comments:
        text = (comment.get("text") or "").strip()
        if not text:
            continue
        tokens = _tokenize(text)
        for n in (2, 3):
            for gram in _ngrams(tokens, n):
                phrase_counts[gram] += 1

    if not phrase_counts:
        return 0.0

    repeated = sum(1 for _, cnt in phrase_counts.items() if cnt >= 2)
    total_phrases = len(phrase_counts)
    repeat_ratio = repeated / max(total_phrases, 1)

    # Boost if any phrase appears 3+ times (strong echo chamber signal)
    max_repeat = max(phrase_counts.values()) if phrase_counts else 0
    boost = min(30.0, (max_repeat - 2) * 10.0) if max_repeat >= 3 else 0.0

    score = min(100.0, repeat_ratio * 70.0 + boost)
    return round(score, 2)


def _curiosity_score(comments: list[dict[str, Any]], curiosity_phrases: list[str]) -> float:
    """Fraction of comments matching curiosity/confusion phrases, scaled 0–100."""
    if not comments:
        return 0.0

    phrases = [p.lower() for p in curiosity_phrases]
    matches = 0
    for comment in comments:
        text = (comment.get("text") or "").lower()
        if any(p in text for p in phrases):
            matches += 1

    ratio = matches / len(comments)
    return round(min(100.0, ratio * 100.0), 2)


def _niche_relevance_score(
    comments: list[dict[str, Any]],
    caption: str,
    keywords: list[str],
    excluded_topics: list[str],
) -> float:
    """
    Keyword match score against niche config, penalized by excluded topics.
    Returns 0–100.
    """
    kw = [k.lower() for k in keywords]
    excluded = [e.lower() for e in excluded_topics]

    texts = [caption.lower()] + [(c.get("text") or "").lower() for c in comments]
    combined = " ".join(texts)

    if not combined.strip():
        return 0.0

    keyword_hits = sum(1 for k in kw if k in combined)
    keyword_score = min(100.0, (keyword_hits / max(len(kw), 1)) * 100.0)

    excluded_hits = sum(1 for e in excluded if e in combined)
    penalty = min(80.0, excluded_hits * 25.0)

    # Per-comment keyword density bonus
    comment_matches = 0
    for comment in comments:
        text = (comment.get("text") or "").lower()
        if any(k in text for k in kw):
            comment_matches += 1
    density_bonus = min(20.0, (comment_matches / max(len(comments), 1)) * 20.0)

    score = max(0.0, min(100.0, keyword_score + density_bonus - penalty))
    return round(score, 2)


def _composite_signal(
    velocity: float,
    repetition: float,
    curiosity: float,
    niche: float,
) -> float:
    """Weighted composite for ranking early virality potential."""
    raw = velocity * 0.30 + repetition * 0.20 + curiosity * 0.25 + niche * 0.25
    return round(min(100.0, raw), 2)


def _top_repeated_phrases(comments: list[dict[str, Any]], limit: int = 5) -> list[str]:
    phrase_counts: Counter[str] = Counter()
    for comment in comments:
        tokens = _tokenize(comment.get("text") or "")
        for n in (2, 3):
            for gram in _ngrams(tokens, n):
                phrase_counts[gram] += 1
    return [p for p, c in phrase_counts.most_common(limit) if c >= 2]


def _curiosity_examples(
    comments: list[dict[str, Any]],
    curiosity_phrases: list[str],
    limit: int = 3,
) -> list[str]:
    phrases = [p.lower() for p in curiosity_phrases]
    examples: list[str] = []
    for comment in comments:
        text = (comment.get("text") or "").strip()
        if text and any(p in text.lower() for p in phrases):
            examples.append(text[:120])
        if len(examples) >= limit:
            break
    return examples


def compute_video_comment_signals(
    video: dict[str, Any],
    niche_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute all comment signals for a single video."""
    config = niche_config or load_niche_config()
    comments = video.get("comments") or []
    if not isinstance(comments, list):
        comments = []

    caption = (video.get("caption") or "").strip()
    url = (video.get("url") or "").strip()
    author = (video.get("author") or "").strip()
    comment_count = int(video.get("comment_count") or len(comments))

    velocity = _comment_velocity(comments, comment_count)
    repetition = _repetition_score(comments)
    curiosity = _curiosity_score(comments, config.get("curiosity_phrases") or [])
    niche = _niche_relevance_score(
        comments,
        caption,
        config.get("keywords") or [],
        config.get("excluded_topics") or [],
    )
    composite = _composite_signal(velocity, repetition, curiosity, niche)

    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] if url else "unknown"
    dedupe_key = f"niche_comment:{url_hash}"

    return {
        "video_url": url,
        "author": author,
        "caption_preview": caption[:200],
        "comment_count": comment_count,
        "comments_analyzed": len(comments),
        "signals": {
            "comment_velocity": velocity,
            "repetition_score": repetition,
            "curiosity_score": curiosity,
            "niche_relevance_score": niche,
            "composite_signal": composite,
        },
        "details": {
            "top_repeated_phrases": _top_repeated_phrases(comments),
            "curiosity_examples": _curiosity_examples(
                comments, config.get("curiosity_phrases") or []
            ),
            "niche_id": config.get("niche_id", "default"),
            "niche_label": config.get("label", "Default Niche"),
        },
        "dedupe_key": dedupe_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_batch_comment_signals(
    videos: list[dict[str, Any]],
    niche_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Process a batch of videos and return aggregated signal results."""
    config = niche_config or load_niche_config()
    results: list[dict[str, Any]] = []

    for video in videos:
        if not isinstance(video, dict):
            continue
        try:
            results.append(compute_video_comment_signals(video, config))
        except Exception as exc:
            logger.warning("Signal computation failed for video: %s", exc)

    results.sort(
        key=lambda r: r.get("signals", {}).get("composite_signal", 0),
        reverse=True,
    )

    avg_composite = 0.0
    if results:
        avg_composite = round(
            sum(r["signals"]["composite_signal"] for r in results) / len(results),
            2,
        )

    return {
        "success": bool(results),
        "niche_id": config.get("niche_id"),
        "niche_label": config.get("label"),
        "video_count": len(results),
        "avg_composite_signal": avg_composite,
        "videos": results,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
