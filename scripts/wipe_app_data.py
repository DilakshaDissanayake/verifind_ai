#!/usr/bin/env python3
"""Wipe all VERIFIND domain data for a fresh demo.

Keeps `users` rows (so you can still log in). Deletes reports, matches,
claims, chats, notifications, audit logs, and resets trust scores.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from infrastructure.db.sql_client import get_engine  # noqa: E402


TABLES = [
    "chat_messages",
    "chat_rooms",
    "notifications",
    "verification_sessions",
    "claim_attempts",
    "matches",
    "image_vaults",
    "ai_tags",
    "report_images",
    "reports",
    "audit_logs",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe VERIFIND app data (keep users)")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()
    if not args.yes:
        print("This deletes ALL reports, matches, claims, chats, notifications.")
        print("User accounts are kept. Re-run with --yes to confirm.")
        return 1

    engine = get_engine()
    with engine.begin() as conn:
        # Truncate in FK-safe order; CASCADE covers any extra deps
        joined = ", ".join(TABLES)
        conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
        conn.execute(
            text(
                """
                UPDATE trust_scores
                SET score = 1.0,
                    claim_count_24h = 0,
                    fail_count = 0,
                    lockout_until = NULL,
                    updated_at = now()
                """
            )
        )
        counts = {}
        for t in TABLES:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            counts[t] = int(n or 0)
        users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()

    logger.success("Wipe complete. users kept={}", users)
    for t, n in counts.items():
        logger.info("  {} → {} rows", t, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
