"""
Supabase-backed niche resolution for the TikTok insights pipeline.

Resolves account niche from Supabase first, then infers from video/comment signals.
Never raises; always returns a safe default structure.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNTS_TABLE = "accounts"
CONFIDENCE_THRESHOLD = 0.7

_VALID_NICHES = frozenset({
    "fitness", "beauty", "tech", "finance", "gaming", "lifestyle", "business", "unknown",
})

_NICHE_KEYWORDS: dict[str, frozenset[str]] = {
    "fitness": frozenset({
        "gym", "workout", "fitness", "exercise", "muscle", "protein", "cardio", "squat",
        "deadlift", "bench", "reps", "sets", "training", "weight", "lifting", "abs",
        "calories", "macros", "bulk", "cut", "hiit", "yoga", "pilates", "running",
    }),
    "beauty": frozenset({
        "skincare", "makeup", "serum", "moisturizer", "cleanser", "acne", "glow", "skin",
        "foundation", "concealer", "mascara", "lipstick", "routine", "spf", "retinol",
        "collagen", "hair", "shampoo", "conditioner", "beauty", "cosmetic", "lash",
    }),
    "tech": frozenset({
        "tech", "gadget", "phone", "iphone", "android", "laptop", "computer", "app",
        "software", "ai", "coding", "developer", "startup", "review", "unboxing",
        "smartphone", "tablet", "headphones", "camera", "drone", "robot", "saas",
    }),
    "finance": frozenset({
        "finance", "money", "invest", "investing", "stock", "stocks", "crypto", "bitcoin",
        "budget", "saving", "savings", "debt", "income", "passive", "dividend", "trading",
        "portfolio", "wealth", "financial", "bank", "loan", "mortgage", "tax",
    }),
    "gaming": frozenset({
        "gaming", "game", "gamer", "playstation", "xbox", "nintendo", "steam", "twitch",
        "esports", "fortnite", "minecraft", "valorant", "cod", "fps", "rpg", "stream",
        "console", "pc", "multiplayer", "ranked", "clutch", "squad",
    }),
    "lifestyle": frozenset({
        "lifestyle", "vlog", "daily", "routine", "morning", "aesthetic", "home", "decor",
        "travel", "food", "recipe", "cooking", "fashion", "outfit", "style", "wellness",
        "mindfulness", "selfcare", "productivity", "habits", "minimalist", "grwm",
    }),
    "business": frozenset({
        "business", "entrepreneur", "startup", "marketing", "sales", "brand", "client",
        "revenue", "profit", "ecommerce", "shopify", "dropshipping", "freelance", "agency",
        "coach", "course", "linkedin", "networking", "pitch", "founder", "ceo", "sidehustle",
    }),
}

_WORD_RE = re.compile(r"[a-z0-9#]+")
_HASHTAG_RE = re.compile(r"#([a-z0-9_]+)")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _empty_niche_result() -> dict[str, Any]:
    return {"niche": "unknown", "confidence": 0.0, "keywords": []}


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    try:
        from supabase import create_client
        return create_client(supabase_url, service_role_key)
    except Exception as exc:
        logger.warning("Supabase client init failed: %s", exc)
        return None


def _accounts_table() -> str:
    return os.getenv("SUPABASE_ACCOUNTS_TABLE", DEFAULT_ACCOUNTS_TABLE)


def _fetch_account_niche(account_id: str) -> dict[str, Any] | None:
    if not account_id or account_id == "unknown":
        return None
    client = _get_supabase_client()
    if client is None:
        return None
    try:
        resp = (
            client.table(_accounts_table())
            .select("niche, niche_confidence")
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            resp = (
                client.table(_accounts_table())
                .select("niche, niche_confidence")
                .eq("account_id", account_id)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning("Supabase account niche fetch failed: %s", exc)
        return None


def _write_account_niche(account_id: str, niche: str, confidence: float) -> None:
    if not account_id or account_id == "unknown":
        return
    client = _get_supabase_client()
    if client is None:
        return
    try:
        now = datetime.now(timezone.utc).isoformat()
        update_payload = {
            "niche": niche,
            "niche_confidence": round(confidence, 4),
            "updated_at": now,
        }
        for id_field in ("id", "account_id"):
            try:
                client.table(_accounts_table()).update(update_payload).eq(id_field, account_id).execute()
                return
            except Exception:
                continue
    except Exception as exc:
        logger.warning("Supabase account niche write failed: %s", exc)


def _extract_text_signals(
    videos: list[dict[str, Any]] | None,
    comments: list[dict[str, Any]] | None,
) -> tuple[list[str], list[str], list[str]]:
    """Return (all_tokens, hashtags, top_caption_texts)."""
    tokens: list[str] = []
    hashtags: list[str] = []
    captions: list[str] = []

    for video in videos or []:
        if not isinstance(video, dict):
            continue
        caption = str(video.get("caption") or video.get("description") or video.get("text") or "")
        if caption:
            captions.append(caption.lower())
            tokens.extend(_WORD_RE.findall(caption.lower()))
            hashtags.extend(_HASHTAG_RE.findall(caption.lower()))

    for comment in comments or []:
        if not isinstance(comment, dict):
            continue
        text = str(comment.get("comment_text") or comment.get("text") or comment.get("content") or "")
        if text:
            tokens.extend(_WORD_RE.findall(text.lower()))
            hashtags.extend(_HASHTAG_RE.findall(text.lower()))

    return tokens, hashtags, captions


def _top_engagement_videos(videos: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for video in videos or []:
        if not isinstance(video, dict):
            continue
        engagement = video.get("engagement") or {}
        views = _safe_float(
            video.get("play_count") or video.get("playCount")
            or engagement.get("play_count") or engagement.get("playCount")
        )
        likes = _safe_float(
            video.get("digg_count") or video.get("diggCount") or video.get("likes")
            or engagement.get("digg_count") or engagement.get("diggCount")
        )
        comments = _safe_float(
            video.get("comment_count") or video.get("commentCount")
            or engagement.get("comment_count") or engagement.get("commentCount")
        )
        score = views + likes * 10 + comments * 5
        scored.append((score, video))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [v for _, v in scored[:5]]


def _infer_niche(
    videos: list[dict[str, Any]] | None,
    comments: list[dict[str, Any]] | None,
) -> tuple[str, float, list[str]]:
    """Infer niche from content signals. Returns (niche, confidence, keywords)."""
    top_videos = _top_engagement_videos(videos)
    tokens, hashtags, captions = _extract_text_signals(top_videos or videos, comments)

    all_tokens = tokens + hashtags
    if not all_tokens:
        return "unknown", 0.0, []

    token_counts = Counter(all_tokens)
    niche_scores: dict[str, float] = {}

    for niche, keywords in _NICHE_KEYWORDS.items():
        hits = sum(token_counts.get(kw, 0) for kw in keywords)
        if hits > 0:
            niche_scores[niche] = hits / max(len(all_tokens), 1)

    if not niche_scores:
        return "unknown", 0.0, []

    best_niche = max(niche_scores, key=niche_scores.get)  # type: ignore[arg-type]
    raw_score = niche_scores[best_niche]
    total_hits = sum(
        token_counts.get(kw, 0)
        for kw in _NICHE_KEYWORDS.get(best_niche, frozenset())
    )

    confidence = _clamp(0.3 + raw_score * 3.0 + min(total_hits, 10) * 0.05)

    top_keywords = [
        kw for kw, _ in token_counts.most_common(20)
        if kw in _NICHE_KEYWORDS.get(best_niche, frozenset())
    ][:8]

    if not top_keywords:
        top_keywords = [kw for kw, _ in token_counts.most_common(5)]

    return best_niche, round(confidence, 4), top_keywords


def resolveNiche(
    account_id: str,
    videos: list[dict[str, Any]] | None,
    comments: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Resolve account niche — Supabase first, then inference.

    Returns {"niche": str, "confidence": float, "keywords": [str]}.
    Never raises.
    """
    try:
        account_id = str(account_id or "").strip() or "unknown"

        stored = _fetch_account_niche(account_id)
        if stored:
            stored_niche = str(stored.get("niche") or "unknown").strip().lower()
            stored_confidence = _safe_float(stored.get("niche_confidence"))
            if stored_niche in _VALID_NICHES and stored_niche != "unknown":
                if stored_confidence >= CONFIDENCE_THRESHOLD:
                    return {
                        "niche": stored_niche,
                        "confidence": round(stored_confidence, 4),
                        "keywords": [],
                    }

        inferred_niche, inferred_confidence, keywords = _infer_niche(videos, comments)
        if inferred_niche not in _VALID_NICHES:
            inferred_niche = "unknown"

        should_write = False
        if stored is None:
            should_write = inferred_niche != "unknown"
        else:
            stored_confidence = _safe_float(stored.get("niche_confidence"))
            stored_niche = str(stored.get("niche") or "").strip().lower()
            if not stored_niche or stored_niche == "unknown":
                should_write = inferred_niche != "unknown"
            elif inferred_confidence > stored_confidence:
                should_write = True

        if should_write and inferred_niche != "unknown":
            _write_account_niche(account_id, inferred_niche, inferred_confidence)

        return {
            "niche": inferred_niche,
            "confidence": inferred_confidence,
            "keywords": keywords,
        }
    except Exception as exc:
        logger.warning("resolveNiche failed: %s", exc)
        return _empty_niche_result()
