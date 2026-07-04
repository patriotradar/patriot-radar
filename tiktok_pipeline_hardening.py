"""
Production hardening layer for the TikTok insights + recommendation pipeline.

Adds validation, safe scoring, comment cleaning, evidence-based insights,
and fail-safe wrappers WITHOUT replacing existing architecture or behavior.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

QUALITY_SCORE_THRESHOLD = 0.4
DEFAULT_AGE_HOURS = 168.0

_EMOJI_ONLY_RE = re.compile(
    r"^[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FE0F"
    r"\U0000200D\s\.,!?]+$",
    re.UNICODE,
)
_WORD_RE = re.compile(r"[a-z0-9']+")
_SPAM_REPEAT_RE = re.compile(r"(.+?)\1{2,}", re.IGNORECASE)

PAIN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("struggle", re.compile(r"\b(struggle|struggling|can't|cannot|hard to|difficult)\b", re.I)),
    ("confusion", re.compile(r"\b(confused|don't understand|dont understand|unclear)\b", re.I)),
    ("frustration", re.compile(r"\b(frustrat|annoying|sick of|tired of|hate when)\b", re.I)),
    ("question", re.compile(r"\b(how do|how does|why is|why does|what is|can someone)\b", re.I)),
    ("consistency", re.compile(r"\b(consistent|consistency|give up|quit|fall off)\b", re.I)),
]

WHO_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("beginners", re.compile(r"\b(beginner|new to|just started|first time)\b", re.I)),
    ("everyone", re.compile(r"\b(everyone|anyone|people|nobody)\b", re.I)),
    ("creators", re.compile(r"\b(creator|influencer|coach)\b", re.I)),
]

FORMAT_OPTIONS = ("talking_head", "voiceover", "listicle", "story", "demo")
HOOK_TYPES = ("curiosity", "pain", "authority", "shock")

CURIOSITY_PHRASES = [
    "what is this", "what's this", "wait what", "how do", "how does", "how did",
    "why is", "why does", "why did", "can someone explain", "explain this",
    "i don't understand", "i dont understand", "confused", "what happened",
    "who is", "where is", "is this real", "am i missing",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _video_identifier(video: dict[str, Any]) -> str:
    for key in ("video_id", "id", "url", "webVideoUrl", "videoUrl"):
        val = str(video.get(key) or "").strip()
        if val:
            return val
    return ""


def _video_views(video: dict[str, Any]) -> int:
    engagement = video.get("engagement") or {}
    return _safe_int(
        video.get("play_count")
        or video.get("playCount")
        or video.get("views")
        or engagement.get("play_count")
        or engagement.get("playCount")
        or 0
    )


def _video_likes(video: dict[str, Any]) -> int:
    engagement = video.get("engagement") or {}
    return _safe_int(
        video.get("digg_count")
        or video.get("diggCount")
        or video.get("likes")
        or video.get("like_count")
        or engagement.get("digg_count")
        or engagement.get("diggCount")
        or 0
    )


def _video_comments_count(video: dict[str, Any]) -> int:
    engagement = video.get("engagement") or {}
    comments = video.get("comments") or []
    return max(
        _safe_int(
            video.get("comment_count")
            or video.get("commentCount")
            or engagement.get("comment_count")
            or engagement.get("commentCount")
            or 0
        ),
        len(comments),
    )


def _metadata_fields_present(video: dict[str, Any]) -> tuple[int, int]:
    """Return (present_count, total_checked)."""
    checks = [
        bool(_video_identifier(video)),
        bool(str(video.get("url") or video.get("webVideoUrl") or "").strip()),
        bool(str(video.get("caption") or video.get("description") or video.get("text") or "").strip()),
        bool(str(video.get("author") or video.get("authorMeta", {}).get("name") or "").strip()),
        _video_views(video) > 0 or _video_likes(video) > 0 or _video_comments_count(video) > 0,
        bool(video.get("create_time") or video.get("createTime") or video.get("posted_at")),
    ]
    return sum(1 for c in checks if c), len(checks)


def _parse_age_hours(video: dict[str, Any]) -> tuple[float, bool]:
    """Return (age_hours, low_confidence)."""
    ts = (
        video.get("create_time")
        or video.get("createTime")
        or video.get("posted_at")
        or video.get("timestamp")
    )
    if ts is None:
        return DEFAULT_AGE_HOURS, True

    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            numeric = float(ts)
            if numeric > 1e12:
                numeric /= 1000.0
            dt = datetime.fromtimestamp(numeric, tz=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        return max(age, 0.01), False
    except (TypeError, ValueError, OSError):
        return DEFAULT_AGE_HOURS, True


def compute_quality_score(video: dict[str, Any]) -> float:
    present, total = _metadata_fields_present(video)
    return round(present / max(total, 1), 3)


def validate_videos(
    videos: list[dict[str, Any]] | None,
    *,
    threshold: float = QUALITY_SCORE_THRESHOLD,
) -> dict[str, Any]:
    """
    Data quality gate — reject low-quality videos before scoring or insights.

    Returns accepted videos, rejected videos with reasons, and gate statistics.
    Never raises.
    """
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        for video in videos or []:
            if not isinstance(video, dict):
                rejected.append({"video": video, "reason": "invalid_type"})
                continue

            identifier = _video_identifier(video)
            url = str(video.get("url") or video.get("webVideoUrl") or "").strip()
            caption = str(
                video.get("caption") or video.get("description") or video.get("text") or ""
            ).strip()

            views = _video_views(video)
            likes = _video_likes(video)
            comments = _video_comments_count(video)
            has_caption = bool(caption)

            if not identifier and not url and not has_caption:
                rejected.append({"video": video, "reason": "missing_identifier_and_url"})
                continue

            if views <= 0 and likes <= 0 and comments <= 0 and not has_caption:
                rejected.append({"video": video, "reason": "no_engagement_metrics"})
                continue

            present, total = _metadata_fields_present(video)
            if present == 0 or (not caption and not url and not identifier):
                rejected.append({"video": video, "reason": "empty_metadata"})
                continue

            quality_score = round(present / max(total, 1), 3)
            if has_caption and not (views or likes or comments):
                quality_score = max(quality_score, 0.5)
            enriched = {**video, "quality_score": quality_score}

            if quality_score <= threshold:
                rejected.append({
                    "video": enriched,
                    "reason": "quality_below_threshold",
                    "quality_score": quality_score,
                })
                continue

            accepted.append(enriched)
    except Exception as exc:
        logger.exception("validate_videos failed: %s", exc)
        errors.append(str(exc))

    return {
        "accepted": accepted,
        "rejected": rejected,
        "stats": {
            "input_count": len(videos or []),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "threshold": threshold,
        },
        "errors": errors,
    }


def compute_trend_score(video: dict[str, Any]) -> dict[str, Any]:
    """
    Safe trend scoring: velocity + engagement + freshness.

    Preserves existing virality fields on the video; adds trend_score overlay.
    """
    views = max(_video_views(video), 0)
    likes = max(_video_likes(video), 0)
    comments = max(_video_comments_count(video), 0)
    age_hours, low_confidence = _parse_age_hours(video)

    age_denom = max(age_hours, 1.0)
    views_denom = max(views, 1)

    velocity_score = round(views / age_denom, 4)
    engagement_score = round((likes + comments) / views_denom, 4)
    freshness_score = round(1.0 / age_denom, 4)
    trend_score = round(velocity_score + engagement_score + freshness_score, 4)

    return {
        "video_id": _video_identifier(video),
        "url": str(video.get("url") or video.get("webVideoUrl") or ""),
        "trend_score": trend_score,
        "velocity_score": velocity_score,
        "engagement_score": engagement_score,
        "freshness_score": freshness_score,
        "age_hours": round(age_hours, 2),
        "low_confidence": low_confidence,
        "quality_score": video.get("quality_score") or compute_quality_score(video),
        "views": views,
        "likes": likes,
        "comments": comments,
    }


def compute_trend_scores(videos: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Batch trend scoring with per-item fail-safe."""
    scores: list[dict[str, Any]] = []
    for video in videos or []:
        try:
            scores.append(compute_trend_score(video))
        except Exception as exc:
            logger.warning("trend_score skipped for video: %s", exc)
    return scores


def _comment_text(comment: dict[str, Any]) -> str:
    return str(
        comment.get("comment_text")
        or comment.get("text")
        or comment.get("content")
        or ""
    ).strip()


def _is_emoji_only(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if _WORD_RE.search(stripped.lower()):
        return False
    return bool(_EMOJI_ONLY_RE.match(stripped)) or not stripped.isascii()


def _is_spam_like(text: str) -> bool:
    lowered = text.lower().strip()
    if len(lowered) < 6:
        return False
    if _SPAM_REPEAT_RE.search(lowered):
        return True
    tokens = lowered.split()
    if len(tokens) >= 3:
        counts = Counter(tokens)
        if counts and counts.most_common(1)[0][1] >= 3 and len(counts) <= 2:
            return True
    return False


def clean_comments(comments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Comment cleaning layer — removes noise before insights generation.

    Removes emoji-only, short, duplicate, and spam-like comments.
    Normalizes text to lowercase in output.
    """
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        for comment in comments or []:
            if not isinstance(comment, dict):
                continue
            raw = _comment_text(comment)
            if len(raw) < 3:
                continue
            if _is_emoji_only(raw):
                continue
            if _is_spam_like(raw):
                continue

            normalized = raw.lower()
            if normalized in seen:
                continue
            seen.add(normalized)

            out = dict(comment)
            out["comment_text"] = normalized
            out["text"] = normalized
            cleaned.append(out)
    except Exception as exc:
        logger.exception("clean_comments failed: %s", exc)

    return cleaned


def _confidence_from_count(count: int) -> str:
    if count >= 10:
        return "high"
    if count >= 3:
        return "medium"
    return "low"


def _detect_who(text: str, niche: str) -> str:
    for label, pattern in WHO_PATTERNS:
        if pattern.search(text):
            return label
    if niche:
        return f"people in {niche}"
    return "viewers"


def _detect_problem(text: str) -> str | None:
    for label, pattern in PAIN_PATTERNS:
        if pattern.search(text):
            return label
    if "?" in text:
        return "unanswered questions"
    return None


def _build_insight_text(who: str, problem: str, context: str) -> str:
    return f"{who} {problem} {context}".strip()


def generate_insights(
    videos: list[dict[str, Any]] | None,
    comments: list[dict[str, Any]] | None,
    niche: str = "",
) -> list[dict[str, Any]]:
    """
    Evidence-based insights from cleaned comments and video context.

    Every insight includes evidence_count, confidence, and based_on_examples.
    Insights follow WHO + PROBLEM + CONTEXT structure.
    """
    insights: list[dict[str, Any]] = []
    niche_clean = (niche or "").strip().lower()

    try:
        comment_texts = [_comment_text(c) for c in (comments or []) if _comment_text(c)]
        if not comment_texts:
            return []

        phrase_evidence: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "examples": [],
                "video_ids": set(),
                "comments": [],
            }
        )

        video_by_id = {
            _video_identifier(v): v for v in (videos or []) if _video_identifier(v)
        }

        for comment in comments or []:
            text = _comment_text(comment)
            if not text:
                continue
            tokens = [t for t in _WORD_RE.findall(text.lower()) if len(t) > 2]
            for n in (2, 3):
                for i in range(len(tokens) - n + 1):
                    phrase = " ".join(tokens[i : i + n])
                    bucket = phrase_evidence[phrase]
                    bucket["count"] += 1
                    bucket["comments"].append(text)
                    if len(bucket["examples"]) < 5:
                        bucket["examples"].append(text[:160])
                    vid = str(comment.get("video_id") or "")
                    if vid:
                        bucket["video_ids"].add(vid)

        for phrase, data in sorted(
            phrase_evidence.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        ):
            evidence_count = data["count"]
            if evidence_count < 1:
                continue

            sample_comment = data["comments"][0] if data["comments"] else phrase
            who = _detect_who(sample_comment, niche_clean)
            problem = _detect_problem(sample_comment)
            if not problem:
                if any(p in sample_comment for p in CURIOSITY_PHRASES):
                    problem = "have unanswered questions about"
                else:
                    problem = "repeatedly mention"
            context = f'"{phrase}" in comments'

            insight_text = _build_insight_text(who, problem, context)
            confidence = _confidence_from_count(evidence_count)

            insights.append({
                "insight": insight_text,
                "evidence_count": evidence_count,
                "confidence": confidence,
                "based_on_examples": list(data["examples"]),
                "phrase": phrase,
                "video_count": len(data["video_ids"]),
            })

        question_insights: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "examples": [], "video_ids": set()}
        )
        for text in comment_texts:
            if not any(p in text.lower() for p in CURIOSITY_PHRASES) and "?" not in text:
                continue
            key = text[:120].lower()
            bucket = question_insights[key]
            bucket["count"] += 1
            if len(bucket["examples"]) < 5:
                bucket["examples"].append(text[:160])

        for text_key, data in question_insights.items():
            if data["count"] < 1:
                continue
            who = _detect_who(text_key, niche_clean)
            insight_text = _build_insight_text(
                who,
                "ask questions about",
                text_key[:80],
            )
            insights.append({
                "insight": insight_text,
                "evidence_count": data["count"],
                "confidence": _confidence_from_count(data["count"]),
                "based_on_examples": list(data["examples"]),
                "type": "question",
                "video_count": len(data["video_ids"]),
            })

        for video in videos or []:
            caption = str(video.get("caption") or video.get("description") or "").strip()
            if not caption:
                continue
            vid_comments = [
                _comment_text(c)
                for c in (video.get("comments") or [])
                if _comment_text(c)
            ]
            if len(vid_comments) < 3:
                continue
            who = _detect_who(caption, niche_clean)
            problem = _detect_problem(caption) or "discuss topics around"
            context = f'video "{caption[:60]}"'
            insights.append({
                "insight": _build_insight_text(who, problem, context),
                "evidence_count": len(vid_comments),
                "confidence": _confidence_from_count(len(vid_comments)),
                "based_on_examples": vid_comments[:5],
                "type": "video_context",
                "video_id": _video_identifier(video),
                "video_count": 1,
            })

        insights = [i for i in insights if i.get("evidence_count", 0) > 0]
        insights.sort(key=lambda x: x.get("evidence_count", 0), reverse=True)
    except Exception as exc:
        logger.exception("generate_insights failed: %s", exc)

    return insights


def validate_insights(
    insights: list[dict[str, Any]] | None,
    comments: list[dict[str, Any]] | None,
    videos: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Insight validation — keep only insights with cross-comment or cross-video support.

    Keeps insights that appear in 3+ comments, across 2+ videos, or in high-engagement clusters.
    """
    if not insights:
        return []

    validated: list[dict[str, Any]] = []
    comment_texts = [_comment_text(c).lower() for c in (comments or []) if _comment_text(c)]

    try:
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            evidence_count = int(insight.get("evidence_count") or 0)
            if evidence_count <= 0:
                continue

            phrase = str(insight.get("phrase") or "").lower()
            insight_text = str(insight.get("insight") or "").lower()
            video_count = int(insight.get("video_count") or 0)

            matching_comments = 0
            for text in comment_texts:
                if phrase and phrase in text:
                    matching_comments += 1
                elif insight_text and any(
                    word in text for word in insight_text.split() if len(word) > 4
                ):
                    matching_comments += 1

            examples = insight.get("based_on_examples") or []
            example_hits = sum(
                1
                for ex in examples
                if any(ex.lower() in t or t in ex.lower() for t in comment_texts[:200])
            )

            cross_comment = max(matching_comments, example_hits, evidence_count)
            cross_video = video_count >= 2

            high_engagement = False
            if videos:
                for video in videos:
                    likes = _video_likes(video)
                    views = _video_views(video)
                    if views > 10000 or likes > 500:
                        cap = str(video.get("caption") or "").lower()
                        if phrase and phrase in cap:
                            high_engagement = True
                            break

            if cross_comment >= 3 or cross_video or high_engagement:
                validated.append(insight)
            elif evidence_count >= 10:
                validated.append(insight)
    except Exception as exc:
        logger.exception("validate_insights failed: %s", exc)
        return [i for i in (insights or []) if i.get("evidence_count", 0) >= 10]

    return validated


def generate_post_recommendations(
    insights: list[dict[str, Any]] | None,
    videos: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Hardened post recommendation module.

    Never runs on empty insights. Never blocks pipeline. Always returns a safe dict.
    """
    empty = {"recommended_posts": []}

    try:
        if not insights:
            return empty

        recommendations: list[dict[str, Any]] = []
        formats_cycle = list(FORMAT_OPTIONS)
        hooks_cycle = list(HOOK_TYPES)

        for idx, insight in enumerate(insights[:8]):
            if not isinstance(insight, dict):
                continue
            insight_text = str(insight.get("insight") or "").strip()
            if not insight_text:
                continue

            examples = insight.get("based_on_examples") or []
            target_pain = insight_text
            fmt = formats_cycle[idx % len(formats_cycle)]
            hook_type = hooks_cycle[idx % len(hooks_cycle)]

            if "question" in insight_text.lower() or insight.get("type") == "question":
                hook = f"Everyone's asking this — here's the real answer about {insight_text[:50]}"
                title = f"Answer the #1 question your audience keeps asking"
            elif "struggle" in insight_text.lower() or hook_type == "pain":
                hook = f"If you've ever felt stuck, this is why — and how to fix it"
                title = f"Solve the pain point: {insight_text[:60]}"
            else:
                hook = f"Nobody talks about this — but your comments prove it matters"
                title = f"Content idea grounded in audience signals"

            script_outline = [
                f"Hook: {hook}",
                f"Context: Reference real audience language — {examples[0][:80] if examples else insight_text[:80]}",
                "Problem: Name the specific struggle viewers expressed in comments",
                "Solution: Deliver 2-3 actionable steps tied to the pain point",
                "CTA: Ask viewers to comment with their experience",
            ]

            recommendations.append({
                "title": title,
                "hook": hook,
                "script_outline": script_outline,
                "why_it_works": (
                    f"Grounded in {insight.get('evidence_count', 0)} comment signals "
                    f"with {insight.get('confidence', 'medium')} confidence"
                ),
                "target_pain_point": target_pain,
                "format": fmt,
                "based_on": [insight_text] + examples[:2],
                "hook_type": hook_type,
            })

        return {"recommended_posts": recommendations}
    except Exception as exc:
        logger.exception("generate_post_recommendations failed: %s", exc)
        return empty


def empty_pipeline_response() -> dict[str, Any]:
    """Safe default API response — no null values."""
    return {
        "videos": [],
        "insights": [],
        "recommended_posts": [],
        "trend_scores": [],
        "trending_products": [],
        "errors": [],
    }


def build_safe_pipeline_response(
    *,
    videos: list[dict[str, Any]] | None = None,
    insights: list[dict[str, Any]] | None = None,
    recommended_posts: list[dict[str, Any]] | None = None,
    trend_scores: list[dict[str, Any]] | None = None,
    trending_products: list[dict[str, Any]] | None = None,
    errors: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Output safety contract — always returns complete structure."""
    response = {
        "videos": list(videos or []),
        "insights": list(insights or []),
        "recommended_posts": list(recommended_posts or []),
        "trend_scores": list(trend_scores or []),
        "trending_products": list(trending_products or []),
        "errors": list(errors or []),
    }
    if extra:
        for key, value in extra.items():
            if value is not None:
                response[key] = value
    return response
