"""
Learning engine for the TikTok viral loop feedback loop.

Analyzes content performance snapshots and updates strategy weightings for
caption style, hashtag ranking, and product scoring. Never raises.
"""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PERFORMANCE_TABLE = "content_performance"
DEFAULT_STRATEGY_TABLE = "content_strategy_weights"
DEFAULT_QUEUE_TABLE = "content_queue"

_WORD_RE = re.compile(r"[a-z0-9']+")


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        logger.warning("Supabase credentials missing; strategy update skipped.")
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _empty_result() -> dict[str, Any]:
    return {"updated": False, "weights": {}, "error": None}


def _default_weights() -> dict[str, Any]:
    return {
        "caption_style": {
            "question": 1.0,
            "pov": 1.0,
            "statement": 1.0,
            "trending_reference": 1.0,
        },
        "hashtag_ranking": {},
        "product_scoring": {},
        "engagement_baseline": 0.0,
        "sample_count": 0,
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _classify_caption_style(caption: str) -> str:
    lower = caption.lower().strip()
    if lower.startswith("pov:") or "pov:" in lower[:20]:
        return "pov"
    if "?" in lower:
        return "question"
    if any(kw in lower for kw in ("trending", "viral", "blowing up", "fyp")):
        return "trending_reference"
    return "statement"


def _extract_hashtags_from_queue(row: dict[str, Any]) -> list[str]:
    tags = row.get("hashtags") or []
    if isinstance(tags, list):
        return [str(t).lower().strip() for t in tags if str(t).strip()]
    return []


def _fetch_performance_with_content(
    supabase,
    perf_table: str,
    queue_table: str,
    account_id: str,
) -> list[dict[str, Any]]:
    try:
        perf_response = (
            supabase.table(perf_table)
            .select("content_id,performance_metrics,timestamp")
            .eq("account_id", account_id)
            .order("timestamp", desc=True)
            .limit(100)
            .execute()
        )
        perf_rows = perf_response.data or []
        if not perf_rows:
            return []

        content_ids = [r["content_id"] for r in perf_rows if r.get("content_id")]
        if not content_ids:
            return []

        queue_response = (
            supabase.table(queue_table)
            .select("id,caption,hook,hashtags,product_name")
            .in_("id", content_ids)
            .execute()
        )
        queue_by_id = {r["id"]: r for r in (queue_response.data or []) if r.get("id")}

        combined: list[dict[str, Any]] = []
        for perf in perf_rows:
            cid = perf.get("content_id")
            if not cid or cid not in queue_by_id:
                continue
            combined.append({
                "content": queue_by_id[cid],
                "metrics": perf.get("performance_metrics") or {},
            })
        return combined

    except Exception as exc:
        logger.warning("Failed to fetch performance data for learning: %s", exc)
        return []


def _compute_weights_from_performance(
    records: list[dict[str, Any]],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    weights = _default_weights()
    if existing:
        weights.update({k: v for k, v in existing.items() if k in weights})

    if not records:
        return weights

    caption_scores: dict[str, list[float]] = defaultdict(list)
    hashtag_scores: dict[str, list[float]] = defaultdict(list)
    product_scores: dict[str, list[float]] = defaultdict(list)
    engagement_rates: list[float] = []

    for record in records:
        content = record.get("content") or {}
        metrics = record.get("metrics") or {}
        engagement = _safe_float(metrics.get("engagement_rate"))
        engagement_rates.append(engagement)

        caption = str(content.get("caption") or "")
        style = _classify_caption_style(caption)
        caption_scores[style].append(engagement)

        for tag in _extract_hashtags_from_queue(content):
            hashtag_scores[tag].append(engagement)

        product = str(content.get("product_name") or "").strip().lower()
        if product:
            product_scores[product].append(engagement)

    baseline = mean(engagement_rates) if engagement_rates else 0.0
    weights["engagement_baseline"] = round(baseline, 6)
    weights["sample_count"] = len(records)

    for style, scores in caption_scores.items():
        avg = mean(scores) if scores else baseline
        boost = avg / max(baseline, 0.001)
        weights["caption_style"][style] = round(min(2.0, max(0.5, boost)), 4)

    hashtag_ranking: dict[str, float] = {}
    for tag, scores in hashtag_scores.items():
        avg = mean(scores) if scores else baseline
        hashtag_ranking[tag] = round(avg / max(baseline, 0.001), 4)
    weights["hashtag_ranking"] = dict(
        sorted(hashtag_ranking.items(), key=lambda x: x[1], reverse=True)[:20]
    )

    product_scoring: dict[str, float] = {}
    for product, scores in product_scores.items():
        avg = mean(scores) if scores else baseline
        product_scoring[product] = round(avg / max(baseline, 0.001), 4)
    weights["product_scoring"] = dict(
        sorted(product_scoring.items(), key=lambda x: x[1], reverse=True)[:15]
    )

    return weights


def _fetch_existing_weights(supabase, table: str, account_id: str) -> dict[str, Any] | None:
    try:
        response = (
            supabase.table(table)
            .select("weights_json")
            .eq("account_id", account_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows and rows[0].get("weights_json"):
            return rows[0]["weights_json"]
        return None
    except Exception as exc:
        logger.warning("Failed to fetch existing strategy weights: %s", exc)
        return None


def updateContentStrategy(account_id: str) -> dict[str, Any]:
    """
    Analyze performance data and update content strategy weightings.

    Never raises; returns {"updated": bool, "weights": {}, "error": None}.
    """
    result = _empty_result()
    account = str(account_id or "").strip()
    if not account:
        result["error"] = "missing_account_id"
        return result

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            result["error"] = "missing_supabase_credentials"
            return result

        perf_table = os.getenv("CONTENT_PERFORMANCE_TABLE", DEFAULT_PERFORMANCE_TABLE)
        strategy_table = os.getenv("CONTENT_STRATEGY_TABLE", DEFAULT_STRATEGY_TABLE)
        queue_table = os.getenv("CONTENT_QUEUE_TABLE", DEFAULT_QUEUE_TABLE)

        records = _fetch_performance_with_content(supabase, perf_table, queue_table, account)
        existing = _fetch_existing_weights(supabase, strategy_table, account)
        weights = _compute_weights_from_performance(records, existing)

        try:
            supabase.table(strategy_table).upsert(
                {
                    "account_id": account,
                    "weights_json": weights,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="account_id",
            ).execute()
            result["updated"] = True
            result["weights"] = weights
        except Exception as exc:
            logger.warning("Failed to store strategy weights: %s", exc)
            result["error"] = str(exc)
            result["weights"] = weights

        return result

    except Exception as exc:
        logger.warning("updateContentStrategy failed: %s", exc)
        result["error"] = str(exc)
        return result
