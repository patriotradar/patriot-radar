"""
Feedback loop for the Virality Intelligence System.

Automatic viral outcome detection, prediction vs reality comparison,
and bounded self-learning orchestration. Fully isolated from existing pipelines.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from niche_comment_signal_processor import group_raw_rows_by_video
from niche_comment_virality_engine import compute_virality_predictions

from virality_calibration_engine import (
    adjust_weights_bounded,
    compute_signal_errors,
    compute_weighted_score,
    load_calibration_state,
    store_calibration_log,
)
from virality_explainer import store_explanations_batch
from virality_snapshot_store import (
    fetch_raw_comment_rows,
    fetch_snapshots_for_video,
    store_prediction_snapshots,
)

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent / "data" / "virality_intelligence_config.json"


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


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


def _compute_video_engagement_metrics(video: dict[str, Any]) -> dict[str, float]:
    """Compute velocity and acceleration from raw comments for outcome detection."""
    comments = video.get("comments") or []
    timestamps: list[float] = []
    for comment in comments:
        ts = _parse_timestamp(comment)
        if ts is not None:
            timestamps.append(ts)

    if len(timestamps) < 2:
        return {
            "velocity_per_hour": 0.0,
            "velocity_growth": 0.0,
            "acceleration_raw": 0.0,
            "comment_count": len(comments),
        }

    timestamps.sort()
    span_hours = max((timestamps[-1] - timestamps[0]) / 3600.0, 0.25)
    overall_velocity = len(timestamps) / span_hours

    mid = timestamps[0] + (timestamps[-1] - timestamps[0]) / 2.0
    early = [t for t in timestamps if t <= mid]
    recent = [t for t in timestamps if t > mid]

    early_span = max((mid - timestamps[0]) / 3600.0, 0.25) if early else 0.25
    recent_span = max((timestamps[-1] - mid) / 3600.0, 0.25) if recent else 0.25

    early_velocity = len(early) / early_span if early else 0.0
    recent_velocity = len(recent) / recent_span if recent else 0.0

    if early_velocity > 0:
        acceleration_raw = ((recent_velocity - early_velocity) / early_velocity) * 100.0
        velocity_growth = acceleration_raw
    elif recent_velocity > 0:
        acceleration_raw = 100.0
        velocity_growth = 100.0
    else:
        acceleration_raw = 0.0
        velocity_growth = 0.0

    return {
        "velocity_per_hour": round(overall_velocity, 2),
        "velocity_growth": round(velocity_growth, 2),
        "acceleration_raw": round(acceleration_raw, 2),
        "comment_count": len(comments),
    }


def detect_viral_outcomes(
    raw_rows: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Automatically detect viral content from engagement data.

    Rules:
    - Top 5–10% of comment velocity growth
    - OR extreme acceleration over engagement windows
    """
    cfg = config or load_config()
    detection = cfg.get("outcome_detection") or {}
    percentile_min = float(detection.get("velocity_percentile_min", 0.90))
    accel_threshold = float(detection.get("extreme_acceleration_threshold", 50.0))
    min_comments = int(detection.get("min_comments_per_video", 3))

    videos = group_raw_rows_by_video(raw_rows)
    metrics_list: list[dict[str, Any]] = []

    for video in videos:
        comments = video.get("comments") or []
        if len(comments) < min_comments:
            continue
        metrics = _compute_video_engagement_metrics(video)
        metrics_list.append({
            "video_id": str(video.get("video_id") or ""),
            "video_url": video.get("url") or "",
            **metrics,
        })

    if not metrics_list:
        return []

    growth_values = sorted(m["velocity_growth"] for m in metrics_list)
    cutoff_idx = max(0, int(len(growth_values) * percentile_min) - 1)
    growth_cutoff = growth_values[cutoff_idx] if growth_values else 0.0

    outcomes: list[dict[str, Any]] = []
    for item in metrics_list:
        is_viral = (
            item["velocity_growth"] >= growth_cutoff
            or item["acceleration_raw"] >= accel_threshold
        )
        if not is_viral:
            continue

        outcome_score = min(
            100.0,
            max(item["velocity_growth"], item["acceleration_raw"], item["velocity_per_hour"] * 2),
        )
        outcomes.append({
            "video_id": item["video_id"],
            "video_url": item["video_url"],
            "is_viral": True,
            "outcome_score": round(outcome_score, 2),
            "velocity_growth": item["velocity_growth"],
            "acceleration_raw": item["acceleration_raw"],
            "velocity_per_hour": item["velocity_per_hour"],
            "detection_reason": (
                "top_velocity_growth"
                if item["velocity_growth"] >= growth_cutoff
                else "extreme_acceleration"
            ),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        })

    return outcomes


def compare_predictions_vs_outcomes(
    outcomes: list[dict[str, Any]],
    *,
    niche: str = "",
) -> list[dict[str, Any]]:
    """
    Compare historical snapshots against detected viral outcomes.
    Computes per-signal error for each matched video.
    """
    comparisons: list[dict[str, Any]] = []

    for outcome in outcomes:
        video_id = outcome["video_id"]
        snapshots = fetch_snapshots_for_video(video_id, niche=niche or None)
        if not snapshots:
            snapshots = fetch_snapshots_for_video(video_id)

        if not snapshots:
            continue

        earliest = snapshots[0]
        predicted_score = float(earliest.get("virality_score") or 0.0)
        actual_score = float(outcome["outcome_score"])
        signals = earliest.get("signals") or {
            "velocity_score": earliest.get("comment_velocity"),
            "acceleration_score": earliest.get("acceleration"),
            "cross_video_score": earliest.get("repetition_score"),
            "niche_relevance_score": earliest.get("niche_relevance_score"),
            "curiosity_score": earliest.get("curiosity_score"),
        }

        signal_errors = compute_signal_errors(signals, actual_score)
        prediction_error = round(actual_score - predicted_score, 4)

        comparisons.append({
            "video_id": video_id,
            "niche": earliest.get("niche") or niche,
            "predicted_score": predicted_score,
            "actual_score": actual_score,
            "prediction_error": prediction_error,
            "signal_errors": signal_errors,
            "snapshot_at": earliest.get("snapshot_at"),
            "outcome": outcome,
        })

    return comparisons


def aggregate_signal_errors(comparisons: list[dict[str, Any]]) -> dict[str, float]:
    """Average per-signal errors across all comparisons."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for comp in comparisons:
        for key, err in (comp.get("signal_errors") or {}).items():
            buckets[key].append(float(err))

    return {key: round(mean(values), 4) for key, values in buckets.items() if values}


def compute_prediction_accuracy(comparisons: list[dict[str, Any]]) -> float:
    """Mean absolute error inverted to 0-100 accuracy score."""
    if not comparisons:
        return 50.0
    errors = [abs(float(c.get("prediction_error") or 0.0)) for c in comparisons]
    mae = mean(errors)
    return round(max(0.0, min(100.0, 100.0 - mae)), 2)


def apply_calibrated_scores(
    prediction_result: dict[str, Any],
    weights: dict[str, float],
) -> dict[str, Any]:
    """Re-score videos with calibrated weights without modifying core engine output."""
    videos = prediction_result.get("videos") or []
    for video in videos:
        signals = video.get("signals") or {}
        calibrated = compute_weighted_score(signals, weights)
        video["calibrated_virality_score"] = calibrated
        video["virality_score"] = calibrated

    ranked = prediction_result.get("ranked_trends") or []
    for trend in ranked:
        if trend.get("type") == "video" and trend.get("signals"):
            trend["calibrated_virality_score"] = compute_weighted_score(trend["signals"], weights)
            trend["virality_score"] = trend["calibrated_virality_score"]

    return prediction_result


def run_learning_cycle(
    raw_rows: list[dict[str, Any]] | None = None,
    niches: list[str] | None = None,
) -> dict[str, Any]:
    """
    Full automated learning pipeline:
    1. Collect snapshots
    2. Detect viral outcomes
    3. Compare predictions vs outcomes
    4. Adjust weights (bounded)
    5. Store calibration + explanations
    """
    cfg = load_config()
    learning_cfg = cfg.get("learning") or {}
    min_outcomes = int(learning_cfg.get("min_outcomes_for_learning", 3))
    max_adj = float(learning_cfg.get("max_adjustment_pct", 0.03))
    min_adj = float(learning_cfg.get("min_adjustment_pct", 0.01))
    error_threshold = float(learning_cfg.get("error_threshold", 5.0))

    rows = raw_rows if raw_rows is not None else fetch_raw_comment_rows()
    niche_list = niches or cfg.get("default_niches") or ["fitness"]

    calibration = load_calibration_state()
    weights = calibration["weights"]
    accuracy_before = calibration.get("accuracy")

    snapshot_results: list[dict[str, Any]] = []
    all_videos_for_explain: list[dict[str, Any]] = []
    niche_used = ""

    for niche in niche_list:
        niche_used = niche
        base_result = compute_virality_predictions(rows, niche)
        if not base_result.get("success"):
            continue

        enhanced = apply_calibrated_scores(base_result, weights)
        videos = enhanced.get("videos") or []
        snap_result = store_prediction_snapshots(videos, niche, weights)
        snapshot_results.append({"niche": niche, **snap_result})
        all_videos_for_explain.extend(videos[:10])

    outcomes = detect_viral_outcomes(rows, cfg)
    comparisons: list[dict[str, Any]] = []
    for niche in niche_list:
        comparisons.extend(compare_predictions_vs_outcomes(outcomes, niche=niche))

    seen_videos: set[str] = set()
    unique_comparisons: list[dict[str, Any]] = []
    for comp in comparisons:
        vid = comp["video_id"]
        if vid not in seen_videos:
            seen_videos.add(vid)
            unique_comparisons.append(comp)

    accuracy_after = compute_prediction_accuracy(unique_comparisons)
    aggregated_errors = aggregate_signal_errors(unique_comparisons)

    new_weights = weights
    adjustments: dict[str, float] = {k: 0.0 for k in weights}

    if len(unique_comparisons) >= min_outcomes:
        new_weights, adjustments = adjust_weights_bounded(
            weights,
            aggregated_errors,
            max_adjustment=max_adj,
            min_adjustment=min_adj,
            error_threshold=error_threshold,
        )
        cal_result = store_calibration_log(
            weights,
            new_weights,
            adjustments,
            aggregated_errors,
            outcomes_processed=len(unique_comparisons),
            accuracy_before=accuracy_before,
            accuracy_after=accuracy_after,
            metadata={"outcomes_detected": len(outcomes), "niches_processed": niche_list},
        )
    else:
        cal_result = {"stored": False, "reason": "insufficient_outcomes", "local_saved": False}

    niche_accuracy = {"_global": accuracy_after}
    explain_result = store_explanations_batch(
        all_videos_for_explain[:20],
        niche_used or niche_list[0],
        new_weights,
        niche_accuracy=niche_accuracy,
        calibration_accuracy=accuracy_after,
    )

    return {
        "success": True,
        "snapshots": snapshot_results,
        "outcomes_detected": len(outcomes),
        "outcomes": outcomes[:20],
        "comparisons": len(unique_comparisons),
        "comparison_details": unique_comparisons[:10],
        "aggregated_signal_errors": aggregated_errors,
        "accuracy_before": accuracy_before,
        "accuracy_after": accuracy_after,
        "previous_weights": weights,
        "new_weights": new_weights,
        "adjustments": adjustments,
        "calibration_result": cal_result,
        "explanations_result": explain_result,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
