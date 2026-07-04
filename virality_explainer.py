"""
Explainability layer for the Virality Intelligence System.

Generates human-readable prediction breakdowns and confidence scores.
Non-destructive — does not alter core scoring in niche_comment_virality_engine.py.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

from virality_calibration_engine import SIGNAL_KEYS, compute_weighted_score, normalize_weights

logger = logging.getLogger(__name__)

DEFAULT_EXPLANATION_TABLE = "virality_explanations"

SIGNAL_LABELS = {
    "velocity": "Comment velocity",
    "acceleration": "Comment acceleration",
    "cross_video": "Cross-video repetition",
    "niche_relevance": "Niche relevance",
    "curiosity": "Curiosity / confusion",
}

SIGNAL_SCORE_KEYS = {
    "velocity": "velocity_score",
    "acceleration": "acceleration_score",
    "cross_video": "cross_video_score",
    "niche_relevance": "niche_relevance_score",
    "curiosity": "curiosity_score",
}


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _explanation_dedupe_key(video_id: str, niche: str, day: str) -> str:
    raw = f"{video_id}|{niche.strip().lower()}|{day}|explain"
    return "virality_explanation:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compute_signal_impacts(
    signals: dict[str, float],
    weights: dict[str, float],
) -> list[dict[str, Any]]:
    """Compute per-signal contribution to the weighted score."""
    w = normalize_weights(weights)
    impacts: list[dict[str, Any]] = []

    for key in SIGNAL_KEYS:
        score_key = SIGNAL_SCORE_KEYS[key]
        score = float(signals.get(score_key) or 0.0)
        weight = w[key]
        impact = round((score * weight) / 100.0, 4)
        impacts.append({
            "signal": key,
            "label": SIGNAL_LABELS[key],
            "score": round(score, 2),
            "weight": round(weight, 4),
            "impact": impact,
            "impact_pct": round(impact * 100, 1),
        })

    impacts.sort(key=lambda x: x["impact"], reverse=True)
    return impacts


def compute_confidence(
    *,
    niche: str,
    signal_impacts: list[dict[str, Any]],
    niche_accuracy: dict[str, float] | None = None,
    calibration_accuracy: float | None = None,
) -> dict[str, Any]:
    """
    Confidence scoring based on historical accuracy and signal stability.
    Returns level (High/Medium/Low) and numeric score 0-100.
    """
    niche_key = niche.strip().lower()
    base_accuracy = calibration_accuracy if calibration_accuracy is not None else 50.0
    if niche_accuracy and niche_key in niche_accuracy:
        base_accuracy = niche_accuracy[niche_key]
    elif niche_accuracy and "_global" in niche_accuracy:
        base_accuracy = niche_accuracy["_global"]

    top_impact = signal_impacts[0]["impact"] if signal_impacts else 0.0
    second_impact = signal_impacts[1]["impact"] if len(signal_impacts) > 1 else 0.0
    stability = 1.0 - min(1.0, abs(top_impact - second_impact) * 2) if top_impact else 0.5

    score = round(min(100.0, base_accuracy * 0.6 + stability * 40.0), 2)

    if score >= 70:
        level = "High"
    elif score >= 45:
        level = "Medium"
    else:
        level = "Low"

    return {
        "level": level,
        "score": score,
        "factors": {
            "historical_accuracy": round(base_accuracy, 2),
            "signal_stability": round(stability * 100, 2),
        },
    }


def explain_prediction(
    video: dict[str, Any],
    niche: str,
    weights: dict[str, float],
    *,
    niche_accuracy: dict[str, float] | None = None,
    calibration_accuracy: float | None = None,
) -> dict[str, Any]:
    """
    Generate full explanation for a single video prediction.

    Returns top contributors, positive/negative factors, and confidence.
    """
    signals = video.get("signals") or {}
    impacts = compute_signal_impacts(signals, weights)
    confidence = compute_confidence(
        niche=niche,
        signal_impacts=impacts,
        niche_accuracy=niche_accuracy,
        calibration_accuracy=calibration_accuracy,
    )

    positive: list[str] = []
    negative: list[str] = []

    for item in impacts:
        label = item["label"]
        impact = item["impact"]
        score = item["score"]
        if impact >= 0.08:
            positive.append(f"{label} (+{impact:.2f} impact, score {score:.0f})")
        elif score < 20 and item["weight"] >= 0.15:
            negative.append(f"Weak {label.lower()} (score {score:.0f}) reduced confidence")

    if confidence["level"] == "Low":
        negative.append(
            f"Low confidence due to weak historical performance in niche '{niche}'"
        )

    top_contributors = [
        f"{item['label']} (+{item['impact']:.2f} impact)"
        for item in impacts[:3]
        if item["impact"] > 0.01
    ]

    virality_score = float(video.get("virality_score") or compute_weighted_score(signals, weights))
    summary_parts = top_contributors[:2] if top_contributors else ["Insufficient signal data"]
    summary = f"Score {virality_score:.0f}: " + "; ".join(summary_parts)

    return {
        "summary": summary,
        "virality_score": virality_score,
        "confidence": confidence,
        "top_contributors": top_contributors,
        "positive_factors": positive,
        "negative_factors": negative,
        "signal_impacts": impacts,
        "weights_used": normalize_weights(weights),
    }


def explain_predictions_batch(
    videos: list[dict[str, Any]],
    niche: str,
    weights: dict[str, float],
    *,
    niche_accuracy: dict[str, float] | None = None,
    calibration_accuracy: float | None = None,
) -> list[dict[str, Any]]:
    """Generate explanations for a batch of video predictions."""
    results: list[dict[str, Any]] = []
    for video in videos:
        explanation = explain_prediction(
            video,
            niche,
            weights,
            niche_accuracy=niche_accuracy,
            calibration_accuracy=calibration_accuracy,
        )
        results.append({
            "video_id": video.get("video_id"),
            "explanation": explanation,
        })
    return results


def store_explanation(
    video_id: str,
    niche: str,
    explanation: dict[str, Any],
) -> dict[str, Any]:
    """Persist explanation to virality_explanations. Never raises."""
    table = os.getenv("VIRALITY_EXPLANATION_TABLE", DEFAULT_EXPLANATION_TABLE)
    now = datetime.now(timezone.utc)
    confidence = explanation.get("confidence") or {}

    row = {
        "created_at": now.isoformat(),
        "video_id": video_id,
        "niche": niche.strip().lower(),
        "virality_score": float(explanation.get("virality_score") or 0.0),
        "confidence_level": confidence.get("level", "Medium"),
        "confidence_score": float(confidence.get("score") or 50.0),
        "explanation": explanation,
        "dedupe_key": _explanation_dedupe_key(video_id, niche, now.strftime("%Y%m%d")),
    }

    client = _get_supabase_client()
    if client is None:
        return {"stored": False, "error": "missing_supabase_credentials"}

    try:
        client.table(table).upsert(row, on_conflict="dedupe_key").execute()
        return {"stored": True, "error": None}
    except Exception as exc:
        logger.error("Failed to store explanation for %s: %s", video_id, exc)
        return {"stored": False, "error": str(exc)}


def store_explanations_batch(
    videos: list[dict[str, Any]],
    niche: str,
    weights: dict[str, float],
    *,
    niche_accuracy: dict[str, float] | None = None,
    calibration_accuracy: float | None = None,
) -> dict[str, Any]:
    """Generate and store explanations for all videos."""
    stored = 0
    failed = 0
    explanations: list[dict[str, Any]] = []

    for video in videos:
        video_id = str(video.get("video_id") or "")
        if not video_id:
            continue
        explanation = explain_prediction(
            video,
            niche,
            weights,
            niche_accuracy=niche_accuracy,
            calibration_accuracy=calibration_accuracy,
        )
        result = store_explanation(video_id, niche, explanation)
        explanations.append({"video_id": video_id, "explanation": explanation})
        if result.get("stored"):
            stored += 1
        else:
            failed += 1

    return {"stored": stored, "failed": failed, "explanations": explanations}
