"""
Queue enhancement — optional commerce pipeline step.

Adds product CTAs and monetisation metadata to content queue items.
"""

from __future__ import annotations

from typing import Any


def enhance_content_queue(
    account_id: str,
    attachments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Enhance queued content with product attachment metadata.

    Never raises; returns empty list on failure.
    """
    if not isinstance(attachments, list):
        return []

    enhanced: list[dict[str, Any]] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        if attachment.get("status") != "attached":
            continue
        enhanced.append({
            "account_id": account_id,
            "product_name": attachment.get("product_name", ""),
            "product_id": attachment.get("product_id"),
            "keyword": attachment.get("keyword", ""),
            "cta": f"Pin {attachment.get('product_name', 'product')} link in comments",
            "enhancement_type": "product_cta",
            "status": "queued",
        })

    return enhanced
