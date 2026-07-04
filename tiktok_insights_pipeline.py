"""
Unified TikTok insights pipeline with production hardening.

Orchestrates discovery → validation → scoring → comment cleaning → insights →
recommendations with fail-safe behavior at every step.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from apify_tiktok_comment_fetcher import (
    fetch_tiktok_comments_via_apify,
    load_sample_comment_videos,
)
from apify_tiktok_fetcher import fetch_tiktok_via_apify
from niche_comment_signal_processor import compute_niche_comment_signals, group_raw_rows_by_video
from niche_comment_raw_store import videos_to_raw_rows
from tiktok_content_generator import generateContentPack
from tiktok_emerging_products_engine import detectEmergingProducts
from tiktok_niche_resolver import resolveNiche
from tiktok_pipeline_hardening import (
    build_safe_pipeline_response,
    clean_comments,
    compute_trend_scores,
    empty_pipeline_response,
    generate_insights,
    generate_post_recommendations,
    validate_insights,
    validate_videos,
)
from tiktok_trend_extractor import extract_tiktok_trend_signals
from tiktok_trending_products_engine import generateTrendingProducts
from tiktok_content_publisher import queueContentForPosting
from tiktok_performance_tracker import trackContentPerformance
from tiktok_learning_engine import updateContentStrategy
from trend_intelligence_store import store_external_tiktok_signals

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_PATH = (
    __import__("pathlib").Path(__file__).resolve().parent / "data" / "tiktok_comment_sample.json"
)


def _normalize_video_for_gate(raw: dict[str, Any]) -> dict[str, Any]:
    """Map various video shapes to a common gate/scoring shape."""
    engagement = raw.get("engagement") or {}
    comments = raw.get("comments") or []
    return {
        **raw,
        "video_id": raw.get("video_id") or raw.get("id") or "",
        "url": raw.get("url") or raw.get("webVideoUrl") or "",
        "caption": raw.get("caption") or raw.get("description") or raw.get("text") or "",
        "author": raw.get("author") or "",
        "engagement": {
            "play_count": engagement.get("play_count") or raw.get("playCount") or raw.get("play_count") or 0,
            "digg_count": engagement.get("digg_count") or raw.get("diggCount") or raw.get("likes") or 0,
            "comment_count": max(
                engagement.get("comment_count") or raw.get("commentCount") or 0,
                len(comments),
            ),
        },
        "comments": comments,
        "create_time": raw.get("create_time") or raw.get("createTime") or raw.get("posted_at"),
    }


def _flatten_cleaned_comments(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for video in videos:
        vid = str(video.get("video_id") or video.get("url") or "")
        for comment in video.get("comments") or []:
            flat.append({**comment, "video_id": vid})
    return flat


def _derive_account_id(account_id: str, videos: list[dict[str, Any]]) -> str:
    """Resolve account_id from explicit value or first video author."""
    explicit = str(account_id or "").strip()
    if explicit:
        return explicit
    for video in videos:
        author = str(video.get("author") or "").strip()
        if author:
            return author
    return "unknown"


def run_hardened_tiktok_pipeline(
    *,
    account_id: str = "",
    niche: str = "",
    video_inputs: list[dict[str, Any]] | None = None,
    use_apify: bool = True,
    persist_signals: bool = False,
    sample_path: str | None = None,
) -> dict[str, Any]:
    """
    Production-grade TikTok intelligence pipeline.

    Never raises. Always returns the output safety contract.
    """
    errors: list[str] = []
    response = empty_pipeline_response()

    try:
        videos: list[dict[str, Any]] = []
        data_source = "unknown"
        apify_feedback: dict[str, Any] = {}

        if video_inputs:
            videos = [_normalize_video_for_gate(v) for v in video_inputs if isinstance(v, dict)]
            data_source = "explicit_inputs"
        elif use_apify:
            comment_result = fetch_tiktok_comments_via_apify()
            apify_feedback = {
                "success": comment_result.get("success", False),
                "source": "apify_comments",
                "error": comment_result.get("error") or "",
            }
            if comment_result.get("success") and comment_result.get("items"):
                videos = [_normalize_video_for_gate(v) for v in comment_result["items"]]
                data_source = "apify_comments"
            else:
                discovery = fetch_tiktok_via_apify()
                apify_feedback = {
                    "success": discovery.get("success", False),
                    "source": "apify_discovery",
                    "error": discovery.get("error") or "",
                }
                if discovery.get("success") and discovery.get("items"):
                    videos = [_normalize_video_for_gate(v) for v in discovery["items"]]
                    data_source = "apify_discovery"
                elif not discovery.get("token_present"):
                    path = sample_path or str(DEFAULT_SAMPLE_PATH)
                    videos = [_normalize_video_for_gate(v) for v in load_sample_comment_videos(path)]
                    data_source = "sample_fallback"
                    apify_feedback = {"success": True, "source": "sample_fallback", "error": ""}
                else:
                    errors.append(comment_result.get("error") or discovery.get("error") or "apify_fetch_failed")
        else:
            path = sample_path or str(DEFAULT_SAMPLE_PATH)
            videos = [_normalize_video_for_gate(v) for v in load_sample_comment_videos(path)]
            data_source = "sample_fallback"
            apify_feedback = {"success": True, "source": "sample_fallback", "error": ""}

        apify_feedback["data_source"] = data_source

        gate = validate_videos(videos)
        accepted_videos = gate.get("accepted") or []
        if gate.get("errors"):
            errors.extend(gate["errors"])

        trend_scores = compute_trend_scores(accepted_videos)

        cleaned_videos: list[dict[str, Any]] = []
        for video in accepted_videos:
            try:
                cleaned = clean_comments(video.get("comments") or [])
                cleaned_videos.append({**video, "comments": cleaned})
            except Exception as exc:
                logger.warning("Comment cleaning failed for video: %s", exc)
                cleaned_videos.append(video)

        flat_comments = _flatten_cleaned_comments(cleaned_videos)

        resolved_account_id = _derive_account_id(account_id, accepted_videos)
        niche_result = resolveNiche(
            account_id=resolved_account_id,
            videos=cleaned_videos,
            comments=flat_comments,
        )
        niche_str = str(niche_result.get("niche") or niche or "unknown")
        if niche and not niche_result.get("confidence"):
            niche_str = niche

        raw_insights = generate_insights(cleaned_videos, flat_comments, niche=niche_str)
        validated_insights = validate_insights(raw_insights, flat_comments, cleaned_videos)

        emerging_products: list[dict[str, Any]] = []
        trending_products: list[dict[str, Any]] = []
        content_pack: dict[str, Any] = {"captions": [], "hashtags": [], "hook_variations": []}

        try:
            emerging_products = detectEmergingProducts(
                videos=cleaned_videos,
                comments=flat_comments,
                niche=niche_result,
                trend_scores=trend_scores,
            )
        except Exception as exc:
            logger.warning("Emerging products detection skipped: %s", exc)
            errors.append(f"emerging_products: {exc}")

        try:
            trending_products = generateTrendingProducts(
                videos=cleaned_videos,
                comments=flat_comments,
                niche=niche_result,
                trend_scores=trend_scores,
            )
        except Exception as exc:
            logger.warning("Trending products detection skipped: %s", exc)
            errors.append(f"trending_products: {exc}")

        try:
            content_pack = generateContentPack(
                emerging_products=emerging_products,
                niche=niche_result,
                apify_feedback=apify_feedback,
            )
        except Exception as exc:
            logger.warning("Content pack generation skipped: %s", exc)
            errors.append(f"content_pack: {exc}")

        queue_result: dict[str, Any] = {"queued": 0, "skipped": 0, "posted": 0, "error": None, "items": []}
        performance_result: dict[str, Any] = {"tracked": 0, "skipped": 0, "error": None, "snapshots": []}
        strategy_result: dict[str, Any] = {"updated": False, "weights": {}, "error": None}

        try:
            queue_result = queueContentForPosting(
                account_id=resolved_account_id,
                content_pack=content_pack,
                emerging_products=emerging_products,
            )
        except Exception as exc:
            logger.warning("Content queue skipped: %s", exc)

        try:
            performance_result = trackContentPerformance(resolved_account_id)
        except Exception as exc:
            logger.warning("Performance tracking skipped: %s", exc)

        try:
            strategy_result = updateContentStrategy(resolved_account_id)
        except Exception as exc:
            logger.warning("Strategy update skipped: %s", exc)

        rec_result = generate_post_recommendations(validated_insights, cleaned_videos)
        recommended_posts = rec_result.get("recommended_posts") or []

        signals = {}
        if accepted_videos:
            try:
                extractor_inputs = [
                    {
                        "url": v.get("url", ""),
                        "caption": v.get("caption", ""),
                        "description": v.get("caption", ""),
                        "author": v.get("author", ""),
                        "engagement": v.get("engagement") or {},
                        "source": v.get("source", data_source),
                    }
                    for v in accepted_videos
                ]
                signals = extract_tiktok_trend_signals(extractor_inputs)
                if persist_signals and signals.get("extracted_items"):
                    store_external_tiktok_signals(signals)
            except Exception as exc:
                logger.warning("Trend signal extraction skipped: %s", exc)
                errors.append(f"signal_extraction: {exc}")

        niche_signals = {}
        if niche_str and cleaned_videos:
            try:
                raw_rows = videos_to_raw_rows(cleaned_videos)
                niche_signals = compute_niche_comment_signals(raw_rows, niche_str)
            except Exception as exc:
                logger.warning("Niche comment signals skipped: %s", exc)
                errors.append(f"niche_signals: {exc}")

        response = build_safe_pipeline_response(
            videos=cleaned_videos,
            insights=validated_insights,
            recommended_posts=recommended_posts,
            trend_scores=trend_scores,
            errors=errors,
            niche=niche_result,
            emerging_products=emerging_products,
            trending_products=trending_products,
            content_pack=content_pack,
            extra={
                "success": True,
                "data_source": data_source,
                "gate_stats": gate.get("stats") or {},
                "rejected_count": len(gate.get("rejected") or []),
                "insight_summary": signals.get("insight_summary", ""),
                "aggregated_signals": signals.get("aggregated_signals") or {},
                "niche_signals": niche_signals,
                "content_queue": queue_result,
                "performance_tracking": performance_result,
                "strategy_update": strategy_result,
                "computed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return response

    except Exception as exc:
        logger.exception("Hardened TikTok pipeline failed: %s", exc)
        response = empty_pipeline_response()
        response["errors"] = [str(exc)]
        response["success"] = False
        return response


def run_hardened_pipeline_from_raw_rows(
    raw_rows: list[dict[str, Any]],
    niche: str,
    account_id: str = "",
) -> dict[str, Any]:
    """Query-time hardened pipeline from niche_comment_raw rows."""
    errors: list[str] = []
    try:
        videos = group_raw_rows_by_video(raw_rows)
        normalized = [_normalize_video_for_gate(v) for v in videos]

        gate = validate_videos(normalized)
        accepted = gate.get("accepted") or []

        cleaned_videos: list[dict[str, Any]] = []
        for video in accepted:
            cleaned = clean_comments(video.get("comments") or [])
            cleaned_videos.append({**video, "comments": cleaned})

        flat_comments = _flatten_cleaned_comments(cleaned_videos)
        trend_scores = compute_trend_scores(accepted)

        resolved_account_id = _derive_account_id(account_id, accepted)
        niche_result = resolveNiche(
            account_id=resolved_account_id,
            videos=cleaned_videos,
            comments=flat_comments,
        )
        niche_str = str(niche_result.get("niche") or niche or "unknown")
        if niche and not niche_result.get("confidence"):
            niche_str = niche

        raw_insights = generate_insights(cleaned_videos, flat_comments, niche=niche_str)
        validated = validate_insights(raw_insights, flat_comments, cleaned_videos)

        emerging_products = detectEmergingProducts(
            videos=cleaned_videos,
            comments=flat_comments,
            niche=niche_result,
            trend_scores=trend_scores,
        )
        trending_products = generateTrendingProducts(
            videos=cleaned_videos,
            comments=flat_comments,
            niche=niche_result,
            trend_scores=trend_scores,
        )
        content_pack = generateContentPack(
            emerging_products=emerging_products,
            niche=niche_result,
            apify_feedback={},
        )

        queue_result: dict[str, Any] = {"queued": 0, "skipped": 0, "posted": 0, "error": None, "items": []}
        performance_result: dict[str, Any] = {"tracked": 0, "skipped": 0, "error": None, "snapshots": []}
        strategy_result: dict[str, Any] = {"updated": False, "weights": {}, "error": None}

        try:
            queue_result = queueContentForPosting(
                account_id=resolved_account_id,
                content_pack=content_pack,
                emerging_products=emerging_products,
            )
        except Exception as exc:
            logger.warning("Content queue skipped: %s", exc)

        try:
            performance_result = trackContentPerformance(resolved_account_id)
        except Exception as exc:
            logger.warning("Performance tracking skipped: %s", exc)

        try:
            strategy_result = updateContentStrategy(resolved_account_id)
        except Exception as exc:
            logger.warning("Strategy update skipped: %s", exc)

        recs = generate_post_recommendations(validated, cleaned_videos)

        return build_safe_pipeline_response(
            videos=cleaned_videos,
            insights=validated,
            recommended_posts=recs.get("recommended_posts") or [],
            trend_scores=trend_scores,
            errors=errors,
            niche=niche_result,
            emerging_products=emerging_products,
            trending_products=trending_products,
            content_pack=content_pack,
            extra={
                "success": True,
                "gate_stats": gate.get("stats") or {},
                "content_queue": queue_result,
                "performance_tracking": performance_result,
                "strategy_update": strategy_result,
                "computed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:
        logger.exception("run_hardened_pipeline_from_raw_rows failed: %s", exc)
        response = empty_pipeline_response()
        response["errors"] = [str(exc)]
        response["success"] = False
        return response
