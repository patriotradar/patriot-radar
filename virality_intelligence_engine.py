"""
Virality Intelligence orchestrator — unified entry point.

Wraps the existing virality engine with calibration, explainability,
and snapshot storage without modifying existing systems.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from niche_comment_virality_engine import compute_virality_predictions

from virality_calibration_engine import compute_weighted_score, load_calibration_state
from virality_explainer import explain_predictions_batch
from virality_feedback_loop import apply_calibrated_scores
from virality_snapshot_store import store_prediction_snapshots


def compute_intelligent_predictions(
    raw_rows: list[dict[str, Any]],
    niche: str,
    *,
    persist_snapshots: bool = False,
    persist_explanations: bool = False,
) -> dict[str, Any]:
    """
    Enhanced virality predictions with calibration, confidence, and explanations.

    Core scoring formula is unchanged — calibrated weights are applied as a
    non-destructive overlay on raw signal scores.
    """
    calibration = load_calibration_state()
    weights = calibration["weights"]
    calibration_accuracy = calibration.get("accuracy")

    base = compute_virality_predictions(raw_rows, niche)
    if not base.get("success"):
        return {
            **base,
            "intelligence": {
                "enabled": True,
                "calibration_source": calibration.get("source"),
                "weights": weights,
            },
        }

    enhanced = apply_calibrated_scores(base, weights)
    videos = enhanced.get("videos") or []

    explanations = explain_predictions_batch(
        videos,
        niche,
        weights,
        calibration_accuracy=calibration_accuracy,
    )
    explanation_by_id = {e["video_id"]: e["explanation"] for e in explanations}

    for video in videos:
        vid = video.get("video_id")
        expl = explanation_by_id.get(vid)
        if expl:
            video["explanation"] = expl
            video["confidence"] = expl.get("confidence")

    if persist_snapshots:
        store_prediction_snapshots(videos, niche, weights)

    if persist_explanations:
        from virality_explainer import store_explanations_batch

        store_explanations_batch(
            videos,
            niche,
            weights,
            calibration_accuracy=calibration_accuracy,
        )

    return {
        **enhanced,
        "weights": weights,
        "calibrated_weights": weights,
        "base_weights": base.get("weights"),
        "intelligence": {
            "enabled": True,
            "calibration_source": calibration.get("source"),
            "calibrated_at": calibration.get("calibrated_at"),
            "calibration_accuracy": calibration_accuracy,
            "learning_active": calibration.get("source") != "defaults",
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def rescore_with_weights(signals: dict[str, float], weights: dict[str, float]) -> float:
    """Utility to recompute score from signals with specific weights."""
    return compute_weighted_score(signals, weights)
