"""
Per-user adaptive calibration for recommendation selection.

Learns each user's evolving performance baseline from historical posts and
adjusts final candidate ranking relative to that baseline — not fixed thresholds.
"""

from __future__ import annotations

import json
import os
import re
from statistics import median

WINDOW_DEFAULT = 30
WINDOW_MIN = 20
WINDOW_MAX = 50
RECENT_SHIFT_WINDOW = 8

GLOBAL_DEFAULT_BASELINE = {
    "views": 300.0,
    "engagement": 1.0,
    "post_count": 0,
    "insufficient": True,
    "source": "global_default",
}

CLASSIFICATION_WEIGHTS = {
    "BREAKOUT": 2.0,
    "STRONG": 1.0,
    "NORMAL": 0.0,
    "BELOW_EXPECTATION": -1.0,
}


def _clamp_window(post_count: int) -> int:
    if post_count <= WINDOW_MIN:
        return post_count
    return min(WINDOW_MAX, max(WINDOW_MIN, min(WINDOW_DEFAULT, post_count)))


def post_engagement_rate(post: dict) -> float:
    views = float(post.get("views", 0) or 0)
    if views <= 0:
        return 0.0
    likes = float(post.get("likes", 0) or 0)
    comments = float(post.get("comments", 0) or 0)
    shares = float(post.get("shares", 0) or 0)
    return ((likes + comments * 3 + shares * 5) / views) * 100


def flatten_performance_posts(performance) -> list[dict]:
    """Normalize cr_analytics rows, audienceModel lists, or keyword-keyed performance dicts."""
    if not performance:
        return []

    if isinstance(performance, list):
        return [p for p in performance if isinstance(p, dict)]

    if not isinstance(performance, dict):
        return []

    entries: list[dict] = []
    for key, value in performance.items():
        if isinstance(value, list):
            for post in value:
                if not isinstance(post, dict):
                    continue
                entry = dict(post)
                if not entry.get("keyword"):
                    entry["keyword"] = key
                entries.append(entry)
        elif isinstance(value, dict) and ("views" in value or "likes" in value):
            entry = dict(value)
            if not entry.get("keyword"):
                entry["keyword"] = key
            entries.append(entry)

    return entries


def load_performance_posts() -> list[dict]:
    """Load optional per-user post history from env or local JSON (no schema changes)."""
    raw = os.getenv("PERFORMANCE_JSON")
    if raw:
        try:
            return flatten_performance_posts(json.loads(raw))
        except json.JSONDecodeError:
            pass

    for path in ("performance_posts.json", "performance.json"):
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return flatten_performance_posts(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue
    return []


def breakout_multiplier(post_count: int) -> float:
    if post_count < 10:
        return 2.0
    if post_count < 25:
        return 2.5
    return 3.0


def compute_user_baseline(posts: list[dict], engagement_metrics: dict | None = None) -> dict:
    """Rolling baseline from the last 20–50 posts; falls back to global defaults."""
    valid = [p for p in posts if float(p.get("views", 0) or 0) > 0]
    window = _clamp_window(len(valid))
    recent = valid[-window:] if window else []

    if len(recent) >= 3:
        view_samples = [float(p.get("views", 0) or 0) for p in recent]
        rate_samples = [post_engagement_rate(p) for p in recent]
        return {
            "views": float(median(view_samples)),
            "engagement": float(median(rate_samples)) if rate_samples else GLOBAL_DEFAULT_BASELINE["engagement"],
            "post_count": len(recent),
            "insufficient": False,
            "source": "user_posts",
        }

    if engagement_metrics:
        avg_views = float(engagement_metrics.get("avg_views", 0) or 0)
        avg_rate = engagement_metrics.get("engagement_rate")
        if avg_views > 0:
            return {
                "views": avg_views,
                "engagement": float(avg_rate) if avg_rate is not None else GLOBAL_DEFAULT_BASELINE["engagement"],
                "post_count": int(engagement_metrics.get("post_count", 0) or 0),
                "insufficient": len(recent) < 3,
                "source": "engagement_metrics_aggregate",
            }

    return dict(GLOBAL_DEFAULT_BASELINE)


def classify_post_performance(post: dict, baseline: dict) -> str:
    """Internal label relative to the user's baseline only."""
    views = float(post.get("views", 0) or 0)
    rate = post_engagement_rate(post)
    base_views = max(float(baseline.get("views", 0) or 0), 1.0)
    base_rate = max(float(baseline.get("engagement", 0) or 0), 0.01)
    multiplier = breakout_multiplier(int(baseline.get("post_count", 0) or 0))

    breakout_views = base_views * multiplier
    strong_views = base_views * 1.25
    below_views = base_views * 0.75

    if views >= breakout_views and rate >= base_rate * 1.1:
        return "BREAKOUT"
    if views >= strong_views or rate >= base_rate * 1.15:
        return "STRONG"
    if views < below_views and rate < base_rate * 0.85:
        return "BELOW_EXPECTATION"
    return "NORMAL"


def detect_baseline_shift(posts: list[dict], baseline: dict) -> dict:
    """
    If recent posts consistently underperform, weight recent behaviour more heavily
    so outdated strong patterns do not dominate selection.
    """
    valid = [p for p in posts if float(p.get("views", 0) or 0) > 0]
    recent = valid[-RECENT_SHIFT_WINDOW:]
    if len(recent) < 5:
        return {
            "shift_detected": False,
            "recent_weight": 0.4,
            "legacy_weight": 0.6,
        }

    below = sum(
        1 for post in recent if classify_post_performance(post, baseline) == "BELOW_EXPECTATION"
    )
    ratio = below / len(recent)
    if ratio >= 0.6:
        return {
            "shift_detected": True,
            "recent_weight": 0.75,
            "legacy_weight": 0.25,
        }
    if ratio >= 0.4:
        return {
            "shift_detected": True,
            "recent_weight": 0.6,
            "legacy_weight": 0.4,
        }
    return {
        "shift_detected": False,
        "recent_weight": 0.4,
        "legacy_weight": 0.6,
    }


def _normalize_format_label(raw: str) -> str:
    lowered = (raw or "").lower().strip()
    if not lowered:
        return ""
    if "yes/no" in lowered or "debate" in lowered:
        return "debate"
    if "opinion" in lowered or "hot take" in lowered:
        return "opinion"
    if "story" in lowered or "nostalgia" in lowered:
        return "story"
    if "educational" in lowered or "tutorial" in lowered or "explainer" in lowered:
        return "explainer"
    if "reaction" in lowered:
        return "reaction"
    return lowered.split("/")[0].strip() or lowered


def _normalize_emotion_label(post: dict) -> str:
    for key in ("emotionalTrigger", "emotion", "audienceDriver", "topic"):
        value = post.get(key)
        if value:
            return str(value).lower().strip()
    return ""


def pattern_key_from_post(post: dict) -> str:
    keyword = (post.get("keyword") or "").lower().strip()
    fmt = _normalize_format_label(post.get("format", ""))
    emotion = _normalize_emotion_label(post)
    return f"{keyword}|{fmt}|{emotion}"


def pattern_key_from_candidate(item: dict, engagement_signal: str = "HEALTHY") -> str:
    keyword = (item.get("keyword") or "").lower().strip()
    debate = int(item.get("debate", 0) or 0)
    emotion_score = int(item.get("emotion", 0) or 0)

    if debate >= emotion_score and debate >= 16:
        fmt = "debate"
        emotion = "debate"
    elif emotion_score >= 18:
        fmt = "opinion"
        emotion = "pride"
    elif engagement_signal == "ATTENTION_WITHOUT_VALUE":
        fmt = "explainer"
        emotion = "education"
    elif engagement_signal == "HOOK_OK_LOW_CONVERSION":
        fmt = "reaction"
        emotion = "curiosity"
    else:
        fmt = _normalize_format_label(item.get("discovery_type", "") or item.get("category", ""))
        emotion = _normalize_emotion_label(item) or "curiosity"

    return f"{keyword}|{fmt}|{emotion}"


def build_pattern_affinity(posts: list[dict], baseline: dict, shift: dict) -> dict[str, float]:
    valid = [p for p in posts if float(p.get("views", 0) or 0) > 0]
    if not valid:
        return {}

    recent_cutoff = max(0, len(valid) - RECENT_SHIFT_WINDOW)
    affinity: dict[str, list[float]] = {}

    for index, post in enumerate(valid):
        label = classify_post_performance(post, baseline)
        weight = CLASSIFICATION_WEIGHTS.get(label, 0.0)
        if weight == 0.0:
            continue

        time_weight = shift["recent_weight"] if index >= recent_cutoff else shift["legacy_weight"]
        key = pattern_key_from_post(post)
        affinity.setdefault(key, []).append(weight * time_weight)

        # Topic-only bucket for partial matching when format/emotion differ.
        topic_key = f"{(post.get('keyword') or '').lower().strip()}||"
        affinity.setdefault(topic_key, []).append(weight * time_weight * 0.6)

    return {key: sum(values) / len(values) for key, values in affinity.items()}


def build_calibration_context(
    performance=None,
    engagement_metrics: dict | None = None,
) -> dict:
    posts = flatten_performance_posts(performance) if performance else load_performance_posts()
    baseline = compute_user_baseline(posts, engagement_metrics)
    shift = detect_baseline_shift(posts, baseline)
    pattern_affinity = build_pattern_affinity(posts, baseline, shift)

    return {
        "baseline": baseline,
        "shift": shift,
        "pattern_affinity": pattern_affinity,
        "breakout_multiplier": breakout_multiplier(int(baseline.get("post_count", 0) or 0)),
    }


def _keyword_overlap(candidate_keyword: str, pattern_keyword: str) -> bool:
    if not candidate_keyword or not pattern_keyword:
        return False
    if candidate_keyword == pattern_keyword:
        return True
    return candidate_keyword in pattern_keyword or pattern_keyword in candidate_keyword


def calibrated_selection_boost(item: dict, calibration_context: dict, engagement_signal: str) -> float:
    """
    Relative boost/penalty for a trend candidate based on the user's historical outcomes.
    Does not alter raw trend scores — only interpretation at selection time.
    """
    if not calibration_context:
        return 0.0

    affinity = calibration_context.get("pattern_affinity") or {}
    if not affinity:
        return 0.0

    candidate_key = pattern_key_from_candidate(item, engagement_signal)
    keyword = (item.get("keyword") or "").lower().strip()

    if candidate_key in affinity:
        return float(affinity[candidate_key])

    boost = 0.0
    matches = 0
    for pattern_key, score in affinity.items():
        parts = pattern_key.split("|")
        pattern_keyword = parts[0] if parts else ""
        pattern_format = parts[1] if len(parts) > 1 else ""
        candidate_format = candidate_key.split("|")[1] if "|" in candidate_key else ""

        if not _keyword_overlap(keyword, pattern_keyword):
            continue

        matches += 1
        boost += score
        if pattern_format and pattern_format == candidate_format:
            boost += score * 0.35

    if matches:
        return boost / matches
    return 0.0


def calibrated_rank_key(item: dict, calibration_context: dict | None, engagement_signal: str):
    """Combine trend ranking with user-calibrated pattern preference."""
    base = (
        float(item.get("opportunity_gap", 0) or 0),
        float(item.get("content_score", 0) or 0),
        float(item.get("viral_score", 0) or 0),
    )
    if not calibration_context:
        return base

    boost = calibrated_selection_boost(item, calibration_context, engagement_signal)
    scaled = boost * 2.5
    return (base[0] + scaled, base[1] + scaled * 0.5, base[2] + scaled * 0.25)
