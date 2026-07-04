#!/usr/bin/env python3
"""CI/CLI runner for the Virality Intelligence learning pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virality_feedback_loop import run_learning_cycle
from virality_intelligence_engine import compute_intelligent_predictions
from virality_snapshot_store import fetch_raw_comment_rows
from niche_comment_virality_engine import load_sample_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Virality Intelligence learning pipeline")
    parser.add_argument(
        "--mode",
        choices=["learn", "predict"],
        default="learn",
        help="learn = full feedback loop; predict = enhanced predictions only",
    )
    parser.add_argument("--niche", help="Niche for predict mode")
    parser.add_argument(
        "--sample",
        default=str(ROOT / "data" / "tiktok_comment_sample.json"),
        help="Sample JSON when Supabase unavailable",
    )
    parser.add_argument("--use-sample", action="store_true", help="Force sample data")
    parser.add_argument("--output", help="Write JSON result to file")
    args = parser.parse_args()

    if args.use_sample or not fetch_raw_comment_rows(limit=1):
        rows = load_sample_rows(args.sample)
        data_source = "sample"
    else:
        rows = fetch_raw_comment_rows()
        data_source = "supabase"

    if args.mode == "learn":
        result = run_learning_cycle(raw_rows=rows)
        result["data_source"] = data_source
    else:
        niche = args.niche or "fitness"
        result = compute_intelligent_predictions(rows, niche, persist_snapshots=True, persist_explanations=True)
        result["data_source"] = data_source

    payload = json.dumps(result, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(payload)

    return 0 if result.get("success", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
