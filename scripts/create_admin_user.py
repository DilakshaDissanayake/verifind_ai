#!/usr/bin/env python3
"""Create / promote a Supabase Auth user as VERIFIND admin (production-ready).

Uses SUPABASE_SERVICE_KEY (Auth Admin API) — never commit passwords.

Examples:
  uv run python scripts/create_admin_user.py --email admin@gmail.com --password '...'
  make create-admin EMAIL=admin@gmail.com PASSWORD='...'
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

from infrastructure.config import get_settings  # noqa: E402
from infrastructure.db.sql_client import get_session  # noqa: E402
from infrastructure.log import setup_logging  # noqa: E402


def _create_or_update_auth_user(*, email: str, password: str) -> str:
    """Return auth user id (UUID string). Confirms email so login works immediately."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env"
        )

    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    email = email.strip().lower()

    # Try create first
    try:
        result = client.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"role": "admin"},
            }
        )
        if result.user and result.user.id:
            logger.info("Created auth user {}", email)
            return str(result.user.id)
    except Exception as exc:
        msg = str(exc).lower()
        if "already" not in msg and "exists" not in msg and "registered" not in msg:
            raise
        logger.warning("Auth user already exists — updating password / confirm")

    # Lookup existing + update password
    listed = client.auth.admin.list_users()
    users = getattr(listed, "users", None) or listed or []
    match = None
    for u in users:
        if str(getattr(u, "email", "") or "").lower() == email:
            match = u
            break
    if match is None:
        raise RuntimeError(
            f"User {email} exists but could not be listed — set password in Dashboard"
        )

    uid = str(match.id)
    client.auth.admin.update_user_by_id(
        uid,
        {
            "password": password,
            "email_confirm": True,
            "user_metadata": {"role": "admin"},
        },
    )
    logger.info("Updated auth user {}", email)
    return uid


def _promote_app_user(*, auth_user_id: str, email: str) -> None:
    email = email.strip().lower()
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO users (id, auth_user_id, email, role)
                VALUES (
                    CAST(:aid AS uuid),
                    CAST(:aid AS uuid),
                    :email,
                    'admin'
                )
                ON CONFLICT (id) DO UPDATE
                  SET email = EXCLUDED.email,
                      role = 'admin',
                      auth_user_id = COALESCE(users.auth_user_id, EXCLUDED.auth_user_id),
                      updated_at = now()
                """
            ),
            {"aid": auth_user_id, "email": email},
        )
        # Also match by email if id conflict path missed a duplicate email row
        session.execute(
            text(
                """
                UPDATE users
                SET role = 'admin', updated_at = now()
                WHERE lower(email) = :email
                """
            ),
            {"email": email},
        )
        session.execute(
            text(
                """
                INSERT INTO trust_scores (user_id)
                VALUES (CAST(:aid AS uuid))
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"aid": auth_user_id},
        )
        session.commit()
        logger.success("App user promoted: {} role=admin id={}", email, auth_user_id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Create VERIFIND admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if len(args.password) < 6:
        logger.error("Password must be at least 6 characters")
        return 1

    try:
        uid = _create_or_update_auth_user(email=args.email, password=args.password)
        _promote_app_user(auth_user_id=uid, email=args.email)
    except Exception as exc:
        logger.exception("create_admin_user failed: {}", exc)
        return 1

    print()
    print("Admin ready:")
    print(f"  email:    {args.email.strip().lower()}")
    print("  password: (the one you passed — not stored in repo)")
    print("  login:    http://localhost:5173  or Flutter")
    print("  require:  AUTH_DEV_BYPASS=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
