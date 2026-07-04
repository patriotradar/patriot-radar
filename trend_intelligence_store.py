"""
Persistence layer for external trend intelligence signals.

Writes read-only TikTok extraction output to Supabase trend_intelligence_feed.
Does not touch trends.py scoring, recommendations, or calibration.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_FEED_TABLE = "trend_intelligence_feed"
SOURCE_TIKTOK = "tiktok"


def _content_key(item: dict[str, Any]) -> str:
    url = (item.get("url") or "").strip()
    if url:
        return url
    preview = (item.get("caption_preview") or "").strip()
    if preview:
        return hashlib.sha256(preview.encode("utf-8")).hexdigest()[:32]
    return hashlib.sha256(repr(item).encode("utf-8")).hexdigest()[:32]


def _signal_strength(item: dict[str, Any], modifier: int = 0) -> int:
    viral = float(item.get("virality", {}).get("viral_strength_score", 0) or 0)
    fmt = float(item.get("format", {}).get("format_strength_score", 0) or 0)
    base = int(round((viral * 0.7 + fmt * 0.3) * 100))
    return max(0, min(100, base + modifier))


def _trend_state(signal_strength: int, previous_strength: int | None = None) -> str:
    if previous_strength is not None:
        delta = signal_strength - previous_strength
        if signal_strength >= 75:
            return "peaking"
        if delta <= -10:
            return "fading"
        if delta >= 10:
            return "rising"
    if signal_strength >= 75:
        return "peaking"
    if signal_strength >= 50:
        return "rising"
    return "emerging"


def _parse_timestamp(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    return value


def _virality_score(item: dict[str, Any]) -> int:
    """Return 0–100 virality score from item signals."""
    virality = item.get("virality") or {}
    if virality.get("virality_score") is not None:
        return max(0, min(100, int(virality["virality_score"])))
    raw = float(virality.get("viral_strength_score", 0) or 0)
    return max(0, min(100, int(round(raw * 100))))


def _row_base(
    item: dict[str, Any],
    ts: str,
    key: str,
    row_type: str,
    signal_strength: int,
    trend_state: str,
    signal: dict[str, Any],
    summary: str,
    dedupe_key: str,
) -> dict[str, Any]:
    """Build a feed row with virality_score always populated."""
    viral = _virality_score(item)
    item_snapshot = {
        "content_key": key,
        "url": item.get("url", ""),
        "author": item.get("author", ""),
        "caption_preview": item.get("caption_preview", ""),
        "extraction_status": item.get("extraction_status", ""),
        "batch_timestamp": ts,
        "virality_score": viral,
        "virality": item.get("virality") or {},
    }
    return {
        "created_at": ts,
        "source": SOURCE_TIKTOK,
        "type": row_type,
        "signal_strength": signal_strength,
        "virality_score": viral,
        "trend_state": trend_state,
        "raw_data": {**item_snapshot, "signal": signal},
        "summary": summary,
        "dedupe_key": dedupe_key,
    }


def signals_to_feed_rows(
    external_tiktok_signals: dict[str, Any],
    previous_strengths: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Flatten extracted TikTok items into trend_intelligence_feed rows."""
    if not external_tiktok_signals:
        return []

    items = external_tiktok_signals.get("extracted_items") or []
    if not items:
        return []

    ts = _parse_timestamp(external_tiktok_signals.get("timestamp"))
    prev = previous_strengths or {}
    rows: list[dict[str, Any]] = []

    for item in items:
        key = _content_key(item)
        base_strength = _signal_strength(item)

        hook = item.get("hook") or {}
        hook_type = hook.get("hook_type", "opinion")
        hook_dedupe = f"{key}:hook:{hook_type}"
        hook_strength = _signal_strength(item, 5)
        rows.append(_row_base(
            item, ts, key, "hook", hook_strength,
            _trend_state(hook_strength, prev.get(hook_dedupe)),
            hook,
            f"{hook_type} hook: {hook.get('hook_text', '')[:160]}".strip(),
            hook_dedupe,
        ))

        fmt = item.get("format") or {}
        fmt_type = fmt.get("format_type", "unknown")
        fmt_dedupe = f"{key}:format:{fmt_type}"
        fmt_strength = int(round(float(fmt.get("format_strength_score", 0) or 0) * 100))
        rows.append(_row_base(
            item, ts, key, "format", max(0, min(100, fmt_strength)),
            _trend_state(fmt_strength, prev.get(fmt_dedupe)),
            fmt,
            f"Format: {fmt_type.replace('_', ' ')}",
            fmt_dedupe,
        ))

        emotion = item.get("emotion") or {}
        emotion_name = emotion.get("dominant_emotion", "curiosity")
        emotion_dedupe = f"{key}:emotion:{emotion_name}"
        emotion_strength = _signal_strength(item, 3)
        mixture = emotion.get("emotion_mixture") or {}
        rows.append(_row_base(
            item, ts, key, "emotion", emotion_strength,
            _trend_state(emotion_strength, prev.get(emotion_dedupe)),
            emotion,
            f"Emotion: {emotion_name}" + (
                f" ({', '.join(f'{k} {v:.0%}' for k, v in list(mixture.items())[:3])})"
                if mixture else ""
            ),
            emotion_dedupe,
        ))

        topics = item.get("topics") or {}
        primary = topics.get("primary_topic", "other")
        secondary = topics.get("secondary_topics") or []
        topic_dedupe = f"{key}:topic:{primary}"
        topic_strength = _signal_strength(item, 2)
        rows.append(_row_base(
            item, ts, key, "topic", topic_strength,
            _trend_state(topic_strength, prev.get(topic_dedupe)),
            topics,
            f"Topic: {primary}" + (
                f" (+ {', '.join(secondary[:3])})" if secondary else ""
            ),
            topic_dedupe,
        ))

        linguistics = item.get("linguistics") or {}
        clusters = linguistics.get("keyword_clusters") or []
        phrases = linguistics.get("phrase_patterns") or []
        if clusters or phrases:
            cluster_dedupe = f"{key}:keyword_cluster:aggregate"
            top_kw = ", ".join(c["keyword"] for c in clusters[:5])
            top_phrases = ", ".join(phrases[:5])
            cluster_strength = min(
                100,
                base_strength + len(clusters) * 3 + len(phrases) * 2,
            )
            rows.append(_row_base(
                item, ts, key, "keyword_cluster", cluster_strength,
                _trend_state(cluster_strength, prev.get(cluster_dedupe)),
                {"keyword_clusters": clusters, "phrase_patterns": phrases},
                f"Keywords: {top_kw or 'n/a'}" + (
                    f" | Phrases: {top_phrases}" if top_phrases else ""
                ),
                cluster_dedupe,
            ))

    return rows


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )
    if not supabase_url or not service_role_key:
        missing = []
        if not supabase_url:
            missing.append("SUPABASE_URL")
        if not service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        logger.error(
            "Supabase credentials missing (%s). Cannot write to trend_intelligence_feed.",
            ", ".join(missing),
        )
        return None
    from supabase import create_client
    return create_client(supabase_url, service_role_key)


def _is_table_missing_error(exc: Exception | str) -> bool:
    msg = str(exc)
    return "PGRST205" in msg or "Could not find the table" in msg


def verify_feed_table(table: str | None = None) -> dict[str, Any]:
    """
    Probe trend_intelligence_feed existence and row count via service role.

    Returns {ok, table, row_count, error, table_missing}.
    """
    table_name = table or os.getenv("SUPABASE_FEED_TABLE", DEFAULT_FEED_TABLE)
    result: dict[str, Any] = {
        "ok": False,
        "table": table_name,
        "row_count": None,
        "error": None,
        "table_missing": False,
    }
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            result["error"] = "missing_supabase_credentials"
            return result

        response = (
            supabase.table(table_name)
            .select("id", count="exact")
            .eq("source", SOURCE_TIKTOK)
            .limit(1)
            .execute()
        )
        result["ok"] = True
        result["row_count"] = getattr(response, "count", None)
        if result["row_count"] is None:
            result["row_count"] = len(response.data or [])
        logger.info(
            "Supabase feed table probe: table=%s row_count=%s",
            table_name,
            result["row_count"],
        )
        return result
    except Exception as exc:
        result["error"] = str(exc)
        if _is_table_missing_error(exc):
            result["table_missing"] = True
            result["error"] = (
                f"table_missing:{table_name} — run sql/trend_intelligence_feed_setup.sql "
                "in Supabase SQL Editor or scripts/apply_trend_feed_schema.py"
            )
        logger.error("Supabase feed table probe failed: %s", exc)
        return result


def _fetch_previous_strengths(
    supabase,
    table: str,
    dedupe_keys: list[str],
) -> dict[str, int]:
    if not dedupe_keys:
        return {}
    try:
        response = (
            supabase.table(table)
            .select("dedupe_key,signal_strength")
            .in_("dedupe_key", dedupe_keys)
            .execute()
        )
        rows = response.data or []
        return {
            row["dedupe_key"]: int(row.get("signal_strength", 0) or 0)
            for row in rows
            if row.get("dedupe_key")
        }
    except Exception:
        return {}


def store_trend_intelligence_rows(
    rows: list[dict[str, Any]],
    table: str | None = None,
) -> dict[str, Any]:
    """
    Upsert feed rows into Supabase. Idempotent per dedupe_key (video/url signal).

    Returns a result dict; never raises.
    """
    table_name = table or os.getenv("SUPABASE_FEED_TABLE", DEFAULT_FEED_TABLE)
    if not rows:
        logger.info("No trend_intelligence_feed rows to store.")
        return {"stored": 0, "skipped": 0, "error": None}

    logger.info("Preparing to upsert %d row(s) into %s.", len(rows), table_name)

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {
                "stored": 0,
                "skipped": len(rows),
                "error": "missing_supabase_credentials",
            }

        table_probe = verify_feed_table(table_name)
        if table_probe.get("table_missing"):
            return {
                "stored": 0,
                "skipped": len(rows),
                "error": table_probe.get("error"),
                "table_probe": table_probe,
            }
        if not table_probe.get("ok"):
            return {
                "stored": 0,
                "skipped": len(rows),
                "error": table_probe.get("error") or "feed_table_probe_failed",
                "table_probe": table_probe,
            }

        dedupe_keys = [row["dedupe_key"] for row in rows if row.get("dedupe_key")]
        previous = _fetch_previous_strengths(supabase, table_name, dedupe_keys)

        for row in rows:
            dedupe = row.get("dedupe_key")
            if dedupe and dedupe in previous:
                row["trend_state"] = _trend_state(
                    int(row.get("signal_strength", 0)),
                    previous[dedupe],
                )

        stored = 0
        failed = 0
        last_error: str | None = None
        strip_virality_column = False

        for row in rows:
            payload = dict(row)
            if strip_virality_column:
                payload.pop("virality_score", None)

            try:
                supabase.table(table_name).upsert(
                    payload,
                    on_conflict="dedupe_key",
                ).execute()
                stored += 1
            except Exception as exc:
                err_msg = str(exc)
                last_error = err_msg
                # Retry without top-level virality_score if column not migrated yet.
                if (
                    not strip_virality_column
                    and "virality_score" in err_msg.lower()
                    and payload.get("virality_score") is not None
                ):
                    logger.warning(
                        "virality_score column missing in %s — retrying upserts without column "
                        "(run sql/trend_intelligence_feed_add_virality.sql). Error: %s",
                        table_name,
                        err_msg,
                    )
                    strip_virality_column = True
                    try:
                        payload_no_col = dict(row)
                        payload_no_col.pop("virality_score", None)
                        supabase.table(table_name).upsert(
                            payload_no_col,
                            on_conflict="dedupe_key",
                        ).execute()
                        stored += 1
                        continue
                    except Exception as retry_exc:
                        last_error = str(retry_exc)
                        logger.error("Supabase upsert retry failed for %s: %s", row.get("dedupe_key"), retry_exc)

                failed += 1
                logger.error(
                    "Supabase upsert failed for dedupe_key=%s: %s",
                    row.get("dedupe_key"),
                    err_msg,
                )

        logger.info(
            "Supabase upsert finished: table=%s stored=%d failed=%d row_count_before=%s",
            table_name,
            stored,
            failed,
            table_probe.get("row_count"),
        )
        if failed and last_error:
            logger.error("Last Supabase upsert error: %s", last_error)
            if _is_table_missing_error(last_error):
                return {
                    "stored": stored,
                    "skipped": failed,
                    "error": (
                        f"table_missing:{table_name} — run sql/trend_intelligence_feed_setup.sql"
                    ),
                }
        post_probe = verify_feed_table(table_name) if stored > 0 else table_probe
        return {
            "stored": stored,
            "skipped": failed,
            "error": None if failed == 0 else ("partial_write_failure: " + (last_error or "unknown")),
            "table_probe": post_probe,
        }
    except Exception as exc:
        logger.exception("Supabase upsert failed: %s", exc)
        return {"stored": 0, "skipped": len(rows), "error": str(exc)}


def store_external_tiktok_signals(
    external_tiktok_signals: dict[str, Any] | None,
    table: str | None = None,
) -> dict[str, Any]:
    """
    Persist external TikTok signals to trend_intelligence_feed.

    Safe to call with empty input — returns without error.
    """
    try:
        if not external_tiktok_signals:
            return {"stored": 0, "skipped": 0, "error": None}
        items = external_tiktok_signals.get("extracted_items") or []
        if not items:
            return {"stored": 0, "skipped": 0, "error": None}

        rows = signals_to_feed_rows(external_tiktok_signals)
        return store_trend_intelligence_rows(rows, table=table)
    except Exception as exc:
        return {"stored": 0, "skipped": 0, "error": str(exc)}
