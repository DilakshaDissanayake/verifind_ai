#!/usr/bin/env python3
"""Ensure public-sanitized + private-vault storage buckets exist."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from infrastructure.db.supabase_client import ensure_buckets  # noqa: E402
from infrastructure.log import setup_logging  # noqa: E402


def main() -> int:
    setup_logging()
    result = ensure_buckets()
    if result.get("ok"):
        logger.success("Buckets OK (created={})", result.get("created") or [])
        return 0
    logger.error("ensure_buckets failed: {}", result.get("error"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
