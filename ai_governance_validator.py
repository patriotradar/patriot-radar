"""Secondary AI Validator (Gemini layer) — approves or rejects proposed fixes."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

from ai_governance_constants import GEMINI_APPROVED, GEMINI_PENDING, GEMINI_REJECTED, RISK_SAFE
from ai_governance_risk import compute_auto_applicable, is_blocked_path

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

VALIDATOR_SYSTEM = """You are a safety validator for production code fixes in CreatorRadar.
Review the proposed fix and check correctness and side effects.

REJECT if the fix:
- Changes business logic, scoring, providers, API contracts, or schema
- Touches blocked paths (trend_intelligence_engine/, providers/, api/, sql/, scoring)
- Is not a minimal defensive guard
- Could silently change behaviour

APPROVE only if:
- Single-line or minimal defensive fix
- No behaviour change
- Correct null/undefined/type guard

Respond with JSON only:
{
  "status": "APPROVED | REJECTED",
  "warnings": ["list of warnings"]
}
"""


def _call_gemini(messages: list[dict[str, str]]) -> str | None:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None
    try:
        resp = requests.post(
            GEMINI_URL,
            headers={"Authorization": f"Bearer {gemini_key}", "Content-Type": "application/json"},
            json={
                "model": DEFAULT_MODEL,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 800,
            },
            timeout=45,
        )
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("Gemini validator call failed: %s", exc)
    return None


def _parse_validator_response(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _rule_based_validate(issue: dict[str, Any]) -> dict[str, Any]:
    """Conservative fallback — reject unless clearly safe with no diff."""
    risk = issue.get("risk", "REVIEW")
    source_file = issue.get("source_file", "")
    proposed_fix = issue.get("proposed_fix", "")
    warnings = list(issue.get("warnings") or [])

    if is_blocked_path(source_file):
        return {"gemini_status": GEMINI_REJECTED, "warnings": warnings + ["Blocked path"]}

    if risk != RISK_SAFE or not proposed_fix.strip():
        warnings.append("Gemini unavailable — defaulting to REJECTED for safety")
        return {"gemini_status": GEMINI_REJECTED, "warnings": warnings}

    warnings.append("Gemini unavailable — cannot validate SAFE fix")
    return {"gemini_status": GEMINI_REJECTED, "warnings": warnings}


def validate_fix(issue: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a reviewed issue. Returns updated gemini_status, warnings, auto_applicable.
    """
    result = dict(issue)
    warnings = list(issue.get("warnings") or [])

    if issue.get("risk") == "BLOCKED" or is_blocked_path(issue.get("source_file", "")):
        result["gemini_status"] = GEMINI_REJECTED
        result["warnings"] = warnings + ["Blocked — validator rejected"]
        result["auto_applicable"] = False
        return result

    if not issue.get("proposed_fix", "").strip():
        result["gemini_status"] = GEMINI_REJECTED
        result["warnings"] = warnings + ["No proposed fix to validate"]
        result["auto_applicable"] = False
        return result

    prompt = f"""Issue: {issue.get('issue')}
Root cause: {issue.get('root_cause')}
Risk classification: {issue.get('risk')}
Source file: {issue.get('source_file')}
Proposed fix (unified diff):
{issue.get('proposed_fix')}
"""

    llm_text = _call_gemini(
        [
            {"role": "system", "content": VALIDATOR_SYSTEM},
            {"role": "user", "content": prompt},
        ]
    )

    if not llm_text:
        validated = _rule_based_validate(issue)
        result.update(validated)
        result["auto_applicable"] = compute_auto_applicable(
            risk=result.get("risk", ""),
            gemini_status=result.get("gemini_status", GEMINI_PENDING),
            source_file=result.get("source_file", ""),
        )
        return result

    parsed = _parse_validator_response(llm_text)
    status = str(parsed.get("status", GEMINI_REJECTED)).upper()
    llm_warnings = parsed.get("warnings") or []
    if not isinstance(llm_warnings, list):
        llm_warnings = [str(llm_warnings)]

    if status not in (GEMINI_APPROVED, GEMINI_REJECTED):
        status = GEMINI_REJECTED
        llm_warnings.append("Invalid validator status — rejected for safety")

    # Policy override: never approve non-SAFE fixes
    if issue.get("risk") != RISK_SAFE:
        status = GEMINI_REJECTED
        llm_warnings.append("Only SAFE fixes can be APPROVED by policy")

    result["gemini_status"] = status
    result["warnings"] = warnings + [str(w) for w in llm_warnings]
    result["auto_applicable"] = compute_auto_applicable(
        risk=result.get("risk", ""),
        gemini_status=result["gemini_status"],
        source_file=result.get("source_file", ""),
    )
    return result
