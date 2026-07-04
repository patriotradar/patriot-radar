#!/usr/bin/env python3
"""
Manual / CI trigger for Niche-Aware Comment Signal scan.

Isolated from run_tiktok_trend_scan.py — does not touch existing trend pipeline.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from niche_comment_signal_engine import run_niche_comment_signal_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Niche-Aware Comment Signal scan")
    parser.add_argument(
        "--inputs",
        help="Path to JSON file with video+comment data (skips Apify when set)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Compute only; skip Supabase write",
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

    video_inputs = None
    if args.inputs:
        with open(args.inputs, encoding="utf-8") as f:
            video_inputs = json.load(f)

    result = run_niche_comment_signal_scan(
        video_inputs=video_inputs,
        sample_path=args.inputs,
        persist=not args.no_persist,
        use_apify=not args.no_apify,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    apify_fetch = result.get("apify_fetch") or {}
    store_result = result.get("store_result") or {}

    summary = {
        "success": result.get("success"),
        "data_source": result.get("data_source"),
        "niche_id": result.get("niche_id"),
        "niche_label": result.get("niche_label"),
        "apify_fetch_succeeded": apify_fetch.get("success"),
        "apify_items_returned": apify_fetch.get("item_count", 0),
        "apify_raw_error": apify_fetch.get("error"),
        "apify_token_present": apify_fetch.get("token_present"),
        "video_count": result.get("video_count"),
        "avg_composite_signal": result.get("avg_composite_signal", 0),
        "supabase_rows_stored": store_result.get("stored", 0),
        "supabase_rows_skipped": store_result.get("skipped", 0),
        "supabase_error": store_result.get("error"),
        "local_output": result.get("local_output"),
    }
    print(json.dumps(summary, indent=2))

    if not result.get("success"):
        return 1
    if store_result.get("error") and not args.no_persist:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
