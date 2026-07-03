#!/usr/bin/env python3
"""
One-time Supabase backfill: recompute per-user recommendations using existing
stored data + current trends.py output layer (no scanner re-run).

Reads:
  - Supabase auth users (user_metadata.performance)
  - Global trend snapshot (results.json URL or file)

Writes:
  - Versioned rows to cr_recommendation_outputs (safe; does not overwrite raw analytics)
  - Local fallback JSON if Supabase write is disabled or fails
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from trends import build_virality_recommendation

DEFAULT_TRENDS_URL = (
    "https://raw.githubusercontent.com/patriotradar/patriot-radar-dashboard/main/results.json"
)
DEFAULT_OUTPUT_VERSION = "v2-recommendation-layer"
DEFAULT_OUTPUT_TABLE = "cr_recommendation_outputs"


def load_trends_snapshot(path_or_url: str) -> dict:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        resp = requests.get(path_or_url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    with open(path_or_url, encoding="utf-8") as f:
        return json.load(f)


def flatten_performance_entries(performance: dict) -> list[dict]:
    entries = []
    if not isinstance(performance, dict):
        return entries
    for posts in performance.values():
        if not isinstance(posts, list):
            continue
        for post in posts:
            if isinstance(post, dict):
                entries.append(post)
    return entries


def aggregate_engagement_metrics(performance: dict) -> dict | None:
    entries = flatten_performance_entries(performance)
    if not entries:
        return None

    view_samples = []
    like_samples = []
    rate_samples = []

    for entry in entries:
        views = float(entry.get("views", 0) or 0)
        if views <= 0:
            continue
        likes = float(entry.get("likes", 0) or 0)
        comments = float(entry.get("comments", 0) or 0)
        shares = float(entry.get("shares", 0) or 0)
        engagement = likes + comments * 3 + shares * 5
        view_samples.append(views)
        like_samples.append(likes)
        rate_samples.append((engagement / views) * 100)

    if not view_samples:
        return None

    return {
        "avg_views": sum(view_samples) / len(view_samples),
        "avg_likes": sum(like_samples) / len(like_samples),
        "engagement_rate": sum(rate_samples) / len(rate_samples),
        "post_count": len(view_samples),
    }


def extract_user_performance(user: dict) -> dict:
    meta = user.get("user_metadata") or user.get("raw_user_meta_data") or {}
    performance = meta.get("performance") or {}
    return performance if isinstance(performance, dict) else {}


def build_user_output(
    user: dict,
    trends: dict,
    output_version: str,
) -> dict:
    user_id = user.get("id")
    email = user.get("email")
    performance = extract_user_performance(user)
    engagement_metrics = aggregate_engagement_metrics(performance)

    results = trends.get("results") or []
    emerging = trends.get("emerging") or []
    recommendation = build_virality_recommendation(results, emerging, engagement_metrics)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "user_id": user_id,
        "user_email": email,
        "output_version": output_version,
        "state": recommendation["state"],
        "engagement_signal": recommendation["engagement_signal"],
        "insight_summary": recommendation["insight_summary"],
        "next_post": recommendation["next_post"],
        "recommendation_meta": recommendation["based_on"],
        "engagement_metrics": engagement_metrics,
        "trends_last_updated": trends.get("last_updated"),
        "backfilled_at": now,
    }


def list_supabase_users(supabase) -> list[dict]:
    users = []
    page = 1
    per_page = 200

    while True:
        response = supabase.auth.admin.list_users(page=page, per_page=per_page)
        batch = getattr(response, "users", None)
        if batch is None and isinstance(response, dict):
            batch = response.get("users", [])
        if batch is None and isinstance(response, list):
            batch = response
        if not batch:
            break

        for user in batch:
            if hasattr(user, "model_dump"):
                users.append(user.model_dump())
            elif hasattr(user, "dict"):
                users.append(user.dict())
            elif isinstance(user, dict):
                users.append(user)
            else:
                users.append(
                    {
                        "id": getattr(user, "id", None),
                        "email": getattr(user, "email", None),
                        "user_metadata": getattr(user, "user_metadata", {}) or {},
                    }
                )

        if len(batch) < per_page:
            break
        page += 1

    return users


def write_local_fallback(outputs: list[dict], output_dir: Path, output_version: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"backfill_{output_version}_{stamp}.json"
    payload = {
        "output_version": output_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(outputs),
        "outputs": outputs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def upsert_outputs(supabase, table: str, outputs: list[dict]) -> tuple[int, int]:
    success = 0
    failed = 0
    for row in outputs:
        try:
            supabase.table(table).upsert(
                row,
                on_conflict="user_id,output_version",
            ).execute()
            success += 1
        except Exception as exc:
            failed += 1
            print(f"Write failed for {row.get('user_email') or row.get('user_id')}: {exc}")
    return success, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-time Supabase recommendation backfill")
    parser.add_argument(
        "--trends-source",
        default=os.getenv("TRENDS_JSON_URL") or os.getenv("RESULTS_JSON_PATH") or DEFAULT_TRENDS_URL,
        help="URL or local path to results.json trend snapshot",
    )
    parser.add_argument(
        "--output-version",
        default=os.getenv("BACKFILL_OUTPUT_VERSION", DEFAULT_OUTPUT_VERSION),
        help="Version label stored with each row (safe re-runs create/update same version)",
    )
    parser.add_argument(
        "--output-table",
        default=os.getenv("SUPABASE_OUTPUT_TABLE", DEFAULT_OUTPUT_TABLE),
        help="Supabase table for versioned outputs",
    )
    parser.add_argument(
        "--local-fallback-dir",
        default=os.getenv("BACKFILL_LOCAL_DIR", "backfill_outputs"),
        help="Directory for local JSON fallback artifact",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute outputs but do not write to Supabase",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Skip Supabase writes; always save local JSON artifact",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only first N users (0 = all)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.",
            file=sys.stderr,
        )
        return 1

    print(f"Loading trends snapshot from: {args.trends_source}")
    trends = load_trends_snapshot(args.trends_source)
    results_count = len(trends.get("results") or [])
    emerging_count = len(trends.get("emerging") or [])
    print(f"Trends loaded: {results_count} results, {emerging_count} emerging")

    users = []
    supabase = None

    from supabase import create_client

    supabase = create_client(supabase_url, service_role_key)
    users = list_supabase_users(supabase)
    print(f"Loaded {len(users)} Supabase users")

    if args.limit and args.limit > 0:
        users = users[: args.limit]

    outputs = []
    skipped = 0
    for user in users:
        if not user.get("id"):
            skipped += 1
            continue
        outputs.append(build_user_output(user, trends, args.output_version))

    print(f"Computed {len(outputs)} recommendation outputs ({skipped} users skipped)")

    if args.dry_run:
        sample = outputs[:3]
        print(json.dumps(sample, indent=2))
        print("Dry run complete — no data written.")
        return 0

    fallback_path = write_local_fallback(
        outputs,
        Path(args.local_fallback_dir),
        args.output_version,
    )
    print(f"Local fallback artifact: {fallback_path}")

    if args.local_only:
        print("Local-only mode complete.")
        return 0

    success, failed = upsert_outputs(supabase, args.output_table, outputs)
    print(f"Supabase upsert complete: {success} succeeded, {failed} failed")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
