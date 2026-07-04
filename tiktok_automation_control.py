"""
Per-account automation mode control for the TikTok viral loop.

Modes:
  - queue_only (default): only queue content in Supabase
  - approval_required: content must be approved before posting
  - auto_post: direct posting only when AUTO_POST=true and account enabled

Never raises; always returns a safe mode string.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_TABLE = "automation_settings"
VALID_MODES = frozenset({"queue_only", "approval_required", "auto_post"})
DEFAULT_MODE = "queue_only"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        logger.warning("Supabase credentials missing; automation mode defaults to queue_only.")
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def _is_auto_post_enabled() -> bool:
    return os.getenv("AUTO_POST", "").strip().lower() in ("1", "true", "yes")


def getAutomationMode(account_id: str) -> str:
    """
    Return automation mode for account_id.

    auto_post is downgraded to queue_only unless AUTO_POST=true.
    Never raises; defaults to queue_only on any failure.
    """
    account = str(account_id or "").strip()
    if not account:
        return DEFAULT_MODE

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return DEFAULT_MODE

        table = os.getenv("AUTOMATION_SETTINGS_TABLE", DEFAULT_SETTINGS_TABLE)
        response = (
            supabase.table(table)
            .select("mode")
            .eq("account_id", account)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return DEFAULT_MODE

        mode = str(rows[0].get("mode") or DEFAULT_MODE).strip()
        if mode not in VALID_MODES:
            return DEFAULT_MODE

        if mode == "auto_post" and not _is_auto_post_enabled():
            return DEFAULT_MODE

        return mode

    except Exception as exc:
        logger.warning("getAutomationMode failed for %s: %s", account, exc)
        return DEFAULT_MODE


def setAutomationMode(account_id: str, mode: str) -> dict[str, Any]:
    """
    Persist automation mode for account_id.

    auto_post is stored but effective mode respects AUTO_POST env flag.
    Never raises; returns {"updated": bool, "mode": str, "error": None}.
    """
    result: dict[str, Any] = {"updated": False, "mode": DEFAULT_MODE, "error": None}
    account = str(account_id or "").strip()
    requested = str(mode or DEFAULT_MODE).strip()

    if not account:
        result["error"] = "missing_account_id"
        return result

    if requested not in VALID_MODES:
        result["error"] = "invalid_mode"
        result["mode"] = DEFAULT_MODE
        return result

    effective = requested
    if requested == "auto_post" and not _is_auto_post_enabled():
        effective = DEFAULT_MODE

    result["mode"] = effective

    try:
        supabase = _get_supabase_client()
        if supabase is None:
            result["error"] = "missing_supabase_credentials"
            return result

        table = os.getenv("AUTOMATION_SETTINGS_TABLE", DEFAULT_SETTINGS_TABLE)
        supabase.table(table).upsert(
            {
                "account_id": account,
                "mode": requested,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="account_id",
        ).execute()
        result["updated"] = True
        return result

    except Exception as exc:
        logger.warning("setAutomationMode failed for %s: %s", account, exc)
        result["error"] = str(exc)
        return result
