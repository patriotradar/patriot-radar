#!/usr/bin/env python3
"""CLI runner for the action orchestration layer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from action_orchestrator import generatePrimaryActions
from tiktok_live_state_assembler import assembleLiveState


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate primary actions from live state")
    parser.add_argument(
        "--mode",
        choices=["assemble", "direct"],
        default="assemble",
        help="assemble = build live_state then orchestrate; direct = read JSON input",
    )
    parser.add_argument("--account-id", default="demo_account", help="Account ID for assemble mode")
    parser.add_argument(
        "--input",
        help="Path to live_state JSON for direct mode",
    )
    parser.add_argument(
        "--commerce-mode",
        choices=["true", "false", "auto"],
        default="auto",
        help="Commerce mode override for assemble mode",
    )
    parser.add_argument("--user-role", default="creator", help="User role (creator, business, admin)")
    parser.add_argument(
        "--admin-override",
        action="store_true",
        help="Include admin debug secondary actions",
    )
    parser.add_argument("--output", help="Write JSON result to file")
    args = parser.parse_args()

    if args.mode == "direct":
        if not args.input:
            print("Error: --input required for direct mode", file=sys.stderr)
            return 1
        live_state = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = generatePrimaryActions(live_state)
    else:
        commerce_mode = None
        if args.commerce_mode == "true":
            commerce_mode = True
        elif args.commerce_mode == "false":
            commerce_mode = False

        live_state = assembleLiveState(
            args.account_id,
            commerce_mode=commerce_mode,
            user_role=args.user_role,
            admin_override=args.admin_override,
        )
        result = {
            "live_state": live_state,
            "actions": generatePrimaryActions(live_state),
        }

    payload = json.dumps(result, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
