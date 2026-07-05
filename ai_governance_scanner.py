"""Health & Issue Scanner — collects runtime errors, failed tests, and health signals."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent


def _run_tests() -> dict[str, Any]:
    """Run Python unittest suite and capture failures."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "returncode": proc.returncode,
        }
    except Exception as exc:
        return {"success": False, "stdout": "", "stderr": str(exc), "returncode": -1}


def _parse_test_failures(output: str) -> list[dict[str, str]]:
    """Extract structured failure info from unittest output."""
    failures: list[dict[str, str]] = []
    blocks = re.split(r"(?m)^=+ FAIL:|^=+ ERROR:", output)
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        trace = "\n".join(lines[1:]).strip()
        file_match = re.search(r'File "([^"]+)", line (\d+)', trace)
        source_file = ""
        if file_match:
            source_file = file_match.group(1)
            if str(REPO_ROOT) in source_file:
                source_file = os.path.relpath(source_file, REPO_ROOT)
        failures.append(
            {
                "issue": f"Test failure: {title}",
                "details": trace[:2000],
                "source_file": source_file,
                "scan_source": "tests",
            }
        )
    return failures


def _check_system_health() -> list[dict[str, str]]:
    """Collect system health degradation signals."""
    issues: list[dict[str, str]] = []
    try:
        from tiktok_system_health import build_health_details

        details = build_health_details()
        health = details.get("system_health", "degraded")
        if health in ("degraded", "failing"):
            issues.append(
                {
                    "issue": f"System health is {health}",
                    "details": str(details),
                    "source_file": "tiktok_system_health.py",
                    "scan_source": "health",
                }
            )
    except Exception as exc:
        issues.append(
            {
                "issue": "System health check raised an exception",
                "details": str(exc),
                "source_file": "tiktok_system_health.py",
                "scan_source": "health",
            }
        )
    return issues


def _scan_log_patterns() -> list[dict[str, str]]:
    """Scan known log/runtime artifacts for error patterns."""
    issues: list[dict[str, str]] = []
    candidates = [
        REPO_ROOT / "last-run.txt",
        REPO_ROOT / "data" / "governance_scan.log",
    ]
    error_patterns = [
        (r"TypeError:\s*(.+)", "TypeError"),
        (r"ReferenceError:\s*(.+)", "ReferenceError"),
        (r"Cannot read propert(?:y|ies) of (undefined|null)", "NullReference"),
        (r"AttributeError:\s*(.+)", "AttributeError"),
        (r"KeyError:\s*(.+)", "KeyError"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pattern, label in error_patterns:
            for match in re.finditer(pattern, text):
                issues.append(
                    {
                        "issue": f"Runtime {label}: {match.group(0)[:200]}",
                        "details": text[max(0, match.start() - 200) : match.end() + 200],
                        "source_file": str(path.relative_to(REPO_ROOT)),
                        "scan_source": "logs",
                    }
                )
    return issues


def scan_issues() -> list[dict[str, Any]]:
    """
    Run all scanners and return structured issue reports (no fixes yet).

    Each item: { issue, details, source_file, scan_source }
    """
    raw: list[dict[str, str]] = []

    test_result = _run_tests()
    if not test_result["success"]:
        raw.extend(_parse_test_failures(test_result["stdout"] + "\n" + test_result["stderr"]))
        if not raw:
            raw.append(
                {
                    "issue": "Test suite failed",
                    "details": (test_result["stderr"] or test_result["stdout"])[:2000],
                    "source_file": "",
                    "scan_source": "tests",
                }
            )

    raw.extend(_check_system_health())
    raw.extend(_scan_log_patterns())

    # Deduplicate by issue text
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in raw:
        key = item.get("issue", "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    logger.info("Governance scan found %d issue(s)", len(unique))
    return unique
