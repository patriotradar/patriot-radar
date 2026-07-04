#!/usr/bin/env python3
"""CLI for the hardened TikTok insights + recommendation pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tiktok_insights_pipeline import run_hardened_tiktok_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run hardened TikTok insights pipeline")
    parser.add_argument("--niche", default="", help="Niche query for insight generation")
    parser.add_argument("--no-apify", action="store_true", help="Use sample data instead of Apify")
    parser.add_argument("--persist", action="store_true", help="Persist trend signals to Supabase")
    parser.add_argument("--output", help="Write JSON output to file")
    args = parser.parse_args()

    result = run_hardened_tiktok_pipeline(
        niche=args.niche,
        use_apify=not args.no_apify,
        persist_signals=args.persist,
    )

    payload = json.dumps(result, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(payload)

    return 0 if result.get("success", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
