#!/usr/bin/env python3
"""
Manual / CI trigger for TikTok Shop content pipeline with inventory gate.

Runs content stages end-to-end; pauses ONLY product attachment when catalog inventory is missing.
Does not modify trends.py or existing TikTok trend scan pipelines.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tiktok_shop_content_pipeline import (
    resumeAfterInventoryUpdate,
    run_tiktok_shop_content_pipeline,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DEFAULT_CATALOG = ROOT / "data" / "tiktok_shop_sample_catalog.json"
DEFAULT_ITEMS = ROOT / "data" / "tiktok_shop_sample_content_items.json"


def _load_json(path: Path) -> list | dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run TikTok Shop content pipeline with inventory gate",
    )
    parser.add_argument("--account-id", default="demo_account", help="Creator account ID")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="Path to TikTok Shop catalog JSON",
    )
    parser.add_argument(
        "--items",
        type=Path,
        default=DEFAULT_ITEMS,
        help="Path to content items JSON",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume paused attachments after Showcase update (re-check catalog only)",
    )
    parser.add_argument(
        "--content-id",
        help="Optional content_id when resuming a single paused attachment",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write result JSON",
    )
    args = parser.parse_args()

    catalog = _load_json(args.catalog)
    if not isinstance(catalog, list):
        print("Catalog must be a JSON array", file=sys.stderr)
        return 1

    if args.resume:
        result = resumeAfterInventoryUpdate(
            args.account_id,
            catalog,
            content_id=args.content_id,
        )
    else:
        items = _load_json(args.items)
        if not isinstance(items, list):
            print("Content items must be a JSON array", file=sys.stderr)
            return 1
        result = run_tiktok_shop_content_pipeline(
            account_id=args.account_id,
            content_items=items,
            tiktok_shop_catalog=catalog,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logging.info("Wrote result to %s", args.output)

    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
