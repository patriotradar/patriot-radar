"""Safe auto-fix engine — applies approved SAFE fixes only under strict rules."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from ai_governance_constants import GEMINI_APPROVED, RISK_SAFE
from ai_governance_risk import _count_diff_lines, _touches_multiple_files, is_blocked_path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent


class PatchError(Exception):
    """Raised when a patch cannot be safely applied."""


def _parse_unified_diff(diff: str) -> list[dict[str, Any]]:
    """Parse a minimal unified diff into hunks."""
    hunks: list[dict[str, Any]] = []
    current_file = ""
    current_hunk: dict[str, Any] | None = None

    for line in (diff or "").splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
            continue
        if line.startswith("@@"):
            if current_hunk:
                hunks.append(current_hunk)
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if not match:
                continue
            current_hunk = {
                "file": current_file,
                "old_start": int(match.group(1)),
                "new_start": int(match.group(2)),
                "lines": [],
            }
            continue
        if current_hunk is not None and (line.startswith("+") or line.startswith("-") or line.startswith(" ")):
            current_hunk["lines"].append(line)

    if current_hunk:
        hunks.append(current_hunk)
    return hunks


def validate_patch_allowed(issue: dict[str, Any]) -> list[str]:
    """Return list of blocking reasons; empty means allowed."""
    reasons: list[str] = []

    if issue.get("risk") != RISK_SAFE:
        reasons.append("risk is not SAFE")
    if issue.get("gemini_status") != GEMINI_APPROVED:
        reasons.append("gemini_status is not APPROVED")
    if issue.get("admin_status") not in ("approved", "pending"):
        pass  # admin approval checked separately

    source_file = issue.get("source_file") or ""
    if is_blocked_path(source_file):
        reasons.append(f"blocked path: {source_file}")

    diff = issue.get("proposed_fix") or ""
    if not diff.strip():
        reasons.append("empty proposed fix")

    if _touches_multiple_files(diff):
        reasons.append("multi-file diff not allowed")

    added, removed = _count_diff_lines(diff)
    if added > 1 or removed > 1:
        reasons.append("diff exceeds single-line SAFE limit")

    return reasons


def apply_patch(issue: dict[str, Any], *, require_admin_approved: bool = True) -> dict[str, Any]:
    """
    Apply a SAFE approved patch to the repository.

    Returns { success, message, file }.
    Raises PatchError on policy violation.
    """
    if require_admin_approved and issue.get("admin_status") != "approved":
        raise PatchError("Admin approval required before applying patch")

    blockers = validate_patch_allowed(issue)
    if blockers:
        raise PatchError("; ".join(blockers))

    diff = issue.get("proposed_fix") or ""
    hunks = _parse_unified_diff(diff)
    if not hunks:
        raise PatchError("Could not parse unified diff")

    applied_files: list[str] = []
    for hunk in hunks:
        rel_path = hunk.get("file") or issue.get("source_file") or ""
        if not rel_path:
            raise PatchError("No target file in diff")
        if is_blocked_path(rel_path):
            raise PatchError(f"Blocked path: {rel_path}")

        target = (REPO_ROOT / rel_path).resolve()
        if not str(target).startswith(str(REPO_ROOT.resolve())):
            raise PatchError("Path traversal blocked")
        if not target.exists():
            raise PatchError(f"File not found: {rel_path}")

        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        old_start = hunk["old_start"] - 1  # 0-indexed

        new_lines: list[str] = []
        idx = 0
        line_no = 0
        hunk_lines = hunk["lines"]

        while line_no < old_start and idx < len(lines):
            new_lines.append(lines[idx])
            idx += 1
            line_no += 1

        for hline in hunk_lines:
            if hline.startswith(" "):
                if idx >= len(lines):
                    raise PatchError("Context mismatch in diff")
                new_lines.append(lines[idx])
                idx += 1
            elif hline.startswith("-"):
                if idx >= len(lines):
                    raise PatchError("Remove line mismatch in diff")
                idx += 1
            elif hline.startswith("+"):
                new_lines.append(hline[1:] + ("\n" if not hline[1:].endswith("\n") else ""))

        while idx < len(lines):
            new_lines.append(lines[idx])
            idx += 1

        target.write_text("".join(new_lines), encoding="utf-8")
        applied_files.append(rel_path)
        logger.info("Applied SAFE patch to %s", rel_path)

    return {
        "success": True,
        "message": f"Applied patch to {', '.join(applied_files)}",
        "files": applied_files,
    }
