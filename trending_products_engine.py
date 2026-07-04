"""
Trending products engine — read-only state for live UI assembly.

Returns cached trending product signals. Never raises.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TABLE = "tiktok_insights_cache"


def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(supabase_url, service_role_key)


def get_state(account_id: str) -> dict[str, Any]:
    """Return {"products": [...]} (trending) for assembleLiveState."""
    try:
        supabase = _get_supabase_client()
        if supabase is None:
            return {"products": []}

        table = os.getenv("TIKTOK_INSIGHTS_CACHE_TABLE", DEFAULT_CACHE_TABLE)
        account = str(account_id or "").strip()
        query = (
            supabase.table(table)
            .select("payload,updated_at")
            .order("updated_at", desc=True)
            .limit(1)
        )
        if account:
            query = query.eq("account_id", account)
        response = query.execute()
        rows = response.data or []
        if not rows:
            return {"products": []}

        payload = rows[0].get("payload") or {}
        if isinstance(payload, str):
            import json
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        products = payload.get("trending_products") or payload.get("trending") or []
        if not isinstance(products, list):
            products = []

        normalized = []
        for item in products:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "name": str(item.get("name") or item.get("product") or "unknown"),
                "signal_strength": item.get("score") or item.get("signal_strength") or 0,
                "source": "trending",
                "confidence": item.get("confidence") or 0,
                "evidence": item.get("evidence") or [],
            })
        return {"products": normalized}
    except Exception as exc:
        logger.warning("trending_products_engine.get_state failed: %s", exc)
        return {"products": []}
