"""
Emerging product detection engine for the TikTok insights pipeline.

Detects early-stage product signals from video and comment data.
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
    "app", "tool", "device", "gadget", "platform", "course", "book",
})

_NICHE_PRODUCT_HINTS: dict[str, frozenset[str]] = {
    "fitness": frozenset({"protein", "whey", "preworkout", "supplement", "mat", "dumbbell", "bands", "shake"}),
    "beauty": frozenset({"serum", "cream", "moisturizer", "cleanser", "spf", "retinol", "collagen", "toner"}),
    "tech": frozenset({"app", "gadget", "device", "phone", "laptop", "headphones", "tool"}),
    "finance": frozenset({"app", "platform", "course", "book", "tool"}),
    "gaming": frozenset({"headset", "controller", "keyboard", "mouse", "monitor"}),
    "lifestyle": frozenset({"routine", "organizer", "planner", "candle", "diffuser"}),
    "business": frozenset({"course", "tool", "platform", "template", "software"}),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _niche_string(niche: Any) -> str:
    if isinstance(niche, dict):
        return str(niche.get("niche") or "unknown").strip().lower()
    return str(niche or "unknown").strip().lower()


def _comment_text(comment: dict[str, Any]) -> str:
    return str(comment.get("comment_text") or comment.get("text") or "").strip().lower()


def _video_id(video: dict[str, Any]) -> str:
    return str(video.get("video_id") or video.get("id") or video.get("url") or "").strip()


def _extract_product_phrases(text: str) -> list[str]:
    tokens = [t for t in _WORD_RE.findall(text.lower()) if t not in _STOP_WORDS and len(t) >= 2]
    phrases: list[str] = []
    for n in (2, 3):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            if len(phrase) >= 5:
                phrases.append(phrase)
    return phrases


def _engagement_score(video: dict[str, Any]) -> float:
    engagement = video.get("engagement") or {}
    views = max(
        _safe_float(
            video.get("play_count") or video.get("playCount")
            or engagement.get("play_count") or engagement.get("playCount")
        ),
        1.0,
    )
    likes = _safe_float(
        video.get("digg_count") or video.get("diggCount") or video.get("likes")
        or engagement.get("digg_count") or engagement.get("diggCount")
    )
    comments = _safe_float(
        video.get("comment_count") or video.get("commentCount")
        or engagement.get("comment_count") or engagement.get("commentCount")
    )
    return (likes + comments) / views


def _velocity_state(signal_strength: float, mention_count: int, video_count: int) -> str:
    if signal_strength >= 0.75 or (mention_count >= 5 and video_count >= 3):
        return "viral"
    if signal_strength >= 0.45 or video_count >= 2:
        return "rising"
    return "emerging"


def detectEmergingProducts(
    videos: list[dict[str, Any]] | None,
    comments: list[dict[str, Any]] | None,
    niche: Any = "",
    trend_scores: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Detect emerging products from early signals in videos and comments.

    Never raises; always returns a list.
    """
    try:
        videos_list = [v for v in (videos or []) if isinstance(v, dict)]
        comments_list = [c for c in (comments or []) if isinstance(c, dict)]
        scores_list = [s for s in (trend_scores or []) if isinstance(s, dict)]
        niche_str = _niche_string(niche)
        niche_hints = _NICHE_PRODUCT_HINTS.get(niche_str, frozenset())

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

        max_engagement = max(
            (_engagement_score(v) for v in video_by_id.values()),
            default=0.0,
        ) or 1.0
        max_trend = max(
            (_safe_float(t.get("trend_score")) for t in scores_list),
            default=0.0,
        ) or 1.0

        phrase_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "mention_count": 0,
                "video_ids": set(),
                "first_video": "",
                "examples": [],
                "high_engagement_hits": 0,
                "trend_scores": [],
            }
        )

        for comment in comments_list:
            text = _comment_text(comment)
            if not text:
                continue
            vid = str(comment.get("video_id") or "").strip()
            for phrase in _extract_product_phrases(text):
                phrase_tokens = set(phrase.split())
                if not (phrase_tokens & _PRODUCT_HINT_WORDS or phrase_tokens & niche_hints):
                    continue
                entry = phrase_data[phrase]
                entry["mention_count"] += 1
                if vid:
                    entry["video_ids"].add(vid)
                    if not entry["first_video"]:
                        entry["first_video"] = vid
                    video = video_by_id.get(vid, {})
                    eng = _engagement_score(video) / max_engagement
                    if eng > 0.6:
                        entry["high_engagement_hits"] += 1
                    ts = trend_by_video.get(vid, {})
                    if ts:
                        entry["trend_scores"].append(_safe_float(ts.get("trend_score")))
                if len(entry["examples"]) < 5:
                    entry["examples"].append(text[:160])

        if not phrase_data:
            return []

        results: list[dict[str, Any]] = []

        for phrase, data in phrase_data.items():
            mention_count = int(data["mention_count"])
            video_ids: set[str] = data["video_ids"]
            video_count = len(video_ids)

            phrase_tokens = set(phrase.split())
            niche_overlap = (
                len(phrase_tokens & niche_hints) / max(len(niche_hints), 1)
                if niche_hints else 0.3
            )

            avg_trend = (
                sum(data["trend_scores"]) / max(len(data["trend_scores"]), 1)
                if data["trend_scores"] else 0.0
            )
            trend_norm = avg_trend / max_trend if max_trend > 0 else 0.0

            single_strong = 1.0 if data["high_engagement_hits"] >= 1 and mention_count == 1 else 0.0
            cross_video = _clamp(video_count / max(len(video_by_id), 1))
            velocity_spike = _clamp(mention_count / 5.0)
            trend_corr = _clamp(trend_norm)
            niche_rel = _clamp(niche_overlap + (0.2 if phrase_tokens & _PRODUCT_HINT_WORDS else 0.0))

            signal_strength = _clamp(
                0.25 * max(single_strong, cross_video)
                + 0.25 * velocity_spike
                + 0.25 * trend_corr
                + 0.25 * niche_rel
            )

            if signal_strength < 0.2 and mention_count < 2:
                continue

            evidence: list[str] = list(data["examples"][:3])
            if data["high_engagement_hits"]:
                evidence.append("Strong mention in high-engagement video")
            if video_count >= 2:
                evidence.append(f"Early cross-video repetition ({video_count} videos)")
            if velocity_spike > 0.5:
                evidence.append("Comment velocity spike detected")
            if trend_corr > 0.5:
                evidence.append("Correlates with trending video scores")
            if niche_rel > 0.4 and niche_str != "unknown":
                evidence.append(f"Niche keyword overlap ({niche_str})")

            results.append({
                "product": phrase.title(),
                "signal_strength": round(signal_strength, 4),
                "first_seen_video": str(data["first_video"] or ""),
                "velocity_state": _velocity_state(signal_strength, mention_count, video_count),
                "evidence": evidence,
            })

        results.sort(key=lambda x: x["signal_strength"], reverse=True)
        return results[:15]

    except Exception as exc:
        logger.warning("detectEmergingProducts failed: %s", exc)
        return []
