#!/usr/bin/env python3
"""Run multi-source trend intelligence scan (CI / cron entry point)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trend_intelligence_engine import run_trend_intelligence_scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="CreatorRadar multi-source trend intelligence scan")
    parser.add_argument("--niche", default="general", help="Niche to scan (default: general)")
    parser.add_argument("--no-persist", action="store_true", help="Skip Supabase persistence")
    parser.add_argument("--no-feed", action="store_true", help="Skip trend_intelligence_feed writes")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--output", help="Write JSON report to file (clean; avoids stdout noise)")
    args = parser.parse_args()

    def _execute_scan() -> dict:
        return run_trend_intelligence_scan(
            niche=args.niche,
            persist=not args.no_persist,
            store_feed=not args.no_feed,
        )

    try:
        logger.info("Starting trend intelligence scan for niche=%s", args.niche)
        if args.json or args.output:
            saved_stdout = os.dup(1)
            devnull = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(devnull, 1)
                report = _execute_scan()
            finally:
                os.dup2(saved_stdout, 1)
                os.close(devnull)
                os.close(saved_stdout)
        else:
            report = _execute_scan()
    except Exception as exc:
        logger.exception("Trend intelligence scan crashed: %s", exc)
        report = {
            "niche": args.niche,
            "timestamp": None,
            "trend_count": 0,
            "opportunity_count": 0,
            "providers_online": [],
            "providers_offline": [],
            "warnings": [f"Scan crashed: {exc}"],
            "stored": {},
            "recommendations": {},
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(json.dumps({"error": str(exc), "success": False}, indent=2))
        return 1

    online = report.get("providers_online", [])
    offline = report.get("providers_offline", [])
    warnings = report.get("warnings", [])

    logger.info(
        "Scan complete: trends=%s opportunities=%s online=%s offline=%s",
        report.get("trend_count", 0),
        report.get("opportunity_count", 0),
        len(online),
        len(offline),
    )

    for warning in warnings:
        logger.warning(warning)

    if args.json or args.output:
        payload = json.dumps(report, indent=2)
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + "\n", encoding="utf-8")
        if args.json:
            print(payload)
    else:
        summary = {
            "niche": report.get("niche"),
            "timestamp": report.get("timestamp"),
            "trend_count": report.get("trend_count"),
            "opportunity_count": report.get("opportunity_count"),
            "providers_online": online,
            "providers_offline": offline,
            "warnings": warnings,
            "stored": report.get("stored"),
            "primary_action": (report.get("recommendations") or {}).get("primary_action"),
        }
        print(json.dumps(summary, indent=2))

    # Success if at least one provider returned data
    if report.get("trend_count", 0) > 0 or report.get("opportunity_count", 0) > 0:
        return 0
    if online:
        logger.warning("Scan ran but returned zero trends — check provider warnings")
        return 0
    logger.error("All providers offline — scan produced no data")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
