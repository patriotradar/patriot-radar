"""
TikTok Shop attachment — optional commerce pipeline step.

Pauses only product attachment when inventory is missing; never blocks core content.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def attach_products_to_content(
    account_id: str,
    products: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Match products to catalog and attempt attachment.

    Returns (attachments, inventory_gaps). Never raises.
    """
    attachments: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    if not isinstance(products, list):
        return attachments, gaps

    try:
        from tiktok_shop_inventory_gate import checkProductAvailability
    except ImportError:
        logger.debug("tiktok_shop_inventory_gate unavailable — skipping attachment")
        return attachments, gaps

    safe_catalog = catalog if isinstance(catalog, list) else []

    for product in products:
        if not isinstance(product, dict):
            continue
        name = str(product.get("name") or product.get("product_name") or "").strip()
        if not name:
            continue
        try:
            availability = checkProductAvailability(name, safe_catalog)
        except Exception as exc:
            logger.warning("checkProductAvailability failed for %r: %s", name, exc)
            continue

        if availability.get("attachable"):
            attachments.append({
                "product_name": name,
                "product_id": availability.get("product_id"),
                "keyword": product.get("keyword", ""),
                "status": "attached",
                "account_id": account_id,
            })
        else:
            gaps.append({
                "product_name": name,
                "keyword": product.get("keyword", ""),
                "category": availability.get("category", "general"),
                "action_required": availability.get("action_required", "add_to_showcase"),
                "message": f"Add '{name}' to your TikTok Shop Showcase",
                "status": "waiting_user_action",
            })

    return attachments, gaps
