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
    flags = dict(_load_feature_flags())
    if feature_flags:
        flags.update({str(k): bool(v) for k, v in feature_flags.items()})
    commerce_enabled = bool(flags.get("commerce_mode", False))
    if commerce_mode is not None:
        commerce_enabled = bool(commerce_mode)
    return {
        "role": user_role,
        "admin_override": admin_override,
        "visible_modules": visible_modules,
        "commerce_access": canAccessCommerceMode(
            {"admin_override": admin_override}, commerce_enabled
        ),
    }


def empty_live_state_contract() -> dict[str, Any]:
    """Canonical live-state schema — every role must return this exact key set."""
    return {
        "today_flow": {
            "step": "trend → product → content → queue",
            "next_action": "unknown",
            "status": "unknown",
        },
        "trends": [],
        "products": [],
        "inventory_gaps": [],
        "inventory_prevention": [],
        "content_queue": [],
        "approvals": [],
        "performance": {},
        "prediction": {},
        "alerts": [],
        "hidden_alerts": [],
        "raw_logs": [],
        "primary_action": {
            "label": "unknown",
            "action": "unknown",
            "context_id": "unknown",
        },
        "system_health": "unknown",
        "access": {
            "role": DEFAULT_ROLE,
            "admin_override": False,
            "visible_modules": [],
            "commerce_access": False,
        },
    }


LIVE_STATE_SCHEMA_KEYS = frozenset(empty_live_state_contract().keys())


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def normalize_live_state_shape(
    state: dict[str, Any] | None,
    access: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Guarantee the full live-state schema is always present.
    Missing keys are filled with safe defaults; never omits fields.
    """
    base = empty_live_state_contract()
    if not isinstance(state, dict):
        if access:
            base["access"] = {**base["access"], **_as_dict(access)}
        return base

    normalized = empty_live_state_contract()
    normalized["today_flow"] = {**base["today_flow"], **_as_dict(state.get("today_flow"))}
    normalized["primary_action"] = {**base["primary_action"], **_as_dict(state.get("primary_action"))}
    normalized["access"] = {**base["access"], **_as_dict(state.get("access"))}
    if access:
        normalized["access"] = {**normalized["access"], **_as_dict(access)}

    normalized["trends"] = _as_list(state.get("trends"))
    normalized["products"] = _as_list(state.get("products"))
    normalized["inventory_gaps"] = _as_list(state.get("inventory_gaps"))
    normalized["inventory_prevention"] = _as_list(state.get("inventory_prevention"))
    normalized["content_queue"] = _as_list(state.get("content_queue"))
    normalized["approvals"] = _as_list(state.get("approvals"))
    normalized["alerts"] = _as_list(state.get("alerts"))
    normalized["hidden_alerts"] = _as_list(state.get("hidden_alerts"))
    normalized["raw_logs"] = _as_list(state.get("raw_logs"))
    normalized["performance"] = _as_dict(state.get("performance"))
    normalized["prediction"] = _as_dict(state.get("prediction"))

    health = state.get("system_health")
    normalized["system_health"] = (
        str(health).strip() if health is not None and str(health).strip() else base["system_health"]
    )

    return normalized


def _redact_list_content(items: list) -> list:
    return []


def _redact_dict_content(value: dict) -> dict:
    return {}


def filterLiveStateForAccess(state: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    """
    Apply RBAC content redaction while preserving the full live-state schema.

    Never removes keys. Non-admins receive empty arrays, empty objects, or
    sentinel strings (restricted/hidden) instead of sensitive content.
    """
    access_ctx = _as_dict(access)
    normalized = normalize_live_state_shape(state, access_ctx)

    if access_ctx.get("admin_override"):
        return normalized

    visible = set(access_ctx.get("visible_modules") or [])

    if "trends" not in visible:
        normalized["trends"] = _redact_list_content(normalized["trends"])
    if "products" not in visible:
        normalized["products"] = _redact_list_content(normalized["products"])
    if "inventory_system" not in visible:
        normalized["inventory_gaps"] = _redact_list_content(normalized["inventory_gaps"])
        normalized["inventory_prevention"] = _redact_list_content(normalized["inventory_prevention"])
    if "prediction_engine" not in visible:
        normalized["prediction"] = _redact_dict_content(normalized["prediction"])
    if "analytics" not in visible:
        normalized["performance"] = _redact_dict_content(normalized["performance"])
        normalized["content_queue"] = _redact_list_content(normalized["content_queue"])
        normalized["approvals"] = _redact_list_content(normalized["approvals"])
    if "system_health" not in visible:
        normalized["system_health"] = "restricted"
    if "raw_logs" not in visible:
        normalized["raw_logs"] = _redact_list_content(normalized["raw_logs"])
    if "hidden_alerts" not in visible:
        normalized["hidden_alerts"] = _redact_list_content(normalized["hidden_alerts"])
        normalized["alerts"] = [
            a for a in normalized["alerts"]
            if isinstance(a, dict) and a.get("level") != "hidden"
        ]

    return normalized


def canAccessCommerceMode(access: dict[str, Any], commerce_mode_enabled: bool) -> bool:
    """Admin can access commerce_mode regardless of settings."""
    if access.get("admin_override"):
        return True
    return bool(commerce_mode_enabled)
