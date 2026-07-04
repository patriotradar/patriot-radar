"""
Calibration engine for the Virality Intelligence System.

Manages signal weights with bounded, reversible adjustments.
Does not modify niche_comment_virality_engine.py — consumes its default weights
and stores calibrated overrides in isolated structures only.
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from niche_comment_virality_engine import VIRALITY_WEIGHTS

logger = logging.getLogger(__name__)

DEFAULT_CALIBRATION_TABLE = "virality_calibration_logs"
LOCAL_CALIBRATION_PATH = Path(__file__).resolve().parent / "data" / "virality_calibration_state.json"

SIGNAL_KEYS = ("velocity", "acceleration", "cross_video", "niche_relevance", "curiosity")

SIGNAL_TO_WEIGHT = {
    "velocity": "velocity",
    "acceleration": "acceleration",
    "repetition": "cross_video",
    "cross_video": "cross_video",
    "niche_relevance": "niche_relevance",
    "curiosity": "curiosity",
    "confusion": "curiosity",
}

DEFAULT_MAX_ADJUSTMENT = 0.03
DEFAULT_MIN_ADJUSTMENT = 0.01


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def default_weights() -> dict[str, float]:
    return deepcopy(VIRALITY_WEIGHTS)


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Ensure weights sum to 1.0 while preserving relative ratios."""
    cleaned = {k: max(0.01, float(weights.get(k, VIRALITY_WEIGHTS.get(k, 0.0)))) for k in SIGNAL_KEYS}
    total = sum(cleaned.values())
    if total <= 0:
        return default_weights()
    return {k: round(v / total, 4) for k, v in cleaned.items()}


def compute_weighted_score(signals: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Apply calibrated weights to raw signal scores without altering core engine."""
    w = normalize_weights(weights or default_weights())
    velocity = float(signals.get("velocity_score") or signals.get("velocity") or 0.0)
    acceleration = float(signals.get("acceleration_score") or signals.get("acceleration") or 0.0)
    cross_video = float(signals.get("cross_video_score") or signals.get("repetition_score") or 0.0)
    niche = float(signals.get("niche_relevance_score") or signals.get("niche_relevance") or 0.0)
    curiosity = float(signals.get("curiosity_score") or signals.get("curiosity") or 0.0)
    raw = (
        velocity * w["velocity"]
        + acceleration * w["acceleration"]
        + cross_video * w["cross_video"]
        + niche * w["niche_relevance"]
        + curiosity * w["curiosity"]
    )
    return round(min(100.0, raw), 2)


def load_calibration_state() -> dict[str, Any]:
    """Load latest calibrated weights from Supabase, local file, or defaults."""
    client = _get_supabase_client()
    table = os.getenv("VIRALITY_CALIBRATION_TABLE", DEFAULT_CALIBRATION_TABLE)

    if client is not None:
        try:
            resp = (
                client.table(table)
                .select("new_weights, calibrated_at, accuracy_after")
                .order("calibrated_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            if rows and rows[0].get("new_weights"):
                weights = normalize_weights(rows[0]["new_weights"])
                return {
                    "weights": weights,
                    "source": "supabase",
                    "calibrated_at": rows[0].get("calibrated_at"),
                    "accuracy": rows[0].get("accuracy_after"),
                }
        except Exception as exc:
            logger.warning("Could not load calibration from Supabase: %s", exc)

    if LOCAL_CALIBRATION_PATH.exists():
        try:
            payload = json.loads(LOCAL_CALIBRATION_PATH.read_text(encoding="utf-8"))
            weights = normalize_weights(payload.get("weights") or default_weights())
            return {
                "weights": weights,
                "source": "local_file",
                "calibrated_at": payload.get("calibrated_at"),
                "accuracy": payload.get("accuracy"),
            }
        except Exception as exc:
            logger.warning("Could not load local calibration state: %s", exc)

    return {
        "weights": default_weights(),
        "source": "defaults",
        "calibrated_at": None,
        "accuracy": None,
    }


def save_calibration_state_local(weights: dict[str, float], accuracy: float | None = None) -> None:
    LOCAL_CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "weights": normalize_weights(weights),
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "accuracy": accuracy,
    }
    LOCAL_CALIBRATION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def store_calibration_log(
    previous_weights: dict[str, float],
    new_weights: dict[str, float],
    adjustments: dict[str, float],
    signal_errors: dict[str, float],
    *,
    outcomes_processed: int = 0,
    accuracy_before: float | None = None,
    accuracy_after: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist calibration cycle to virality_calibration_logs. Never raises."""
    table = os.getenv("VIRALITY_CALIBRATION_TABLE", DEFAULT_CALIBRATION_TABLE)
    row = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "previous_weights": normalize_weights(previous_weights),
        "new_weights": normalize_weights(new_weights),
        "adjustments": adjustments,
        "signal_errors": signal_errors,
        "outcomes_processed": outcomes_processed,
        "accuracy_before": accuracy_before,
        "accuracy_after": accuracy_after,
        "metadata": metadata or {},
    }

    save_calibration_state_local(new_weights, accuracy_after)

    client = _get_supabase_client()
    if client is None:
        return {"stored": False, "error": "missing_supabase_credentials", "local_saved": True}

    try:
        client.table(table).insert(row).execute()
        return {"stored": True, "error": None, "local_saved": True}
    except Exception as exc:
        logger.error("Failed to store calibration log: %s", exc)
        return {"stored": False, "error": str(exc), "local_saved": True}


def compute_signal_errors(
    predicted_signals: dict[str, float],
    actual_outcome_score: float,
) -> dict[str, float]:
    """Per-signal error: positive = signal underestimated virality."""
    errors: dict[str, float] = {}
    for signal_key, weight_key in SIGNAL_TO_WEIGHT.items():
        score_key = f"{weight_key}_score" if weight_key != "cross_video" else "cross_video_score"
        if score_key not in predicted_signals and signal_key in predicted_signals:
            score_key = signal_key
        signal_value = float(predicted_signals.get(score_key) or predicted_signals.get(signal_key) or 0.0)
        if weight_key not in errors:
            errors[weight_key] = round(actual_outcome_score - signal_value, 4)
    return errors


def adjust_weights_bounded(
    current_weights: dict[str, float],
    aggregated_errors: dict[str, float],
    *,
    max_adjustment: float = DEFAULT_MAX_ADJUSTMENT,
    min_adjustment: float = DEFAULT_MIN_ADJUSTMENT,
    error_threshold: float = 5.0,
) -> tuple[dict[str, float], dict[str, float]]:
    """Apply bounded weight adjustments. Returns (new_weights, adjustments)."""
    weights = normalize_weights(current_weights)
    adjustments: dict[str, float] = {}

    for key in SIGNAL_KEYS:
        error = float(aggregated_errors.get(key, 0.0))
        if abs(error) < error_threshold:
            adjustments[key] = 0.0
            continue

        direction = 1.0 if error > 0 else -1.0
        magnitude = min(max_adjustment, max(min_adjustment, abs(error) / 100.0 * max_adjustment))
        delta = round(direction * magnitude, 4)
        adjustments[key] = delta
        weights[key] = max(0.05, weights[key] + delta)

    return normalize_weights(weights), adjustments


def fetch_calibration_history(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent calibration logs for dashboard analytics."""
    client = _get_supabase_client()
    table = os.getenv("VIRALITY_CALIBRATION_TABLE", DEFAULT_CALIBRATION_TABLE)
    if client is None:
        return []

    try:
        resp = (
            client.table(table)
            .select("*")
            .order("calibrated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.warning("Could not fetch calibration history: %s", exc)
        return []
