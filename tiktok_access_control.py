"""
Role-based access control for TikTok SaaS feature visibility.

Read-only override layer — does NOT alter backend execution rules or safety constraints.
Role is derived from secure backend sources only; never trust client-supplied roles.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VALID_ROLES = frozenset({"admin", "creator", "viewer", "test"})
DEFAULT_ROLE = "creator"

ALL_MODULES = (
    "trends",
    "products",
    "inventory_system",
    "prediction_engine",
    "analytics",
    "system_health",
    "raw_logs",
    "hidden_alerts",
)

COMMERCE_GATED_MODULES = frozenset({"products", "inventory_system"})

_SENSITIVE_MODULES = frozenset({"system_health", "raw_logs", "hidden_alerts"})

_FEATURE_FLAGS_PATH = Path(__file__).resolve().parent / "data" / "feature_flags.json"


def _load_feature_flags() -> dict[str, bool]:
    try:
        with _FEATURE_FLAGS_PATH.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return {}
        return {str(k): bool(v) for k, v in raw.items()}
    except Exception as exc:
        logger.warning("Failed to load feature flags: %s", exc)
        return {}


def _admin_emails() -> set[str]:
    raw = os.getenv("TIKTOK_ADMIN_EMAILS") or os.getenv("ADMIN_EMAILS") or ""
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _normalize_role(value: Any) -> str | None:
    if value is None:
        return None
    role = str(value).strip().lower()
    return role if role in VALID_ROLES else None


def getUserRole(account_id: str, user_record: dict[str, Any] | None = None) -> str:
    """
    Derive user role from secure backend sources only.

    Priority: verified admin email allowlist → user_metadata.role → default creator.
    Unknown or invalid roles default to creator (fail-safe, least privilege for admin).
    """
    user = user_record if isinstance(user_record, dict) else {}
    metadata = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}

    email = str(user.get("email") or metadata.get("email") or "").strip().lower()
    if email and email in _admin_emails():
        return "admin"

    meta_role = _normalize_role(metadata.get("role") or metadata.get("user_role"))
    if meta_role == "admin":
        return "admin"
    if meta_role:
        return meta_role

    # Service-side role table hook (optional future extension)
    env_role = _normalize_role(os.getenv(f"TIKTOK_ROLE_{account_id}"))
    if env_role:
        return env_role

    return DEFAULT_ROLE


def getAdminOverride(user_role: str) -> bool:
    return user_role == "admin"


def resolveVisibleModules(
    user_role: str,
    feature_flags: dict[str, bool] | None = None,
    commerce_mode: bool | None = None,
) -> list[str]:
    """
    Build visible_modules for UI rendering.

    Admin override: all modules visible (including disabled-by-flag modules).
    Non-admin: strict feature-flag gating + commerce_mode for commerce modules.
    """
    flags = dict(_load_feature_flags())
    if feature_flags:
        flags.update({str(k): bool(v) for k, v in feature_flags.items()})

    commerce_enabled = bool(flags.get("commerce_mode", False))
    if commerce_mode is not None:
        commerce_enabled = bool(commerce_mode)

    if getAdminOverride(user_role):
        return list(ALL_MODULES)

    visible: list[str] = []
    for module in ALL_MODULES:
        if not flags.get(module, False):
            continue
        if module in COMMERCE_GATED_MODULES and not commerce_enabled:
            continue
        visible.append(module)
    return visible


def buildAccessContext(
    account_id: str,
    user_record: dict[str, Any] | None = None,
    feature_flags: dict[str, bool] | None = None,
    commerce_mode: bool | None = None,
) -> dict[str, Any]:
    user_role = getUserRole(account_id, user_record)
    admin_override = getAdminOverride(user_role)
    visible_modules = resolveVisibleModules(user_role, feature_flags, commerce_mode)
    return {
        "role": user_role,
        "admin_override": admin_override,
        "visible_modules": visible_modules,
    }


def filterLiveStateForAccess(state: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    """
    Strip sensitive observability fields for non-admin users.
    Core business data for enabled modules is preserved; execution rules unchanged.
    """
    if not isinstance(state, dict):
        return {}
    if access.get("admin_override"):
        return dict(state)

    visible = set(access.get("visible_modules") or [])
    filtered = dict(state)

    if "system_health" not in visible:
        filtered["system_health"] = "restricted"
    if "raw_logs" not in visible:
        filtered["raw_logs"] = []
    if "hidden_alerts" not in visible:
        filtered["hidden_alerts"] = []
        filtered["alerts"] = [
            a for a in (filtered.get("alerts") or [])
            if isinstance(a, dict) and a.get("level") != "hidden"
        ]

    if "products" not in visible:
        filtered["products"] = []
    if "inventory_system" not in visible:
        filtered["inventory_gaps"] = []
        filtered["inventory_prevention"] = []
    if "prediction_engine" not in visible:
        filtered["prediction"] = {}
    if "analytics" not in visible:
        filtered["performance"] = {}

    return filtered


def canAccessCommerceMode(access: dict[str, Any], commerce_mode_enabled: bool) -> bool:
    """Admin can access commerce_mode regardless of settings."""
    if access.get("admin_override"):
        return True
    return bool(commerce_mode_enabled)
