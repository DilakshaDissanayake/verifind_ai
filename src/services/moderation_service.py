"""Admin moderation — content strikes, user block, match decide, contact reveal."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text

from infrastructure.db.sql_client import get_session

CONTENT_STRIKE_LIMIT = 3


@dataclass
class ModerationEvent:
    event_id: UUID
    user_id: UUID
    user_email: Optional[str]
    emergency_contact: Optional[str]
    kind: str
    source: Optional[str]
    snippet: Optional[str]
    strike_number: Optional[int]
    report_id: Optional[UUID]
    match_id: Optional[UUID]
    resolved: bool
    meta: dict[str, Any]
    created_at: Optional[datetime]


def assert_user_can_post(user_id: UUID) -> None:
    """Raise ValueError if account is blocked."""
    session = get_session()
    try:
        row = session.execute(
            text("SELECT is_active FROM users WHERE id = :id LIMIT 1"),
            {"id": str(user_id)},
        ).mappings().first()
    finally:
        session.close()
    if row is None:
        return
    if not row["is_active"]:
        raise PermissionError("Account is blocked. Contact support or wait for admin review.")


def record_prohibited_attempt(
    *,
    user_id: UUID,
    source: str,
    snippet: str,
) -> dict[str, Any]:
    """
    Increment content strikes for prohibited text.
    At CONTENT_STRIKE_LIMIT → auto-block account; post must not be created.
    """
    safe_snippet = (snippet or "")[:160]
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO trust_scores (user_id, content_strike_count)
                VALUES (:uid, 0)
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"uid": str(user_id)},
        )
        row = session.execute(
            text(
                """
                UPDATE trust_scores
                SET content_strike_count = content_strike_count + 1,
                    updated_at = now()
                WHERE user_id = :uid
                RETURNING content_strike_count
                """
            ),
            {"uid": str(user_id)},
        ).mappings().one()
        strike = int(row["content_strike_count"])
        blocked = strike >= CONTENT_STRIKE_LIMIT
        if blocked:
            session.execute(
                text(
                    """
                    UPDATE users SET is_active = false, updated_at = now()
                    WHERE id = :uid
                    """
                ),
                {"uid": str(user_id)},
            )
        event_id = str(uuid4())
        session.execute(
            text(
                """
                INSERT INTO moderation_events
                    (id, user_id, kind, source, snippet, strike_number, meta)
                VALUES
                    (:id, :uid, :kind, :source, :snippet, :strike,
                     CAST(:meta AS jsonb))
                """
            ),
            {
                "id": event_id,
                "uid": str(user_id),
                "kind": "auto_block" if blocked else "content_strike",
                "source": source,
                "snippet": safe_snippet,
                "strike": strike,
                "meta": json.dumps({"blocked": blocked, "limit": CONTENT_STRIKE_LIMIT}),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.warning(
        "content_strike user={} strike={}/{} blocked={}",
        user_id,
        strike,
        CONTENT_STRIKE_LIMIT,
        blocked,
    )
    return {
        "strike_number": strike,
        "limit": CONTENT_STRIKE_LIMIT,
        "blocked": blocked,
        "event_id": event_id,
    }


def set_user_active(
    *,
    user_id: UUID,
    admin_user_id: UUID,
    active: bool,
    reason: str = "",
) -> dict[str, Any]:
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                UPDATE users SET is_active = :active, updated_at = now()
                WHERE id = :uid
                RETURNING id, email, is_active, emergency_contact
                """
            ),
            {"uid": str(user_id), "active": active},
        ).mappings().first()
        if row is None:
            raise ValueError("User not found")
        kind = "admin_unblock" if active else "admin_block"
        session.execute(
            text(
                """
                INSERT INTO moderation_events
                    (id, user_id, kind, source, snippet, meta)
                VALUES
                    (:id, :uid, :kind, 'admin', :snippet, CAST(:meta AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "uid": str(user_id),
                "kind": kind,
                "snippet": (reason or "")[:200],
                "meta": json.dumps({"admin_id": str(admin_user_id), "reason": reason}),
            },
        )
        _audit(
            session,
            actor_id=admin_user_id,
            action=kind,
            entity_type="user",
            entity_id=user_id,
            meta={"reason": reason, "is_active": active},
        )
        session.commit()
        return dict(row)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reveal_user_contact(
    *,
    user_id: UUID,
    admin_user_id: UUID,
    reason: str,
) -> dict[str, Any]:
    """Admin-only contact reveal — always audited."""
    if not (reason or "").strip():
        raise ValueError("reason is required to view emergency contact")
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT id AS user_id, email, display_name, emergency_contact,
                       is_active, role
                FROM users WHERE id = :uid LIMIT 1
                """
            ),
            {"uid": str(user_id)},
        ).mappings().first()
        if row is None:
            raise ValueError("User not found")
        session.execute(
            text(
                """
                INSERT INTO moderation_events
                    (id, user_id, kind, source, snippet, meta)
                VALUES
                    (:id, :uid, 'contact_reveal', 'admin', :snippet,
                     CAST(:meta AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "uid": str(user_id),
                "snippet": reason.strip()[:200],
                "meta": json.dumps({"admin_id": str(admin_user_id)}),
            },
        )
        _audit(
            session,
            actor_id=admin_user_id,
            action="contact_reveal",
            entity_type="user",
            entity_id=user_id,
            meta={"reason": reason.strip()},
        )
        session.commit()
        return dict(row)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def decide_match(
    *,
    match_id: UUID,
    admin_user_id: UUID,
    decision: str,
    note: Optional[str] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Admin PASS (approve) or REJECT an AI match suggestion."""
    decision = decision.upper().strip()
    if decision not in ("PASS", "REJECT"):
        raise ValueError("decision must be PASS or REJECT")
    status = "approved" if decision == "PASS" else "rejected"

    session = get_session()
    try:
        existing = session.execute(
            text(
                """
                SELECT id, score, band, admin_status,
                       ra.category AS cat_a, rb.category AS cat_b
                FROM matches m
                JOIN reports ra ON ra.id = m.report_a_id
                JOIN reports rb ON rb.id = m.report_b_id
                WHERE m.id = :mid
                """
            ),
            {"mid": str(match_id)},
        ).mappings().first()
        if existing is None:
            raise ValueError("Match not found")

        band = str(existing.get("band") or "").upper()
        warning: Optional[str] = None
        if decision == "PASS" and band == "LOW" and not force:
            raise ValueError(
                "LOW-band match requires force=true after manual category check "
                f"(score={float(existing['score']):.2f}, "
                f"{existing.get('cat_a')} ↔ {existing.get('cat_b')})"
            )
        if decision == "PASS" and band == "LOW" and force:
            warning = (
                f"Forced PASS on LOW-band match "
                f"({existing.get('cat_a')} ↔ {existing.get('cat_b')})"
            )

        row = session.execute(
            text(
                """
                UPDATE matches
                SET admin_status = :status,
                    admin_note = :note,
                    admin_decided_at = now(),
                    admin_decided_by = :admin,
                    notified = CASE
                        WHEN :status = 'approved' THEN true
                        ELSE notified
                    END
                WHERE id = :mid
                RETURNING id, report_a_id, report_b_id, score, band, admin_status, notified
                """
            ),
            {
                "mid": str(match_id),
                "status": status,
                "note": (note or "")[:500],
                "admin": str(admin_user_id),
            },
        ).mappings().first()
        if row is None:
            raise ValueError("Match not found")
        session.execute(
            text(
                """
                INSERT INTO moderation_events
                    (id, user_id, kind, source, match_id, snippet, meta)
                VALUES
                    (:id, :admin, 'match_decide', 'admin', :mid, :snippet,
                     CAST(:meta AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "admin": str(admin_user_id),
                "mid": str(match_id),
                "snippet": f"{decision}: {(note or '')[:120]}",
                "meta": json.dumps(
                    {
                        "decision": decision,
                        "admin_status": status,
                        "band": row["band"],
                        "score": float(row["score"]),
                        "force": force,
                    }
                ),
            },
        )
        _audit(
            session,
            actor_id=admin_user_id,
            action=f"match_{status}",
            entity_type="match",
            entity_id=match_id,
            meta={
                "decision": decision,
                "note": note or "",
                "force": force,
                "warning": warning,
            },
        )
        session.commit()
        out = dict(row)
        if warning:
            out["warning"] = warning
        return out
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def resolve_report(
    *,
    report_id: UUID,
    admin_user_id: UUID,
    action: str,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Approve flagged → active, quarantine → flagged, remove → closed."""
    action = action.lower().strip()
    mapping = {
        "approve": "active",
        "quarantine": "flagged",
        "remove": "closed",
    }
    if action not in mapping:
        raise ValueError("action must be approve, quarantine, or remove")
    new_status = mapping[action]

    session = get_session()
    try:
        row = session.execute(
            text(
                """
                UPDATE reports
                SET status = :status, updated_at = now()
                WHERE id = :rid
                RETURNING id AS report_id, user_id, title, status, report_type
                """
            ),
            {"rid": str(report_id), "status": new_status},
        ).mappings().first()
        if row is None:
            raise ValueError("Report not found")
        session.execute(
            text(
                """
                INSERT INTO moderation_events
                    (id, user_id, kind, source, report_id, snippet, resolved,
                     resolved_by, resolved_at, meta)
                VALUES
                    (:id, :uid, 'report_resolve', 'admin', :rid, :snippet, true,
                     :admin, now(), CAST(:meta AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "uid": str(row["user_id"]),
                "rid": str(report_id),
                "snippet": (note or action)[:200],
                "admin": str(admin_user_id),
                "meta": json.dumps({"action": action, "status": new_status}),
            },
        )
        _audit(
            session,
            actor_id=admin_user_id,
            action=f"report_{action}",
            entity_type="report",
            entity_id=report_id,
            meta={"note": note or "", "status": new_status},
        )
        session.commit()
        return dict(row)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_moderation_events(
    *,
    open_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[ModerationEvent]:
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT e.id AS event_id, e.user_id, u.email AS user_email,
                       u.emergency_contact, e.kind, e.source, e.snippet,
                       e.strike_number, e.report_id, e.match_id, e.resolved,
                       e.meta, e.created_at
                FROM moderation_events e
                LEFT JOIN users u ON u.id = e.user_id
                WHERE (:open_only = false OR e.resolved = false)
                  AND e.kind IN (
                    'prohibited_content', 'content_strike', 'auto_block',
                    'admin_block', 'contact_reveal', 'match_decide', 'report_resolve'
                  )
                ORDER BY e.created_at DESC
                LIMIT :lim OFFSET :off
                """
            ),
            {"open_only": open_only, "lim": limit, "off": offset},
        ).mappings().all()
    finally:
        session.close()

    out: list[ModerationEvent] = []
    for row in rows:
        meta = row["meta"] or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        out.append(
            ModerationEvent(
                event_id=row["event_id"],
                user_id=row["user_id"],
                user_email=row["user_email"],
                emergency_contact=row["emergency_contact"],
                kind=row["kind"],
                source=row["source"],
                snippet=row["snippet"],
                strike_number=row["strike_number"],
                report_id=row["report_id"],
                match_id=row["match_id"],
                resolved=bool(row["resolved"]),
                meta=meta if isinstance(meta, dict) else {},
                created_at=row["created_at"],
            )
        )
    return out


def mark_event_resolved(*, event_id: UUID, admin_user_id: UUID) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE moderation_events
                SET resolved = true, resolved_by = :admin, resolved_at = now()
                WHERE id = :id
                """
            ),
            {"id": str(event_id), "admin": str(admin_user_id)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _audit(
    session: Any,
    *,
    actor_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    meta: dict[str, Any],
) -> None:
    session.execute(
        text(
            """
            INSERT INTO audit_logs (id, actor_id, action, entity_type, entity_id, meta)
            VALUES (:id, :actor, :action, :etype, :eid, CAST(:meta AS jsonb))
            """
        ),
        {
            "id": str(uuid4()),
            "actor": str(actor_id),
            "action": action,
            "etype": entity_type,
            "eid": str(entity_id),
            "meta": json.dumps(meta),
        },
    )
