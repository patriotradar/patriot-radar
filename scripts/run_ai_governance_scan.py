#!/usr/bin/env python3
"""CLI entry point for AI Code Governance scans (hourly / on-demand)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_governance_pipeline import run_governance_scan

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI Code Governance scan pipeline")
    parser.add_argument("--no-persist", action="store_true", help="Do not write to Supabase")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    args = parser.parse_args()

    results = run_governance_scan(persist=not args.no_persist)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        logger.info("Governance scan complete: %d issue(s)", len(results))
        for item in results:
            logger.info(
                "  [%s/%s] %s",
                item.get("risk"),
                item.get("gemini_status"),
                item.get("issue", "")[:80],
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
