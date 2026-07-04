"""
Early virality prediction engine for TikTok comment intelligence.

Computes multi-signal virality scores at query time from raw comment data.
Isolated from the TikTok trend pipeline — reads niche_comment_raw only.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from niche_comment_signal_processor import (
    CURIOSITY_PHRASES,
    NICHE_SYNONYMS,
    build_niche_keywords,
    group_raw_rows_by_video,
)

_WORD_RE = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "is", "it", "this", "that", "with", "as", "be", "are", "was",
    "were", "i", "you", "he", "she", "they", "we", "my", "your", "so",
})

CONTROVERSY_PHRASES = [
    "this is fake", "its fake", "it's fake", "no way", "this doesn't work",
    "doesnt work", "doesn't work", "cap", "that's cap", "thats cap",
    "not real", "is this real", "scam", "clickbait", "misleading",
    "wrong", "that's wrong", "thats wrong", "disagree", "nah",
    "stop lying", "liar", "bull", "bs", "skeptical", "doubt",
    "doesn't make sense", "doesnt make sense", "fake news",
]

GENERIC_NOISE = frozenset({
    "nice", "cool", "lol", "lmao", "haha", "wow", "omg", "yes", "no",
    "ok", "okay", "true", "same", "fr", "real", "fire", "slay", "yep",
    "nope", "yeah", "nah", "first", "early", "following", "follow",
    "part", "pov", "fyp", "foryou", "foryoupage",
})

VIRALITY_WEIGHTS = {
    "velocity": 0.25,
    "acceleration": 0.20,
    "cross_video": 0.20,
    "niche_relevance": 0.20,
    "curiosity": 0.15,
}

MIN_COMMENTS_PER_VIDEO = 3
MIN_NICHE_RELEVANCE = 15.0
MIN_COMMENT_LENGTH = 4


def _tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def _ngrams(tokens: list[str], n: int) -> list[str]:
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _parse_timestamp(comment: dict[str, Any]) -> float | None:
    ts = comment.get("commented_at") or comment.get("create_time")
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def _filter_signal_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove low-signal noise comments."""
    filtered: list[dict[str, Any]] = []
    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").strip()
        if len(text) < MIN_COMMENT_LENGTH:
            continue
        tokens = _tokenize(text)
        if not tokens:
            continue
        if len(tokens) == 1 and tokens[0] in GENERIC_NOISE:
            continue
        if all(t in GENERIC_NOISE for t in tokens):
            continue
        filtered.append(comment)
    return filtered


def _velocity_and_acceleration(comments: list[dict[str, Any]]) -> dict[str, float]:
    """
    Compute comment velocity (per hour) and acceleration (change in velocity).
    Does not rely on total comment counts — uses time-bucketed rates.
    """
    timestamps: list[float] = []
    for comment in comments:
        ts = _parse_timestamp(comment)
        if ts is not None:
            timestamps.append(ts)

    if not timestamps:
        return {"velocity_per_hour": 0.0, "velocity_score": 0.0, "acceleration_score": 0.0, "acceleration_raw": 0.0}

    timestamps.sort()
    span_seconds = max(timestamps[-1] - timestamps[0], 60.0)
    span_hours = span_seconds / 3600.0

    overall_velocity = len(timestamps) / span_hours

    mid = timestamps[0] + span_seconds / 2.0
    early = [t for t in timestamps if t <= mid]
    recent = [t for t in timestamps if t > mid]

    early_span = max((mid - timestamps[0]) / 3600.0, 0.25) if early else 0.25
    recent_span = max((timestamps[-1] - mid) / 3600.0, 0.25) if recent else 0.25

    early_velocity = len(early) / early_span if early else 0.0
    recent_velocity = len(recent) / recent_span if recent else 0.0

    if early_velocity > 0:
        acceleration_raw = ((recent_velocity - early_velocity) / early_velocity) * 100.0
    elif recent_velocity > 0:
        acceleration_raw = 100.0
    else:
        acceleration_raw = 0.0

    velocity_score = round(min(100.0, (overall_velocity / 50.0) * 100.0), 2)

    if acceleration_raw >= 50:
        acceleration_score = min(100.0, 60.0 + (acceleration_raw - 50) * 0.8)
    elif acceleration_raw >= 0:
        acceleration_score = min(100.0, 40.0 + acceleration_raw * 0.4)
    else:
        acceleration_score = max(0.0, 40.0 + acceleration_raw * 0.5)

    return {
        "velocity_per_hour": round(overall_velocity, 2),
        "velocity_score": velocity_score,
        "acceleration_score": round(acceleration_score, 2),
        "acceleration_raw": round(acceleration_raw, 2),
    }


def _semantic_niche_relevance(
    comments: list[dict[str, Any]],
    caption: str,
    niche: str,
    keywords: list[str],
) -> float:
    """
    Context-aware niche matching beyond strict keyword hits.
    Uses token overlap, synonym groups, and prefix similarity.
    """
    if not niche.strip():
        return 0.0

    niche_tokens = set(_tokenize(niche))
    keyword_tokens: set[str] = set()
    for kw in keywords:
        keyword_tokens.update(_tokenize(kw))

    semantic_profile = niche_tokens | keyword_tokens
    for token in list(niche_tokens):
        for syn_list in NICHE_SYNONYMS.values():
            if token in syn_list:
                semantic_profile.update(syn_list)
        if token in NICHE_SYNONYMS:
            semantic_profile.update(NICHE_SYNONYMS[token])

    texts = [caption] + [
        (c.get("comment_text") or c.get("text") or "") for c in comments
    ]
    combined_tokens: set[str] = set()
    for text in texts:
        combined_tokens.update(_tokenize(text))

    if not combined_tokens:
        return 0.0

    overlap = len(combined_tokens & semantic_profile)
    union = len(combined_tokens | semantic_profile)
    jaccard = (overlap / union) * 100.0 if union else 0.0

    keyword_hits = 0
    combined_lower = " ".join(texts).lower()
    for kw in keywords:
        if kw.lower() in combined_lower:
            keyword_hits += 1
    keyword_score = min(100.0, (keyword_hits / max(len(keywords), 1)) * 100.0)

    prefix_matches = 0
    for ct in combined_tokens:
        for st in semantic_profile:
            if len(st) >= 4 and len(ct) >= 4 and (ct.startswith(st[:4]) or st.startswith(ct[:4])):
                prefix_matches += 1
                break
    prefix_bonus = min(15.0, prefix_matches * 3.0)

    comment_matches = 0
    for comment in comments:
        ctokens = set(_tokenize((comment.get("comment_text") or comment.get("text") or "")))
        if ctokens & semantic_profile:
            comment_matches += 1
    density_bonus = min(15.0, (comment_matches / max(len(comments), 1)) * 15.0)

    raw = jaccard * 0.35 + keyword_score * 0.40 + prefix_bonus + density_bonus
    return round(min(100.0, raw), 2)


def _curiosity_score(comments: list[dict[str, Any]]) -> float:
    if not comments:
        return 0.0
    matches = 0
    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").lower()
        if any(p in text for p in CURIOSITY_PHRASES):
            matches += 1
    return round(min(100.0, (matches / len(comments)) * 100.0), 2)


def _controversy_score(comments: list[dict[str, Any]]) -> float:
    if not comments:
        return 0.0
    matches = 0
    for comment in comments:
        text = (comment.get("comment_text") or comment.get("text") or "").lower()
        if any(p in text for p in CONTROVERSY_PHRASES):
            matches += 1
    return round(min(100.0, (matches / len(comments)) * 100.0), 2)


def _build_cross_video_clusters(
    videos: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """
    Detect repeated phrases across multiple videos.
    Returns phrase lookup and ranked cross-video clusters.
    """
    phrase_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "video_ids": set(), "videos": []}
    )

    for video in videos:
        video_id = str(video.get("video_id") or "")
        comments = video.get("comments") or []
        local_phrases: Counter[str] = Counter()
        for comment in comments:
            text = (comment.get("comment_text") or comment.get("text") or "").strip()
            tokens = _tokenize(text)
            for n in (2, 3):
                for gram in _ngrams(tokens, n):
                    local_phrases[gram] += 1

        for phrase, count in local_phrases.items():
            if count < 2:
                continue
            phrase_data[phrase]["count"] += count
            phrase_data[phrase]["video_ids"].add(video_id)
            phrase_data[phrase]["videos"].append({
                "video_id": video_id,
                "video_url": video.get("url") or "",
                "author": video.get("author") or "",
            })

    clusters: list[dict[str, Any]] = []
    for phrase, data in phrase_data.items():
        video_count = len(data["video_ids"])
        if video_count < 2:
            continue
        cross_score = min(100.0, video_count * 25.0 + min(data["count"], 20) * 2.5)
        clusters.append({
            "phrase": phrase,
            "total_count": data["count"],
            "video_count": video_count,
            "cross_video_score": round(cross_score, 2),
            "video_ids": list(data["video_ids"]),
        })

    clusters.sort(key=lambda c: (c["cross_video_score"], c["video_count"]), reverse=True)
    return dict(phrase_data), clusters


def _cross_video_score_for_video(
    video_id: str,
    phrases: list[dict[str, Any]],
    phrase_lookup: dict[str, dict[str, Any]],
) -> float:
    if not phrases:
        return 0.0
    scores: list[float] = []
    for p in phrases:
        data = phrase_lookup.get(p.get("phrase", ""))
        if data and len(data["video_ids"]) >= 2:
            vc = len(data["video_ids"])
            scores.append(min(100.0, vc * 25.0 + min(data["count"], 20) * 2.5))
    return round(sum(scores) / len(scores), 2) if scores else 0.0


def _virality_score(
    velocity: float,
    acceleration: float,
    cross_video: float,
    niche: float,
    curiosity: float,
) -> float:
    raw = (
        velocity * VIRALITY_WEIGHTS["velocity"]
        + acceleration * VIRALITY_WEIGHTS["acceleration"]
        + cross_video * VIRALITY_WEIGHTS["cross_video"]
        + niche * VIRALITY_WEIGHTS["niche_relevance"]
        + curiosity * VIRALITY_WEIGHTS["curiosity"]
    )
    return round(min(100.0, raw), 2)


def _early_warning_level(virality_score: float, velocity: float, acceleration: float) -> dict[str, Any]:
    if virality_score >= 75 or (velocity >= 70 and acceleration >= 50):
        level = 4
        label = "Viral Now"
        color = "#ef4444"
    elif virality_score >= 50 or (velocity >= 45 and acceleration >= 35):
        level = 3
        label = "Breakout Candidate"
        color = "#f97316"
    elif virality_score >= 25 or velocity >= 20 or acceleration >= 20:
        level = 2
        label = "Warming"
        color = "#fbbf24"
    else:
        level = 1
        label = "Noise"
        color = "#6b7280"

    return {"level": level, "label": label, "color": color}


def _time_to_viral_status(
    velocity: float,
    acceleration: float,
    virality_score: float,
    acceleration_raw: float,
) -> dict[str, str]:
    if virality_score >= 75 and velocity >= 60:
        return {"status": "already_viral", "label": "Already Viral", "color": "#ef4444"}
    if acceleration_raw >= 30 and velocity >= 25:
        return {"status": "likely_viral_soon", "label": "Likely Viral Soon", "color": "#22c55e"}
    if acceleration_raw < -20 and velocity >= 30:
        return {"status": "fading", "label": "Fading", "color": "#94a3b8"}
    if virality_score < 20 and velocity < 15:
        return {"status": "low_potential", "label": "Low Potential", "color": "#6b7280"}
    if acceleration_raw >= 10:
        return {"status": "likely_viral_soon", "label": "Likely Viral Soon", "color": "#22c55e"}
    return {"status": "low_potential", "label": "Low Potential", "color": "#6b7280"}


def _top_repeated_phrases(comments: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
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


def compute_virality_predictions(
    raw_rows: list[dict[str, Any]],
    niche: str,
    *,
    min_relevance: float = MIN_NICHE_RELEVANCE,
) -> dict[str, Any]:
    """
    Multi-signal early virality prediction from raw comment rows.

    Returns ranked trends with virality scores, warning levels, and cross-video clusters.
    """
    niche_clean = (niche or "").strip()
    keywords = build_niche_keywords(niche_clean)

    if not niche_clean:
        return {
            "success": False,
            "error": "niche_required",
            "niche": "",
            "keywords": [],
            "trends": [],
            "cross_video_clusters": [],
            "video_count": 0,
        }

    videos = group_raw_rows_by_video(raw_rows)
    if not videos:
        return {
            "success": False,
            "error": "no_raw_comments",
            "niche": niche_clean,
            "keywords": keywords,
            "trends": [],
            "cross_video_clusters": [],
            "video_count": 0,
        }

    filtered_videos: list[dict[str, Any]] = []
    for video in videos:
        comments = _filter_signal_comments(video.get("comments") or [])
        if len(comments) < MIN_COMMENTS_PER_VIDEO:
            continue
        filtered_videos.append({**video, "comments": comments})

    phrase_lookup, cross_clusters = _build_cross_video_clusters(filtered_videos)

    results: list[dict[str, Any]] = []

    for video in filtered_videos:
        comments = video.get("comments") or []
        caption = video.get("caption") or ""
        video_id = str(video.get("video_id") or "")

        motion = _velocity_and_acceleration(comments)
        relevance = _semantic_niche_relevance(comments, caption, niche_clean, keywords)
        if relevance < min_relevance:
            continue

        curiosity = _curiosity_score(comments)
        controversy = _controversy_score(comments)
        phrases = _top_repeated_phrases(comments)
        cross_video = _cross_video_score_for_video(video_id, phrases, phrase_lookup)

        virality = _virality_score(
            motion["velocity_score"],
            motion["acceleration_score"],
            cross_video,
            relevance,
            curiosity,
        )

        warning = _early_warning_level(
            virality, motion["velocity_score"], motion["acceleration_score"]
        )
        viral_status = _time_to_viral_status(
            motion["velocity_score"],
            motion["acceleration_score"],
            virality,
            motion["acceleration_raw"],
        )

        results.append({
            "video_id": video_id,
            "video_url": video.get("url") or "",
            "author": video.get("author") or "",
            "caption_preview": caption[:200],
            "comments_analyzed": len(comments),
            "virality_score": virality,
            "early_warning": warning,
            "time_to_viral": viral_status,
            "signals": {
                "velocity_per_hour": motion["velocity_per_hour"],
                "velocity_score": motion["velocity_score"],
                "acceleration_score": motion["acceleration_score"],
                "acceleration_raw": motion["acceleration_raw"],
                "cross_video_score": cross_video,
                "niche_relevance_score": relevance,
                "curiosity_score": curiosity,
                "controversy_score": controversy,
            },
            "top_repeated_phrases": phrases,
        })

    results.sort(key=lambda r: r["virality_score"], reverse=True)

    niche_clusters = [
        c for c in cross_clusters
        if any(kw in c["phrase"] for kw in keywords)
    ][:15]
    if not niche_clusters:
        niche_clusters = cross_clusters[:15]

    cluster_trends: list[dict[str, Any]] = []
    for cluster in niche_clusters:
        cluster_virality = min(100.0, cluster["cross_video_score"] * 0.6 + cluster["video_count"] * 8)
        warning = _early_warning_level(cluster_virality, cluster["cross_video_score"], 30.0)
        cluster_trends.append({
            "topic": cluster["phrase"],
            "type": "cross_video_cluster",
            "virality_score": round(cluster_virality, 2),
            "early_warning": warning,
            "video_count": cluster["video_count"],
            "total_mentions": cluster["total_count"],
            "cross_video_score": cluster["cross_video_score"],
        })

    cluster_trends.sort(key=lambda t: t["virality_score"], reverse=True)

    ranked_trends: list[dict[str, Any]] = []
    for r in results:
        ranked_trends.append({
            "type": "video",
            "topic": r["caption_preview"][:80] or f"Video {r['video_id']}",
            "virality_score": r["virality_score"],
            "early_warning": r["early_warning"],
            "time_to_viral": r["time_to_viral"],
            "video_id": r["video_id"],
            "video_url": r["video_url"],
            "author": r["author"],
            "signals": r["signals"],
        })

    for ct in cluster_trends[:10]:
        ranked_trends.append({
            "type": "cluster",
            "topic": ct["topic"],
            "virality_score": ct["virality_score"],
            "early_warning": ct["early_warning"],
            "video_count": ct["video_count"],
            "total_mentions": ct["total_mentions"],
            "signals": {"cross_video_score": ct["cross_video_score"]},
        })

    ranked_trends.sort(key=lambda t: t["virality_score"], reverse=True)

    return {
        "success": bool(results),
        "niche": niche_clean,
        "keywords": keywords,
        "video_count": len(results),
        "videos": results,
        "cross_video_clusters": niche_clusters,
        "ranked_trends": ranked_trends[:25],
        "weights": VIRALITY_WEIGHTS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def load_sample_rows(path: str) -> list[dict[str, Any]]:
    """Convert sample JSON format to niche_comment_raw row format."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    rows: list[dict[str, Any]] = []
    for video in data:
        video_id = (video.get("url") or "").split("/")[-1] or "unknown"
        for comment in video.get("comments") or []:
            ts = comment.get("create_time")
            commented_at = None
            if ts is not None:
                commented_at = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            rows.append({
                "video_id": video_id,
                "video_url": video.get("url") or "",
                "video_caption": video.get("caption") or "",
                "video_author": video.get("author") or "",
                "comment_text": comment.get("text") or "",
                "comment_author": "",
                "comment_like_count": int(comment.get("like_count") or 0),
                "commented_at": commented_at,
            })
    return rows
