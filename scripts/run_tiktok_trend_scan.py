#!/usr/bin/env python3
"""
Manual / CI trigger for TikTok trend intelligence scan.

Extracts external TikTok signals and persists to trend_intelligence_feed.
Does not modify trends.py scoring or recommendation selection.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trend_shift_engine import run_tiktok_trend_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TikTok trend intelligence scan")
    parser.add_argument(
        "--inputs",
        help="Path to JSON file with TikTok URLs or caption strings (skips Apify when set)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Extract only; skip Supabase write",
    )
    parser.add_argument(
        "--no-apify",
        action="store_true",
        help="Skip Apify fetch; use --inputs or sample file only",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write scan result JSON",
    )
    args = parser.parse_args()

    inputs = None
    if args.inputs:
        with open(args.inputs, encoding="utf-8") as f:
            inputs = json.load(f)

    result = run_tiktok_trend_scan(
        tiktok_inputs=inputs,
        sample_inputs_path=args.inputs,
        persist=not args.no_persist,
        use_apify=not args.no_apify,
    )

    apify_fetch = result.get("apify_fetch") or {}
    store_result = result.get("store_result") or {}

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    summary = {
        "success": result.get("success"),
        "data_source": result.get("data_source"),
        "apify_fetch_succeeded": apify_fetch.get("success"),
        "apify_items_returned": apify_fetch.get("item_count", 0),
        "apify_raw_error": apify_fetch.get("error"),
        "apify_token_present": apify_fetch.get("token_present"),
        "apify_run_id": apify_fetch.get("apify_run_id"),
        "extracted_item_count": result.get("item_count"),
        "avg_virality_score": result.get("avg_virality_score", 0),
        "supabase_rows_stored": store_result.get("stored", 0),
        "supabase_rows_skipped": store_result.get("skipped", 0),
        "supabase_error": store_result.get("error"),
        "supabase_feed_row_count": (store_result.get("table_probe") or {}).get("row_count"),
        "insight_summary": (result.get("insight_summary") or "")[:200],
    }
    print(json.dumps(summary, indent=2))

    if not result.get("success"):
        return 1
    if apify_fetch.get("fallback_refused"):
        return 3
    if store_result.get("error"):
        return 2
    if summary["data_source"] == "apify" and summary["supabase_rows_stored"] == 0 and summary["extracted_item_count"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
