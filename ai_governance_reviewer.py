"""Primary AI Reviewer — analyses issues and proposes minimal defensive fixes."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

from ai_governance_constants import GEMINI_PENDING, RISK_BLOCKED, RISK_REVIEW
from ai_governance_risk import build_issue_output, classify_risk, is_blocked_path

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

REVIEWER_SYSTEM = """You are a senior engineer reviewing production issues for CreatorRadar.
Propose ONLY minimal defensive fixes that do not change business logic.

ALLOWED fixes (SAFE):
- null/undefined guards
- optional chaining (?.)
- default values for missing fields
- array/object existence checks
- try/catch around external API calls (without changing logic)
- obvious TypeError fixes that do not change behaviour

NEVER propose fixes for:
- scoring logic, provider behaviour, API response shape
- database schema, deduplication logic, multi-file changes, architecture

Respond with JSON only:
{
  "root_cause": "brief explanation",
  "proposed_fix": "unified diff format",
  "risk": "SAFE | REVIEW | BLOCKED"
}
"""


def _call_llm(messages: list[dict[str, str]]) -> str | None:
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 1500,
    }

    if groq_key:
        try:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={**payload, "model": "llama-3.3-70b-versatile"},
                timeout=45,
            )
            if resp.ok:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("Groq reviewer call failed: %s", exc)

    if gemini_key:
        try:
            resp = requests.post(
                GEMINI_URL,
                headers={"Authorization": f"Bearer {gemini_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=45,
            )
            if resp.ok:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("Gemini reviewer call failed: %s", exc)

    return None


def _parse_llm_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _rule_based_review(raw: dict[str, Any]) -> dict[str, Any]:
    """Fallback when LLM is unavailable — conservative, no auto-fix."""
    issue = raw.get("issue", "Unknown issue")
    details = raw.get("details", "")
    source_file = raw.get("source_file", "")

    root_cause = "Detected by automated scanner; manual review required."
    proposed_fix = ""
    risk = RISK_REVIEW

    if is_blocked_path(source_file):
        risk = RISK_BLOCKED
        root_cause = f"Issue in blocked path ({source_file}); no auto-fix permitted."

    if "TypeError" in issue or "NullReference" in issue or "Cannot read propert" in details:
        root_cause = "Likely null/undefined access — defensive guard may be appropriate after review."
        risk = RISK_REVIEW if risk != RISK_BLOCKED else risk

    return build_issue_output(
        issue=issue,
        root_cause=root_cause,
        risk=risk,
        proposed_fix=proposed_fix,
        gemini_status=GEMINI_PENDING,
        warnings=["LLM unavailable; rule-based review only — no diff proposed"],
        source_file=source_file,
    )


def review_issue(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Analyse a scanned issue and return the mandatory governance output format.
    """
    issue = str(raw.get("issue") or "Unknown issue")
    source_file = str(raw.get("source_file") or "")
    details = str(raw.get("details") or "")

    if is_blocked_path(source_file):
        return build_issue_output(
            issue=issue,
            root_cause=f"Issue originates in blocked path: {source_file}",
            risk=RISK_BLOCKED,
            proposed_fix="",
            gemini_status=GEMINI_PENDING,
            warnings=["Blocked path — no fix will be auto-applied"],
            source_file=source_file,
        )

    user_prompt = f"""Issue: {issue}
Source file: {source_file or 'unknown'}
Details:
{details[:3000]}

Propose a minimal unified diff fix if SAFE, otherwise classify as REVIEW or BLOCKED."""

    llm_text = _call_llm(
        [
            {"role": "system", "content": REVIEWER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]
    )

    if not llm_text:
        return _rule_based_review(raw)

    parsed = _parse_llm_json(llm_text)
    root_cause = str(parsed.get("root_cause") or "AI analysis pending review")
    proposed_fix = str(parsed.get("proposed_fix") or "")
    llm_risk = str(parsed.get("risk") or RISK_REVIEW).upper()

    risk = classify_risk(source_file=source_file, proposed_fix=proposed_fix, issue=issue)
    if llm_risk == RISK_BLOCKED or risk == RISK_BLOCKED:
        risk = RISK_BLOCKED
    elif risk == RISK_REVIEW and llm_risk == "SAFE":
        risk = RISK_REVIEW  # Never trust LLM alone for SAFE

    warnings: list[str] = []
    if llm_risk != risk:
        warnings.append(f"Risk reclassified from LLM ({llm_risk}) to {risk} by policy engine")

    return build_issue_output(
        issue=issue,
        root_cause=root_cause,
        risk=risk,
        proposed_fix=proposed_fix,
        gemini_status=GEMINI_PENDING,
        warnings=warnings,
        source_file=source_file,
    )
