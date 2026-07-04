#!/usr/bin/env python3
"""
Apply trend_intelligence_feed DDL to Supabase Postgres.

Requires SUPABASE_DB_URL (direct Postgres connection string from Supabase Dashboard
→ Project Settings → Database → Connection string → URI).

Safe to run multiple times (SQL uses IF NOT EXISTS).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQL = ROOT / "sql" / "trend_intelligence_feed_setup.sql"


def _load_sql(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def _apply_with_psycopg2(db_url: str, sql: str) -> None:
    import psycopg2

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply trend_intelligence_feed schema to Supabase")
    parser.add_argument(
        "--sql",
        default=str(DEFAULT_SQL),
        help="Path to SQL setup file (default: sql/trend_intelligence_feed_setup.sql)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print SQL only, do not execute")
    args = parser.parse_args()

    db_url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    sql_path = Path(args.sql)

    try:
        sql = _load_sql(sql_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(sql)
        return 0

    if not db_url:
        print(
            "ERROR: SUPABASE_DB_URL (or DATABASE_URL) is required to apply schema.\n"
            "Get it from Supabase Dashboard → Project Settings → Database → Connection string (URI).\n"
            "Alternatively, paste sql/trend_intelligence_feed_setup.sql into the Supabase SQL Editor.",
            file=sys.stderr,
        )
        return 1

    try:
        _apply_with_psycopg2(db_url, sql)
    except ImportError:
        print(
            "ERROR: psycopg2 is required. Install with: pip install psycopg2-binary",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"ERROR: Schema apply failed: {exc}", file=sys.stderr)
        return 1

    print(f"Schema applied successfully from {sql_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
