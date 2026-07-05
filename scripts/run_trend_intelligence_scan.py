#!/usr/bin/env python3
"""Run multi-source trend intelligence scan (CI / cron entry point)."""

from __future__ import annotations

import argparse
import json
import logging
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
    args = parser.parse_args()

    logger.info("Starting trend intelligence scan for niche=%s", args.niche)
    report = run_trend_intelligence_scan(
        niche=args.niche,
        persist=not args.no_persist,
        store_feed=not args.no_feed,
    )

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

    if args.json:
        print(json.dumps(report, indent=2))
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
