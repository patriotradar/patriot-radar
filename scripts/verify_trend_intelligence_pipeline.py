#!/usr/bin/env python3
"""
End-to-end diagnostic for TikTok trend intelligence pipeline.

Traces: env → Supabase table → row count → local extraction smoke test.
Exit 0 when table exists and (optionally) rows are present; non-zero on hard failures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_TABLE = "trend_intelligence_feed"


def _mask(value: str | None) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def _probe_supabase_table(table: str) -> dict:
    """Return {ok, row_count, error, table_missing}."""
    result: dict = {
        "ok": False,
        "row_count": None,
        "error": None,
        "table_missing": False,
        "supabase_url": os.getenv("SUPABASE_URL") or "(missing)",
    }

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        result["error"] = "missing_supabase_credentials"
        return result

    try:
        from supabase import create_client

        client = create_client(url, key)
        response = (
            client.table(table)
            .select("id", count="exact")
            .eq("source", "tiktok")
            .limit(1)
            .execute()
        )
        result["ok"] = True
        result["row_count"] = getattr(response, "count", None)
        if result["row_count"] is None:
            result["row_count"] = len(response.data or [])
        return result
    except Exception as exc:
        msg = str(exc)
        result["error"] = msg
        if "PGRST205" in msg or "Could not find the table" in msg:
            result["table_missing"] = True
        return result


def _extraction_smoke_test() -> dict:
    from trend_shift_engine import run_tiktok_trend_scan

    scan = run_tiktok_trend_scan(use_apify=False, persist=False)
    return {
        "success": scan.get("success"),
        "extracted_item_count": scan.get("item_count", 0),
        "avg_virality_score": scan.get("avg_virality_score", 0),
        "data_source": scan.get("data_source"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify TikTok trend intelligence pipeline")
    parser.add_argument("--table", default=os.getenv("SUPABASE_FEED_TABLE", DEFAULT_TABLE))
    parser.add_argument("--require-rows", action="store_true", help="Fail if table has zero rows")
    parser.add_argument("--json", action="store_true", help="Print JSON report only")
    args = parser.parse_args()

    report: dict = {
        "env": {
            "SUPABASE_URL": _mask(os.getenv("SUPABASE_URL")),
            "SUPABASE_SERVICE_ROLE_KEY": _mask(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
            "APIFY_API_TOKEN": _mask(os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")),
            "SUPABASE_FEED_TABLE": args.table,
        },
        "supabase_probe": _probe_supabase_table(args.table),
        "extraction_smoke_test": _extraction_smoke_test(),
    }

    probe = report["supabase_probe"]
    extraction = report["extraction_smoke_test"]
    failures: list[str] = []

    if probe.get("table_missing"):
        failures.append(
            f"Table public.{args.table} does not exist. "
            "Run: python scripts/apply_trend_feed_schema.py "
            "(needs SUPABASE_DB_URL) or paste sql/trend_intelligence_feed_setup.sql in Supabase SQL Editor."
        )
    elif probe.get("error"):
        failures.append(f"Supabase probe failed: {probe['error']}")
    elif args.require_rows and (probe.get("row_count") or 0) == 0:
        failures.append(
            f"Table {args.table} exists but has 0 tiktok rows. Run TikTok Trend Intelligence Scan workflow."
        )

    if not extraction.get("success") or extraction.get("extracted_item_count", 0) == 0:
        failures.append("Local extraction smoke test produced zero items.")

    report["ok"] = len(failures) == 0
    report["failures"] = failures

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== TikTok Trend Intelligence Pipeline Diagnostic ===")
        print(json.dumps(report, indent=2))
        if failures:
            print("\nFAILURES:")
            for f in failures:
                print(f"  - {f}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
