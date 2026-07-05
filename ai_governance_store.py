"""Supabase persistence for AI Code Governance issues."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from ai_governance_constants import DEFAULT_GOVERNANCE_TABLE

logger = logging.getLogger(__name__)


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def governance_table() -> str:
    return os.getenv("AI_GOVERNANCE_TABLE", DEFAULT_GOVERNANCE_TABLE)


def issue_to_record(issue: dict[str, Any]) -> dict[str, Any]:
    """Normalize issue dict to DB row shape."""
    return {
        "issue": str(issue.get("issue") or ""),
        "root_cause": str(issue.get("root_cause") or ""),
        "risk": str(issue.get("risk") or "REVIEW"),
        "proposed_fix": str(issue.get("proposed_fix") or ""),
        "gemini_status": str(issue.get("gemini_status") or "PENDING"),
        "warnings": issue.get("warnings") or [],
        "auto_applicable": bool(issue.get("auto_applicable")),
        "source_file": str(issue.get("source_file") or ""),
        "scan_source": str(issue.get("scan_source") or "manual"),
        "admin_status": str(issue.get("admin_status") or "pending"),
        "metadata": issue.get("metadata") or {},
    }


def record_to_issue(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize DB row to mandatory output format."""
    return {
        "id": row.get("id"),
        "issue": row.get("issue") or "",
        "root_cause": row.get("root_cause") or "",
        "risk": row.get("risk") or "REVIEW",
        "proposed_fix": row.get("proposed_fix") or "",
        "gemini_status": row.get("gemini_status") or "PENDING",
        "warnings": row.get("warnings") or [],
        "auto_applicable": bool(row.get("auto_applicable")),
        "source_file": row.get("source_file") or "",
        "scan_source": row.get("scan_source") or "",
        "admin_status": row.get("admin_status") or "pending",
        "apply_error": row.get("apply_error") or "",
        "admin_email": row.get("admin_email") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "applied_at": row.get("applied_at"),
    }


def insert_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    supabase = _get_supabase_client()
    if supabase is None:
        logger.warning("Supabase unavailable; cannot insert governance issue")
        return None
    try:
        payload = issue_to_record(issue)
        response = supabase.table(governance_table()).insert(payload).execute()
        rows = response.data or []
        return record_to_issue(rows[0]) if rows else None
    except Exception as exc:
        logger.warning("insert_issue failed: %s", exc)
        return None


def list_issues(*, limit: int = 50, admin_status: str | None = None) -> list[dict[str, Any]]:
    supabase = _get_supabase_client()
    if supabase is None:
        return []
    try:
        query = supabase.table(governance_table()).select("*").order("created_at", desc=True).limit(limit)
        if admin_status:
            query = query.eq("admin_status", admin_status)
        response = query.execute()
        return [record_to_issue(row) for row in (response.data or [])]
    except Exception as exc:
        logger.warning("list_issues failed: %s", exc)
        return []


def get_issue(issue_id: str) -> dict[str, Any] | None:
    supabase = _get_supabase_client()
    if supabase is None:
        return None
    try:
        response = (
            supabase.table(governance_table()).select("*").eq("id", issue_id).limit(1).execute()
        )
        rows = response.data or []
        return record_to_issue(rows[0]) if rows else None
    except Exception as exc:
        logger.warning("get_issue failed: %s", exc)
        return None


def update_issue(issue_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    supabase = _get_supabase_client()
    if supabase is None:
        return None
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        response = (
            supabase.table(governance_table()).update(payload).eq("id", issue_id).execute()
        )
        rows = response.data or []
        return record_to_issue(rows[0]) if rows else None
    except Exception as exc:
        logger.warning("update_issue failed: %s", exc)
        return None
