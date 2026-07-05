"""Shared constants for the AI Code Governance System."""

from __future__ import annotations

# Paths and patterns that must never receive auto-fixes.
BLOCKED_PATH_FRAGMENTS: tuple[str, ...] = (
    "trend_intelligence_engine/",
    "providers/",
    "api/",
    "sql/",
)

BLOCKED_FILENAME_KEYWORDS: tuple[str, ...] = (
    "scoring",
    "dedupe",
    "dedup",
    "provider",
)

SAFE_FIX_PATTERNS: tuple[str, ...] = (
    "?.",
    "??",
    "|| ",
    "||'",
    '||"',
    "if (",
    "if(",
    "typeof ",
    "!= null",
    "!== null",
    "!== undefined",
    "== null",
    "=== undefined",
    "Array.isArray",
    "try {",
    "try{",
    "catch (",
    "catch(",
    ".length",
    "default ",
    "?? ",
)

RISK_SAFE = "SAFE"
RISK_REVIEW = "REVIEW"
RISK_BLOCKED = "BLOCKED"

GEMINI_APPROVED = "APPROVED"
GEMINI_REJECTED = "REJECTED"
GEMINI_PENDING = "PENDING"

DEFAULT_GOVERNANCE_TABLE = "cr_ai_governance_issues"
