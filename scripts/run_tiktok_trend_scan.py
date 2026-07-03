#!/usr/bin/env python3
"""
Manual / CI trigger for TikTok trend intelligence scan.

Extracts external TikTok signals and persists to trend_intelligence_feed.
Does not modify trends.py scoring or recommendation selection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trend_shift_engine import run_tiktok_trend_scan


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TikTok trend intelligence scan")
    parser.add_argument(
        "--inputs",
        help="Path to JSON file with TikTok URLs or caption strings",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Extract only; skip Supabase write",
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
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    print(json.dumps({
        "success": result.get("success"),
        "item_count": result.get("item_count"),
        "store_result": result.get("store_result"),
        "insight_summary": result.get("insight_summary", "")[:200],
    }, indent=2))

    if not result.get("success"):
        return 1
    if result.get("store_result", {}).get("error"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
