"""Orchestrates the full AI Code Governance pipeline."""

from __future__ import annotations

import logging
from typing import Any

from ai_governance_reviewer import review_issue
from ai_governance_scanner import scan_issues
from ai_governance_store import insert_issue, list_issues
from ai_governance_validator import validate_fix

logger = logging.getLogger(__name__)


def run_governance_scan(*, persist: bool = True) -> list[dict[str, Any]]:
    """
    Full pipeline: scan → primary review → Gemini validation → store.

    Returns list of issues in mandatory output format.
    """
    raw_issues = scan_issues()
    results: list[dict[str, Any]] = []

    if not raw_issues:
        logger.info("No issues detected in governance scan")
        return results

    for raw in raw_issues:
        reviewed = review_issue(raw)
        reviewed["scan_source"] = raw.get("scan_source", "manual")
        validated = validate_fix(reviewed)

        output = {
            "issue": validated.get("issue", ""),
            "root_cause": validated.get("root_cause", ""),
            "risk": validated.get("risk", "REVIEW"),
            "proposed_fix": validated.get("proposed_fix", ""),
            "gemini_status": validated.get("gemini_status", "PENDING"),
            "warnings": validated.get("warnings", []),
            "auto_applicable": validated.get("auto_applicable", False),
            "source_file": validated.get("source_file", ""),
            "scan_source": validated.get("scan_source", "manual"),
        }

        if persist:
            stored = insert_issue(output)
            if stored:
                output["id"] = stored.get("id")
                output["admin_status"] = stored.get("admin_status", "pending")

        results.append(output)

    return results


def get_governance_queue(*, limit: int = 50) -> list[dict[str, Any]]:
    return list_issues(limit=limit)
