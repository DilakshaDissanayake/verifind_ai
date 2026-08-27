"""User upsert — map JWT sub / AUTH_DEV_BYPASS id → users.id FK."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import text

from infrastructure.db.sql_client import get_session


def ensure_app_user(
    *,
    auth_user_id: str,
    email: Optional[str] = None,
    emergency_contact: Optional[str] = None,
) -> UUID:
    """
    Ensure a `users` row exists for the auth subject.

    Prefer matching on auth_user_id; for first insert use the same UUID as id
    when auth_user_id is a valid UUID (dev bypass + Supabase JWT sub).

    Note: use CAST(:x AS uuid) — not :x::uuid — because SQLAlchemy bind
    params collide with Postgres :: cast syntax.
    """
    email_val = (email or f"{auth_user_id}@verifind.local").strip().lower()
    session = get_session()
    try:
        existing = session.execute(
            text(
                "SELECT id FROM users WHERE auth_user_id = CAST(:aid AS uuid) "
                "OR id = CAST(:aid AS uuid) LIMIT 1"
            ),
            {"aid": auth_user_id},
        ).scalar_one_or_none()
        if existing is not None:
            session.execute(
                text(
                    "UPDATE users SET email = COALESCE(email, :email), "
                    "emergency_contact = COALESCE(:contact, emergency_contact), "
                    "updated_at = now() WHERE id = :id"
                ),
                {"id": existing, "email": email_val, "contact": emergency_contact},
            )
            session.commit()
            return UUID(str(existing))

        row = session.execute(
            text(
                """
                                INSERT INTO users (id, auth_user_id, email, emergency_contact)
                                VALUES (CAST(:aid AS uuid), CAST(:aid AS uuid), :email, :contact)
                ON CONFLICT (auth_user_id) DO UPDATE
                                    SET email = EXCLUDED.email,
                                            emergency_contact = COALESCE(EXCLUDED.emergency_contact, users.emergency_contact),
                                            updated_at = now()
                RETURNING id
                """
            ),
            {"aid": auth_user_id, "email": email_val, "contact": emergency_contact},
        ).scalar_one()
        session.execute(
            text(
                """
                INSERT INTO trust_scores (user_id)
                VALUES (:uid)
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"uid": row},
        )
        session.commit()
        return UUID(str(row))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_profile_summary(user_id: UUID) -> dict:
    """Profile fields + report/chat counts for /me and Profile UI."""
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT u.id, u.email, u.display_name, u.role, u.is_active,
                       (SELECT COUNT(*) FROM reports r
                        WHERE r.user_id = u.id AND r.report_type = 'LOST') AS lost_count,
                       (SELECT COUNT(*) FROM reports r
                        WHERE r.user_id = u.id AND r.report_type = 'FOUND') AS found_count,
                       (SELECT COUNT(*) FROM chat_rooms c
                        WHERE c.is_active = true
                          AND (c.owner_id = u.id OR c.finder_id = u.id)) AS active_chats
                FROM users u
                WHERE u.id = :uid
                LIMIT 1
                """
            ),
            {"uid": str(user_id)},
        ).mappings().first()
    finally:
        session.close()
    if row is None:
        return {
            "email": None,
            "display_name": None,
            "role": "user",
            "is_active": True,
            "lost_count": 0,
            "found_count": 0,
            "active_chats": 0,
        }
    return dict(row)
