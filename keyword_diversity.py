"""
Keyword diversity and historical deduplication for TikTok trend intelligence.

Prevents keyword looping across batches by tracking all previously generated
keywords in Supabase and enforcing sub-angle diversity.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "apify_tiktok_config.json"

STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "is", "it", "this", "that", "with", "you", "your", "my", "me", "i", "we",
    "they", "are", "was", "be", "have", "has", "had", "do", "does", "did",
    "not", "no", "yes", "so", "if", "just", "about", "from", "as", "by",
    "tiktok", "british", "britain", "england", "uk",
})

DEFAULT_ANGLE_POOLS: dict[str, list[str]] = {
    "emotional": [
        "veteran gratitude stories uk",
        "nostalgia old britain childhood memories",
        "pride in local community england",
        "emotional reunion military family uk",
    ],
    "historical": [
        "battle of britain facts explained",
        "dunkirk evacuation untold stories",
        "churchill leadership lessons history",
        "ww2 home front british women",
    ],
    "aesthetic": [
        "dark academia british aesthetic",
        "cottagecore english countryside vibes",
        "vintage london street photography",
        "rainy day british mood aesthetic",
    ],
    "pov": [
        "northern working class perspective uk",
        "immigrant view on british culture",
        "rural vs city life england pov",
        "gen z view on patriotism uk",
    ],
    "format": [
        "yes or no debate british politics",
        "storytime british history lesson",
        "hot take unpopular opinion uk",
        "5 things you should know britain",
    ],
}

DEFAULT_HASHTAG_POOLS: dict[str, list[str]] = {
    "emotional": ["veteransuk", "remembranceday", "proudbrit"],
    "historical": ["ww2history", "battleofbritain", "churchillquotes"],
    "aesthetic": ["ukaesthetic", "britishcountryside", "londonvibes"],
    "pov": ["northernuk", "workingclassuk", "britishhumour"],
    "format": ["debateuk", "storytimeuk", "hottakeuk"],
}


def normalize_root(value: str) -> str:
    """Normalize a keyword or phrase to a comparable root form."""
    cleaned = re.sub(r"[^a-z0-9\s']", " ", value.lower())
    tokens = [t for t in cleaned.split() if t and t not in STOPWORDS]
    if not tokens:
        return cleaned.strip()
    return " ".join(tokens[:4])


def root_phrase_key(value: str) -> str:
    """Stable key for root-phrase deduplication (first 3 content tokens)."""
    root = normalize_root(value)
    tokens = root.split()
    return " ".join(tokens[:3]) if tokens else root


def is_duplicate(value: str, historical: set[str], batch_seen: set[str] | None = None) -> bool:
    """Return True if value matches a historical or in-batch root phrase."""
    key = root_phrase_key(value)
    if not key:
        return True
    if key in historical:
        return True
    if batch_seen is not None and key in batch_seen:
        return True
    # Substring overlap: reject if root is subset of an existing historical root
    for existing in historical:
        if len(key) >= 4 and (key in existing or existing in key):
            return True
    return False


def dedupe_keywords(
    keywords: list[str],
    historical: set[str],
    batch_seen: set[str],
    max_count: int = 8,
) -> list[str]:
    """Return diverse keywords not seen in history or current batch."""
    result: list[str] = []
    for kw in keywords:
        if is_duplicate(kw, historical, batch_seen):
            continue
        key = root_phrase_key(kw)
        batch_seen.add(key)
        historical.add(key)  # prevent reuse within same pipeline run
        result.append(kw)
        if len(result) >= max_count:
            break
    return result


def dedupe_phrases(
    phrases: list[str],
    historical: set[str],
    batch_seen: set[str],
) -> list[str]:
    """Return phrase patterns not previously used."""
    result: list[str] = []
    for phrase in phrases:
        if is_duplicate(phrase, historical, batch_seen):
            continue
        key = root_phrase_key(phrase)
        batch_seen.add(key)
        result.append(phrase)
    return result


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client
    return create_client(supabase_url, service_role_key)


def _extract_keywords_from_row(row: dict[str, Any]) -> set[str]:
    """Extract all keyword roots from a feed row."""
    roots: set[str] = set()
    raw = row.get("raw_data") or {}
    summary = row.get("summary") or ""
    caption = raw.get("caption_preview") or ""

    for text in (summary, caption):
        for token in re.findall(r"[a-zA-Z']{3,}", text.lower()):
            if token not in STOPWORDS:
                roots.add(root_phrase_key(token))

    signal = raw.get("signal") or {}
    for cluster in signal.get("keyword_clusters") or []:
        kw = cluster.get("keyword", "")
        if kw:
            roots.add(root_phrase_key(kw))

    for phrase in signal.get("phrase_patterns") or []:
        if phrase:
            roots.add(root_phrase_key(phrase))

    hook = signal.get("hook_text") or raw.get("signal", {}).get("hook_text")
    if hook:
        roots.add(root_phrase_key(hook))

    return roots


def fetch_historical_keyword_roots(limit: int = 500) -> set[str]:
    """
    Load all previously stored keyword roots from trend_intelligence_feed.

    Returns empty set when Supabase is unavailable (scan still proceeds).
    """
    table = os.getenv("SUPABASE_FEED_TABLE", "trend_intelligence_feed")
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            logger.warning("Cannot load historical keywords: Supabase credentials missing.")
            return set()

        response = (
            supabase.table(table)
            .select("summary,raw_data,type")
            .eq("source", "tiktok")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data or []
        historical: set[str] = set()
        for row in rows:
            historical.update(_extract_keywords_from_row(row))

        logger.info("Loaded %d historical keyword roots from %d feed rows.", len(historical), len(rows))
        return historical
    except Exception as exc:
        logger.warning("Failed to load historical keywords: %s", exc)
        return set()


def _load_angle_pools() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Load angle pools from config file with defaults."""
    query_pools = {k: list(v) for k, v in DEFAULT_ANGLE_POOLS.items()}
    hashtag_pools = {k: list(v) for k, v in DEFAULT_HASHTAG_POOLS.items()}

    config_path = os.getenv("APIFY_TIKTOK_CONFIG_PATH")
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                config = json.load(f)
            if isinstance(config.get("anglePools"), dict):
                for angle, queries in config["anglePools"].items():
                    if isinstance(queries, list):
                        query_pools[angle] = queries
            if isinstance(config.get("hashtagAnglePools"), dict):
                for angle, tags in config["hashtagAnglePools"].items():
                    if isinstance(tags, list):
                        hashtag_pools[angle] = tags
        except Exception as exc:
            logger.warning("Failed to load angle pools from config: %s", exc)

    return query_pools, hashtag_pools


def select_diverse_apify_targets(
    historical: set[str],
    max_queries: int = 5,
    max_hashtags: int = 5,
) -> dict[str, Any]:
    """
    Pick search queries and hashtags that introduce new sub-angles.

    Selects at most one target per angle category (emotional, historical,
    aesthetic, pov, format) avoiding anything matching historical roots.
    """
    query_pools, hashtag_pools = _load_angle_pools()
    selected_queries: list[str] = []
    selected_hashtags: list[str] = []
    selected_angles: list[str] = []
    batch_seen: set[str] = set()

    for angle in ("emotional", "historical", "aesthetic", "pov", "format"):
        for query in query_pools.get(angle, []):
            if not is_duplicate(query, historical, batch_seen):
                selected_queries.append(query)
                batch_seen.add(root_phrase_key(query))
                selected_angles.append(angle)
                break

        for tag in hashtag_pools.get(angle, []):
            tag_query = f"#{tag}"
            if not is_duplicate(tag, historical, batch_seen):
                selected_hashtags.append(tag)
                batch_seen.add(root_phrase_key(tag))
                break

    # Trim to limits while preserving angle diversity order
    selected_queries = selected_queries[:max_queries]
    selected_hashtags = selected_hashtags[:max_hashtags]

    logger.info(
        "Selected diverse Apify targets: angles=%s queries=%d hashtags=%d",
        selected_angles,
        len(selected_queries),
        len(selected_hashtags),
    )

    return {
        "searchQueries": selected_queries,
        "hashtags": selected_hashtags,
        "angles_used": selected_angles,
    }
