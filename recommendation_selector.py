"""
Single decision authority for recommendation selection.

All other layers (scoring, calibration, repetition, viral state) contribute
signals only. ONLY final_recommendation_selector() may choose the winner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from recommendation_signals import emotional_trigger, format_family

# Minimum composite score before falling back to structural recommendation.
MIN_QUALITY_THRESHOLD = 2.0


@dataclass
class CandidateSignals:
    item: dict
    draft: dict
    trigger: str
    base_score: float
    calibration_boost: float
    repetition_penalty: float
    viral_potential_score: float
    low_confidence: bool
    final_score: float


def gather_candidates(results, emerging) -> list[dict]:
    """Collect unique candidates. Does not rank or reject."""
    candidates = []
    seen = set()
    for item in (results or [])[:5] + (emerging or [])[:5]:
        keyword = (item.get("keyword") or "").lower()
        if keyword and keyword in seen:
            continue
        if keyword:
            seen.add(keyword)
        candidates.append(item)
    return candidates


def compute_base_score(item: dict) -> float:
    """Trend score signal — advisory input to final ranking."""
    opportunity = float(item.get("opportunity_gap", 0) or 0)
    content = float(item.get("content_score", 0) or 0) / 10.0
    viral = float(item.get("viral_score", 0) or 0) / 10.0
    return opportunity * 0.5 + content * 0.35 + viral * 0.15


def compute_viral_potential_signal(item: dict) -> dict:
    """
    Viral filter as risk signal only — does NOT reject candidates.
    Flags LOW_CONFIDENCE when traction signals are weak.
    """
    from trends import determine_virality_state

    state = determine_virality_state(item)
    rise = float(item.get("rise_percent", 0) or 0)
    platform_count = int(item.get("platform_count", 0) or 0)
    opportunity_gap = float(item.get("opportunity_gap", 0) or 0)

    score = 0.0
    if state == "GROWING":
        score += 2.0
    if rise >= 15:
        score += 0.6
    elif rise > 0:
        score += 0.25
    if platform_count >= 2:
        score += 0.5
    if opportunity_gap >= 6:
        score += 0.4

    low_confidence = state != "GROWING" and score < 1.5
    return {
        "viral_potential_score": score,
        "low_confidence": low_confidence,
        "state": state,
    }


def repetition_penalty_signal(
    keyword: str,
    post_format: str,
    trigger: str,
    history: list[dict],
) -> float:
    """
    Repetition control as penalty signal only — does NOT remove candidates.
    """
    penalty = 0.0
    topic = (keyword or "").lower().strip()
    family = format_family(post_format)

    for past in history:
        if (past.get("keyword") or "").lower().strip() == topic and past.get("format_family") == family:
            penalty += 2.0
            break

    if history and history[-1].get("emotional_trigger") == trigger:
        penalty += 1.5

    return penalty


def _compose_final_score(
    base_score: float,
    calibration_boost: float,
    repetition_penalty: float,
    viral_potential_score: float,
) -> float:
    return (
        base_score
        + calibration_boost * 2.5
        - repetition_penalty
        + viral_potential_score * 0.75
    )


def _score_candidate(
    item: dict,
    engagement_signal: str,
    calibration_context: dict | None,
    history: list[dict],
    build_recommendation_for_item: Callable,
    engagement_metrics,
) -> CandidateSignals:
    from user_calibration import calibrated_selection_boost

    draft = build_recommendation_for_item(item, engagement_metrics)
    next_post = draft.get("next_post") or {}
    post_format = next_post.get("format", "")
    keyword = item.get("keyword", "")
    trigger = emotional_trigger(item, engagement_signal, post_format)

    base_score = compute_base_score(item)
    calibration_boost = calibrated_selection_boost(item, calibration_context or {}, engagement_signal)
    repetition_penalty = repetition_penalty_signal(keyword, post_format, trigger, history)
    viral = compute_viral_potential_signal(item)

    final_score = _compose_final_score(
        base_score,
        calibration_boost,
        repetition_penalty,
        viral["viral_potential_score"],
    )

    return CandidateSignals(
        item=item,
        draft=draft,
        trigger=trigger,
        base_score=base_score,
        calibration_boost=calibration_boost,
        repetition_penalty=repetition_penalty,
        viral_potential_score=viral["viral_potential_score"],
        low_confidence=viral["low_confidence"],
        final_score=final_score,
    )


def _fallback_selection(
    scored: list[CandidateSignals],
    structural_fallback: dict | None,
    engagement_signal: str,
):
    """Choose fallback when no candidate meets quality threshold."""
    if scored:
        best = max(scored, key=lambda c: c.base_score)
        return best.item, best.draft, best.trigger, best

    if structural_fallback:
        return (
            None,
            structural_fallback,
            "curiosity",
            None,
        )

    return None, None, "curiosity", None


def final_recommendation_selector(
    results,
    emerging,
    engagement_metrics=None,
    calibration_context=None,
    history=None,
    build_recommendation_for_item=None,
    structural_fallback: dict | None = None,
):
    """
    SINGLE DECISION AUTHORITY.

    The only function allowed to select the final recommendation, reject via
    quality threshold, or choose fallback. All layers contribute signals only.
    """
    from trends import detect_engagement_signal

    if build_recommendation_for_item is None:
        from recommendation_output import build_recommendation_for_item as default_builder

        build_recommendation_for_item = default_builder

    engagement_signal = detect_engagement_signal(engagement_metrics)
    candidates = gather_candidates(results, emerging)
    history = history or []

    if not candidates:
        item, draft, trigger, _ = _fallback_selection([], structural_fallback, engagement_signal)
        return item, draft, trigger

    scored = [
        _score_candidate(
            item,
            engagement_signal,
            calibration_context,
            history,
            build_recommendation_for_item,
            engagement_metrics,
        )
        for item in candidates
    ]
    scored.sort(key=lambda c: c.final_score, reverse=True)

    winner = scored[0]
    if winner.final_score < MIN_QUALITY_THRESHOLD:
        item, draft, trigger, _ = _fallback_selection(scored, structural_fallback, engagement_signal)
        return item, draft, trigger

    return winner.item, winner.draft, winner.trigger
