#!/usr/bin/env python3
"""Ping Postgres and check PostGIS + pgvector extensions."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from infrastructure.db.sql_client import get_engine, ping_db  # noqa: E402
from infrastructure.log import setup_logging  # noqa: E402


def _ext_ok(name: str) -> bool:
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = :n"),
            {"n": name},
        ).scalar()
    return bool(row)


def main() -> int:
    setup_logging()
    logger.info("Testing database connection…")
    ok = ping_db()
    if not ok:
        logger.error("SELECT 1 failed — check SUPABASE_DB_URL")
        return 1
    logger.success("Connection OK")

    postgis = _ext_ok("postgis")
    pgvector = _ext_ok("vector")
    logger.info("postgis={}  pgvector={}", postgis, pgvector)

    if postgis and pgvector:
        logger.success("All DB checks passed.")
        return 0

    logger.error("Missing extensions. Run: make init-schema")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
