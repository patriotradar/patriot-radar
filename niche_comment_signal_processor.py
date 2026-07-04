"""
Dynamic niche query signal processor.

Computes comment signals at query time from raw comment data.
Niche relevance is never bound at ingestion — the same dataset supports all niches.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from tiktok_pipeline_hardening import clean_comments

_WORD_RE = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "is", "it", "this", "that", "with", "as", "be", "are", "was",
    "were", "i", "you", "he", "she", "they", "we", "my", "your", "so",
})

CURIOSITY_PHRASES = [
    "what is this", "what's this", "wait what", "how do", "how does", "how did",
    "why is", "why does", "why did", "can someone explain", "explain this",
    "i don't understand", "i dont understand", "confused", "what happened",
    "who is", "where is", "is this real", "am i missing",
]

NICHE_SYNONYMS: dict[str, list[str]] = {
    "fitness": ["workout", "gym", "exercise", "training", "muscle", "cardio", "lift"],
    "skincare": ["skin", "acne", "serum", "moisturizer", "routine", "glow", "derma"],
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "blockchain", "token", "web3"],
    "finance": ["money", "budget", "saving", "invest", "wealth", "income", "debt"],
    "cooking": ["recipe", "food", "meal", "kitchen", "bake", "chef", "cook"],
    "beauty": ["makeup", "glam", "cosmetic", "lipstick", "foundation", "mua"],
    "gaming": ["game", "gamer", "playstation", "xbox", "nintendo", "stream"],
    "fashion": ["style", "outfit", "clothing", "wear", "streetwear", "ootd"],
    "health": ["wellness", "nutrition", "diet", "mental", "medical", "doctor"],
    "tech": ["technology", "gadget", "software", "app", "ai", "device"],
    "parenting": ["parent", "baby", "kids", "child", "mom", "dad", "toddler"],
    "travel": ["trip", "vacation", "destination", "flight", "hotel", "explore"],
    "education": ["learn", "study", "school", "teacher", "student", "course"],
    "motivation": ["mindset", "discipline", "habits", "goals", "success", "grind"],
    "pets": ["dog", "cat", "puppy", "kitten", "pet", "animal"],
    "music": ["song", "artist", "beat", "album", "producer", "rap"],
    "business": ["entrepreneur", "startup", "brand", "marketing", "sales", "client"],
    "patriotic": ["patriot", "patriotism", "british", "britain", "uk", "england", "pride"],
    "history": ["heritage", "historical", "past", "ancient", "war", "culture"],
}


def _tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def _ngrams(tokens: list[str], n: int) -> list[str]:
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def build_niche_keywords(niche: str) -> list[str]:
    """Build dynamic keyword list from a runtime niche query."""
    niche_clean = (niche or "").strip().lower()
    if not niche_clean:
        return []

    keywords: list[str] = [niche_clean]
    keywords.extend(_tokenize(niche_clean))

    synonyms = NICHE_SYNONYMS.get(niche_clean, [])
    keywords.extend(synonyms)

    for key, values in NICHE_SYNONYMS.items():
        if niche_clean in values or any(v in niche_clean for v in values):
            keywords.append(key)
            keywords.extend(values)

    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique


def _comment_velocity(comments: list[dict[str, Any]], comment_count: int) -> float:
    timestamps = []
    for comment in comments:
        ts = comment.get("commented_at") or comment.get("create_time")
        if ts is None:
            continue
        if isinstance(ts, str):
            try:
                timestamps.append(int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()))
            except ValueError:
                continue
        else:
            timestamps.append(int(ts))

    count = max(len(comments), comment_count, 1)
    if len(timestamps) >= 2:
        span_seconds = max(max(timestamps) - min(timestamps), 60)
        rate_per_hour = count / (span_seconds / 3600.0)
    elif len(timestamps) == 1:
        rate_per_hour = float(count)
    else:
        rate_per_hour = count / 24.0

    return round(min(100.0, (rate_per_hour / 50.0) * 100.0), 2)


def _repetition_score(comments: list[dict[str, Any]]) -> float:
    if not comments:
        return 0.0

    phrase_counts: Counter[str] = Counter()
    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").strip()
        if not text:
            continue
        tokens = _tokenize(text)
        for n in (2, 3):
            for gram in _ngrams(tokens, n):
                phrase_counts[gram] += 1

    if not phrase_counts:
        return 0.0

    repeated = sum(1 for _, cnt in phrase_counts.items() if cnt >= 2)
    repeat_ratio = repeated / max(len(phrase_counts), 1)
    max_repeat = max(phrase_counts.values())
    boost = min(30.0, (max_repeat - 2) * 10.0) if max_repeat >= 3 else 0.0
    return round(min(100.0, repeat_ratio * 70.0 + boost), 2)


def _curiosity_score(comments: list[dict[str, Any]]) -> float:
    if not comments:
        return 0.0

    matches = 0
    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").lower()
        if any(p in text for p in CURIOSITY_PHRASES):
            matches += 1
    return round(min(100.0, (matches / len(comments)) * 100.0), 2)


def _niche_relevance_score(
    comments: list[dict[str, Any]],
    caption: str,
    keywords: list[str],
) -> float:
    if not keywords:
        return 0.0

    kw = [k.lower() for k in keywords]
    texts = [caption.lower()] + [
        (c.get("comment_text") or c.get("text") or "").lower() for c in comments
    ]
    combined = " ".join(texts)
    if not combined.strip():
        return 0.0

    keyword_hits = sum(1 for k in kw if k in combined)
    keyword_score = min(100.0, (keyword_hits / max(len(kw), 1)) * 100.0)

    comment_matches = 0
    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").lower()
        if any(k in text for k in kw):
            comment_matches += 1
    density_bonus = min(20.0, (comment_matches / max(len(comments), 1)) * 20.0)

    return round(min(100.0, keyword_score + density_bonus), 2)


def _composite_signal(velocity: float, repetition: float, curiosity: float, niche: float) -> float:
    raw = velocity * 0.30 + repetition * 0.20 + curiosity * 0.25 + niche * 0.25
    return round(min(100.0, raw), 2)


def _top_repeated_phrases(comments: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    phrase_counts: Counter[str] = Counter()
    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").strip()
        tokens = _tokenize(text)
        for n in (2, 3):
            for gram in _ngrams(tokens, n):
                phrase_counts[gram] += 1

    return [
        {"phrase": phrase, "count": count}
        for phrase, count in phrase_counts.most_common(limit)
        if count >= 2
    ]


def _trending_comments(
    comments: list[dict[str, Any]],
    keywords: list[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    kw = [k.lower() for k in keywords]
    scored: list[tuple[float, dict[str, Any]]] = []

    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").strip()
        if not text:
            continue
        lower = text.lower()
        relevance = sum(1 for k in kw if k in lower) if kw else 0
        curiosity = 1 if any(p in lower for p in CURIOSITY_PHRASES) else 0
        likes = int(comment.get("comment_like_count") or comment.get("like_count") or 0)
        score = relevance * 25 + curiosity * 15 + min(likes, 50)
        if score > 0 or not kw:
            scored.append((score, comment))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[dict[str, Any]] = []
    for score, comment in scored[:limit]:
        results.append(
            {
                "text": (comment.get("comment_text") or comment.get("text") or "")[:200],
                "author": comment.get("comment_author") or comment.get("author") or "",
                "like_count": int(comment.get("comment_like_count") or comment.get("like_count") or 0),
                "score": round(score, 1),
            }
        )
    return results


def group_raw_rows_by_video(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group flat niche_comment_raw rows into video payloads."""
    by_video: dict[str, dict[str, Any]] = {}

    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        video_id = str(row.get("video_id") or "").strip()
        if not video_id:
            continue

        if video_id not in by_video:
            by_video[video_id] = {
                "video_id": video_id,
                "url": row.get("video_url") or "",
                "caption": row.get("video_caption") or "",
                "author": row.get("video_author") or "",
                "comment_count": int((row.get("metadata") or {}).get("video_comment_count") or 0),
                "comments": [],
            }

        by_video[video_id]["comments"].append(
            {
                "comment_text": row.get("comment_text") or "",
                "comment_author": row.get("comment_author") or "",
                "comment_like_count": int(row.get("comment_like_count") or 0),
                "commented_at": row.get("commented_at"),
            }
        )

    for video in by_video.values():
        video["comment_count"] = max(video["comment_count"], len(video["comments"]))

    return list(by_video.values())


def compute_niche_comment_signals(
    raw_rows: list[dict[str, Any]],
    niche: str,
    *,
    min_relevance: float = 15.0,
) -> dict[str, Any]:
    """
    Compute dynamic niche-aware signals from raw comment rows.

    Returns ranked videos, emerging phrases, and trending comments for the niche.
    """
    niche_clean = (niche or "").strip()
    keywords = build_niche_keywords(niche_clean)
    videos = group_raw_rows_by_video(raw_rows)

    if not niche_clean:
        return {
            "success": False,
            "error": "niche_required",
            "niche": "",
            "keywords": [],
            "video_count": 0,
            "videos": [],
            "emerging_phrases": [],
            "trending_comments": [],
        }

    if not videos:
        return {
            "success": False,
            "error": "no_raw_comments",
            "niche": niche_clean,
            "keywords": keywords,
            "video_count": 0,
            "videos": [],
            "emerging_phrases": [],
            "trending_comments": [],
        }

    results: list[dict[str, Any]] = []
    all_phrases: Counter[str] = Counter()

    for video in videos:
        comments = clean_comments(video.get("comments") or [])
        caption = video.get("caption") or ""
        comment_count = int(video.get("comment_count") or len(comments))

        velocity = _comment_velocity(comments, comment_count)
        repetition = _repetition_score(comments)
        curiosity = _curiosity_score(comments)
        relevance = _niche_relevance_score(comments, caption, keywords)

        if relevance < min_relevance:
            continue

        composite = _composite_signal(velocity, repetition, curiosity, relevance)
        phrases = _top_repeated_phrases(comments)
        for phrase_obj in phrases:
            all_phrases[phrase_obj["phrase"]] += phrase_obj["count"]

        results.append(
            {
                "video_id": video.get("video_id"),
                "video_url": video.get("url") or "",
                "author": video.get("author") or "",
                "caption_preview": caption[:200],
                "comment_count": comment_count,
                "comments_analyzed": len(comments),
                "signals": {
                    "comment_velocity": velocity,
                    "repetition_score": repetition,
                    "curiosity_score": curiosity,
                    "niche_relevance_score": relevance,
                    "composite_signal": composite,
                },
                "top_repeated_phrases": phrases[:5],
                "trending_comments": _trending_comments(comments, keywords, limit=5),
            }
        )

    results.sort(key=lambda v: v["signals"]["composite_signal"], reverse=True)

    emerging = [
        {"phrase": phrase, "count": count}
        for phrase, count in all_phrases.most_common(15)
    ]

    flat_trending: list[dict[str, Any]] = []
    for video in results[:10]:
        for comment in video.get("trending_comments") or []:
            flat_trending.append(
                {
                    **comment,
                    "video_url": video.get("video_url"),
                    "video_author": video.get("author"),
                }
            )
    flat_trending.sort(key=lambda c: c.get("score", 0), reverse=True)

    avg_composite = 0.0
    if results:
        avg_composite = round(
            sum(v["signals"]["composite_signal"] for v in results) / len(results),
            2,
        )

    return {
        "success": bool(results),
        "niche": niche_clean,
        "keywords": keywords,
        "video_count": len(results),
        "avg_composite_signal": avg_composite,
        "videos": results,
        "emerging_phrases": emerging,
        "trending_comments": flat_trending[:20],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
