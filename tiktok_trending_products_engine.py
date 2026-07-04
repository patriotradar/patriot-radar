"""
Trending Products detection engine for the TikTok insights pipeline.

Independent module — detects product mentions from comment and video signals.
Never raises; always returns a list.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9']+")

_STOP_WORDS = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was",
    "one", "our", "out", "day", "get", "has", "him", "his", "how", "its", "may", "new",
    "now", "old", "see", "two", "way", "who", "that", "this", "with", "have", "from",
    "they", "been", "said", "each", "which", "their", "will", "other", "about", "many",
    "then", "them", "these", "some", "would", "make", "like", "into", "time", "very",
    "when", "come", "here", "just", "what", "know", "take", "people", "year", "good",
    "could", "than", "first", "down", "did", "more", "being", "only", "those", "going",
    "really", "still", "even", "your", "there", "where", "why", "back", "much", "before",
    "right", "too", "any", "same", "also", "after", "over", "such", "give", "most",
    "tell", "does", "work", "well", "video", "videos", "comment", "comments", "tiktok",
    "lol", "omg", "yes", "yeah", "dont", "doesnt", "isnt", "wasnt", "cant", "im", "ive",
})

_PRODUCT_HINT_WORDS = frozenset({
    "serum", "cream", "lotion", "moisturizer", "cleanser", "shampoo", "conditioner",
    "supplement", "protein", "powder", "brand", "product", "bought", "buy", "using",
    "tried", "recommend", "recommended", "link", "amazon", "store", "affordable",
    "expensive", "worth", "works", "working", "obsessed", "love", "favorite", "favourite",
    "dupe", "dupes", "routine", "ingredient", "spf", "retinol", "collagen", "whey",
    "preworkout", "equipment", "mat", "dumbbell", "resistance", "bands", "vitamin",
    "oil", "mask", "scrub", "toner", "gel", "spray", "pill", "capsule", "shake",
})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _comment_text(comment: dict[str, Any]) -> str:
    return str(comment.get("comment_text") or comment.get("text") or "").strip().lower()


def _video_id(video: dict[str, Any]) -> str:
    return str(video.get("video_id") or video.get("id") or video.get("url") or "").strip()


def _extract_phrases(text: str) -> list[str]:
    tokens = _WORD_RE.findall(text.lower())
    tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) >= 2]
    phrases: list[str] = []
    for n in (2, 3):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            if len(phrase) >= 5:
                phrases.append(phrase)
    return phrases


def _niche_tokens(niche: str) -> set[str]:
    if not niche:
        return set()
    return set(_WORD_RE.findall(niche.lower()))


def _engagement_score(video: dict[str, Any]) -> float:
    engagement = video.get("engagement") or {}
    views = max(
        _safe_float(
            video.get("play_count")
            or video.get("playCount")
            or engagement.get("play_count")
            or engagement.get("playCount")
        ),
        1.0,
    )
    likes = _safe_float(
        video.get("digg_count")
        or video.get("diggCount")
        or video.get("likes")
        or engagement.get("digg_count")
        or engagement.get("diggCount")
    )
    comments = _safe_float(
        video.get("comment_count")
        or video.get("commentCount")
        or engagement.get("comment_count")
        or engagement.get("commentCount")
    )
    return (likes + comments) / views


def generateTrendingProducts(
    videos: list[dict[str, Any]] | None,
    comments: list[dict[str, Any]] | None,
    niche: str = "",
    trend_scores: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Detect trending products from comment and video signals.

    Uses repeated phrases in comments, cross-video mentions, engagement correlation,
    trend velocity alignment, and niche keyword overlap. Never raises; always returns a list.
    """
    try:
        videos_list = [v for v in (videos or []) if isinstance(v, dict)]
        comments_list = [c for c in (comments or []) if isinstance(c, dict)]
        scores_list = [s for s in (trend_scores or []) if isinstance(s, dict)]

        if not comments_list and not videos_list:
            return []

        trend_by_video: dict[str, dict[str, Any]] = {}
        for ts in scores_list:
            vid = str(ts.get("video_id") or "").strip()
            if vid:
                trend_by_video[vid] = ts

        video_by_id: dict[str, dict[str, Any]] = {}
        for video in videos_list:
            vid = _video_id(video)
            if vid:
                video_by_id[vid] = video

        total_videos = max(len(video_by_id), 1)

        phrase_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "mention_count": 0,
                "video_ids": set(),
                "examples": [],
            }
        )

        for comment in comments_list:
            text = _comment_text(comment)
            if not text:
                continue
            vid = str(comment.get("video_id") or "").strip()
            for phrase in _extract_phrases(text):
                entry = phrase_data[phrase]
                entry["mention_count"] += 1
                if vid:
                    entry["video_ids"].add(vid)
                if len(entry["examples"]) < 5:
                    entry["examples"].append(text[:160])

        if not phrase_data:
            return []

        max_mentions = max(e["mention_count"] for e in phrase_data.values()) or 1
        max_velocity = max(
            (_safe_float(t.get("velocity_score")) for t in scores_list),
            default=0.0,
        ) or 1.0
        max_engagement = max(
            (_engagement_score(video_by_id[vid]) for vid in video_by_id),
            default=0.0,
        ) or 1.0

        niche_tokens = _niche_tokens(niche)
        results: list[dict[str, Any]] = []

        for phrase, data in phrase_data.items():
            mention_count = int(data["mention_count"])
            video_ids: set[str] = data["video_ids"]
            video_count = len(video_ids)

            mention_freq = mention_count / max_mentions
            video_spread = video_count / total_videos

            velocities = [
                _safe_float(trend_by_video.get(vid, {}).get("velocity_score"))
                for vid in video_ids
            ]
            avg_velocity = sum(velocities) / max(len(velocities), 1)
            trend_velocity_norm = avg_velocity / max_velocity if max_velocity > 0 else 0.0

            engagements = [
                _engagement_score(video_by_id[vid])
                for vid in video_ids
                if vid in video_by_id
            ]
            avg_engagement = sum(engagements) / max(len(engagements), 1)
            engagement_norm = avg_engagement / max_engagement if max_engagement > 0 else 0.0

            phrase_tokens = set(phrase.split())
            if niche_tokens:
                overlap = len(phrase_tokens & niche_tokens) / max(len(niche_tokens), 1)
                hint_bonus = 0.3 if phrase_tokens & _PRODUCT_HINT_WORDS else 0.0
                niche_relevance = _clamp(overlap + hint_bonus)
            else:
                niche_relevance = 0.5 if phrase_tokens & _PRODUCT_HINT_WORDS else 0.2

            score = _clamp(
                0.4 * mention_freq
                + 0.2 * video_spread
                + 0.2 * trend_velocity_norm
                + 0.1 * engagement_norm
                + 0.1 * niche_relevance
            )

            if not (mention_count >= 2 or video_count >= 2 or score >= 0.6):
                continue

            confidence = _clamp(
                0.3 * mention_freq
                + 0.3 * video_spread
                + 0.2 * trend_velocity_norm
                + 0.2 * engagement_norm
            )

            evidence: list[str] = list(data["examples"][:3])
            if video_count >= 2:
                evidence.append(f"Mentioned across {video_count} videos")
            if trend_velocity_norm > 0.7:
                evidence.append("Associated with high-velocity trending videos")
            if niche_relevance > 0.5 and niche:
                evidence.append(f"Aligned with niche: {niche}")

            results.append({
                "name": phrase.title(),
                "mention_count": mention_count,
                "video_count": video_count,
                "trend_velocity": round(trend_velocity_norm, 4),
                "niche_relevance": round(niche_relevance, 4),
                "confidence": round(confidence, 4),
                "evidence": evidence,
                "score": round(score, 4),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:20]

    except Exception as exc:
        logger.warning("generateTrendingProducts failed: %s", exc)
        return []
