#!/usr/bin/env python3
"""Apply sql/schema.sql to SUPABASE_DB_URL / DATABASE_URL."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from infrastructure.db.sql_client import get_engine  # noqa: E402
from infrastructure.log import setup_logging  # noqa: E402


def main() -> int:
    setup_logging()
    schema_path = ROOT / "sql" / "schema.sql"
    if not schema_path.is_file():
        logger.error("Missing {}", schema_path)
        return 1

    sql = schema_path.read_text(encoding="utf-8")
    logger.info("Applying {} …", schema_path)
    engine = get_engine()
    with engine.begin() as conn:
        # Split on statement boundaries; keep extension/table DDL simple.
        for stmt in _split_sql(sql):
            conn.execute(text(stmt))
    logger.success("Schema applied.")
    return 0


def _split_sql(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            chunk = "\n".join(buf).strip()
            if chunk:
                parts.append(chunk)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


if __name__ == "__main__":
    raise SystemExit(main())
