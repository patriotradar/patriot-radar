"""Risk classification and blocked-path checks for AI Code Governance."""

from __future__ import annotations

import re
from typing import Any

from ai_governance_constants import (
    BLOCKED_FILENAME_KEYWORDS,
    BLOCKED_PATH_FRAGMENTS,
    RISK_BLOCKED,
    RISK_REVIEW,
    RISK_SAFE,
    SAFE_FIX_PATTERNS,
)


def is_blocked_path(file_path: str) -> bool:
    normalized = (file_path or "").replace("\\", "/").lower()
    if not normalized:
        return False
    for fragment in BLOCKED_PATH_FRAGMENTS:
        if fragment.lower() in normalized:
            return True
    basename = normalized.rsplit("/", 1)[-1]
    for keyword in BLOCKED_FILENAME_KEYWORDS:
        if keyword in basename:
            return True
    if "score" in basename and "scoring" not in basename:
        # scoring logic files often contain 'score'
        if any(k in normalized for k in ("virality", "trend", "recommendation")):
            return True
    return False


def _count_diff_lines(diff: str) -> tuple[int, int]:
    """Return (added_lines, removed_lines) excluding diff headers."""
    added = removed = 0
    for line in (diff or "").splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def _touches_multiple_files(diff: str) -> bool:
    files = set()
    for line in (diff or "").splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            path = line[4:].strip()
            if path.startswith("b/") or path.startswith("a/"):
                path = path[2:]
            if path and path != "/dev/null":
                files.add(path)
    return len(files) > 1


def classify_risk(*, source_file: str, proposed_fix: str, issue: str = "") -> str:
    """Classify risk as SAFE, REVIEW, or BLOCKED."""
    if is_blocked_path(source_file):
        return RISK_BLOCKED

    diff = proposed_fix or ""
    if _touches_multiple_files(diff):
        return RISK_BLOCKED

    added, removed = _count_diff_lines(diff)
    if added == 0 and removed == 0:
        return RISK_REVIEW

    # Multi-line changes are never SAFE
    if added + removed > 2:
        return RISK_REVIEW

    combined = (diff + issue).lower()
    if any(k in combined for k in ("schema", "migration", "alter table", "create table")):
        return RISK_BLOCKED
    if any(k in combined for k in ("dedup", "dedupe", "provider", "api contract", "scoring")):
        return RISK_BLOCKED

    # SAFE: single-line defensive fix patterns
    if added <= 1 and removed <= 1:
        added_content = "".join(
            line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
        )
        if any(p in added_content for p in SAFE_FIX_PATTERNS):
            return RISK_SAFE

    return RISK_REVIEW


def compute_auto_applicable(
    *,
    risk: str,
    gemini_status: str,
    source_file: str,
) -> bool:
    """True only when SAFE + Gemini APPROVED + not blocked."""
    if risk != RISK_SAFE:
        return False
    if gemini_status != "APPROVED":
        return False
    if is_blocked_path(source_file):
        return False
    return True


def build_issue_output(
    *,
    issue: str,
    root_cause: str,
    risk: str,
    proposed_fix: str,
    gemini_status: str,
    warnings: list[str] | None = None,
    source_file: str = "",
) -> dict[str, Any]:
    """Return mandatory output format."""
    warnings = warnings or []
    auto_applicable = compute_auto_applicable(
        risk=risk,
        gemini_status=gemini_status,
        source_file=source_file,
    )
    return {
        "issue": issue,
        "root_cause": root_cause,
        "risk": risk,
        "proposed_fix": proposed_fix,
        "gemini_status": gemini_status,
        "warnings": warnings,
        "auto_applicable": auto_applicable,
        "source_file": source_file,
    }


def extract_file_from_diff(diff: str) -> str:
    for line in (diff or "").splitlines():
        if line.startswith("+++ b/"):
            return line[6:].strip()
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                return path[2:]
            return path
    return ""
