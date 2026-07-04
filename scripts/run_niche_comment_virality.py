#!/usr/bin/env python3
"""CLI for niche comment early virality prediction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from niche_comment_virality_engine import compute_virality_predictions, load_sample_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run niche comment virality prediction")
    parser.add_argument("--niche", required=True, help="Niche query (e.g. fitness, skincare)")
    parser.add_argument(
        "--sample",
        default=str(ROOT / "data" / "tiktok_comment_sample.json"),
        help="Path to sample JSON (used when no Supabase)",
    )
    parser.add_argument("--output", help="Write JSON output to file")
    args = parser.parse_args()

    rows = load_sample_rows(args.sample)
    result = compute_virality_predictions(rows, args.niche)

    payload = json.dumps(result, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(payload)

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
