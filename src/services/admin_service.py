"""Admin REVIEW queue — Sprint 6.

Admin-only: list medium-risk claims, side-by-side vault vs public,
decide PASS (provision chat) or BLOCK (trust penalty + audit).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text

from infrastructure.db.sql_client import get_session
from infrastructure.storage.image_storage import public_url, signed_vault_url


@dataclass
class ReviewQueueItem:
    claim_attempt_id: UUID
    verification_session_id: Optional[UUID]
    match_id: UUID
    claimant_id: UUID
    claimant_email: Optional[str]
    status: str
    risk_score: Optional[float]
    fraud_risk: Optional[float]
    overall_score: Optional[float]
    decision: Optional[str]
    found_report_title: Optional[str]
    created_at: Optional[datetime]


@dataclass
class ReviewDetail:
    claim_attempt_id: UUID
    verification_session_id: Optional[UUID]
    match_id: UUID
    claimant_id: UUID
    claimant_email: Optional[str]
    claimant_emergency_contact: Optional[str]
    status: str
    risk_score: Optional[float]
    fraud_risk: Optional[float]
    overall_score: Optional[float]
    decision: Optional[str]
    questions: list[dict[str, Any]]
    answers: list[str]
    semantic_scores: Optional[list[float]]
    vault_features: Optional[dict[str, Any]]
    public_image_url: Optional[str]
    vault_image_url: Optional[str]
    found_report_id: Optional[UUID]
    lost_report_id: Optional[UUID]
    found_report_title: Optional[str]
    owner_email: Optional[str]
    owner_emergency_contact: Optional[str]
    created_at: Optional[datetime]
    completed_at: Optional[datetime]


def list_review_queue(*, limit: int = 50, offset: int = 0) -> list[ReviewQueueItem]:
    """Claims awaiting admin REVIEW (status=review or decision=REVIEW)."""
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT ca.id AS claim_attempt_id,
                       vs.id AS verification_session_id,
                       ca.match_id,
                       ca.claimant_id,
                       u.email AS claimant_email,
                       ca.status,
                       ca.risk_score,
                       ca.fraud_risk,
                       vs.overall_score,
                       vs.decision,
                       rb.title AS found_report_title,
                       ca.created_at
                FROM claim_attempts ca
                LEFT JOIN verification_sessions vs ON vs.claim_attempt_id = ca.id
                LEFT JOIN users u ON u.id = ca.claimant_id
                LEFT JOIN matches m ON m.id = ca.match_id
                LEFT JOIN reports rb ON rb.id = m.report_b_id
                WHERE ca.status = 'review'
                   OR vs.decision = 'REVIEW'
                ORDER BY ca.created_at DESC
                LIMIT :lim OFFSET :off
                """
            ),
            {"lim": limit, "off": offset},
        ).mappings().all()
    finally:
        session.close()

    return [
        ReviewQueueItem(
            claim_attempt_id=row["claim_attempt_id"],
            verification_session_id=row["verification_session_id"],
            match_id=row["match_id"],
            claimant_id=row["claimant_id"],
            claimant_email=row["claimant_email"],
            status=row["status"],
            risk_score=row["risk_score"],
            fraud_risk=row["fraud_risk"],
            overall_score=row["overall_score"],
            decision=row["decision"],
            found_report_title=row["found_report_title"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def get_review_detail(claim_attempt_id: UUID) -> Optional[ReviewDetail]:
    """Admin detail: vault signed URL + public URL + features (never for public APIs)."""
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT ca.id AS claim_attempt_id,
                       vs.id AS verification_session_id,
                       ca.match_id,
                       ca.claimant_id,
                       u.email AS claimant_email,
                       u.emergency_contact AS claimant_emergency_contact,
                       ca.status,
                       ca.risk_score,
                       ca.fraud_risk,
                       vs.overall_score,
                       vs.decision,
                       vs.questions,
                       vs.answers,
                       vs.semantic_scores,
                       vs.vault_features,
                       vs.completed_at,
                       ca.created_at,
                       m.report_a_id AS lost_report_id,
                       m.report_b_id AS found_report_id,
                       rb.title AS found_report_title,
                       ou.email AS owner_email,
                       ou.emergency_contact AS owner_emergency_contact
                FROM claim_attempts ca
                LEFT JOIN verification_sessions vs ON vs.claim_attempt_id = ca.id
                LEFT JOIN users u ON u.id = ca.claimant_id
                LEFT JOIN matches m ON m.id = ca.match_id
                LEFT JOIN reports rb ON rb.id = m.report_b_id
                LEFT JOIN users ou ON ou.id = rb.user_id
                WHERE ca.id = :id
                """
            ),
            {"id": str(claim_attempt_id)},
        ).mappings().first()
    finally:
        session.close()

    if row is None:
        return None

    found_id = row["found_report_id"]
    public_image_url, vault_image_url, vault_features = _resolve_images(
        found_id, row.get("vault_features")
    )

    return ReviewDetail(
        claim_attempt_id=row["claim_attempt_id"],
        verification_session_id=row["verification_session_id"],
        match_id=row["match_id"],
        claimant_id=row["claimant_id"],
        claimant_email=row["claimant_email"],
        claimant_emergency_contact=row["claimant_emergency_contact"],
        status=row["status"],
        risk_score=row["risk_score"],
        fraud_risk=row["fraud_risk"],
        overall_score=row["overall_score"],
        decision=row["decision"],
        questions=_parse_json(row["questions"]) or [],
        answers=_parse_json(row["answers"]) or [],
        semantic_scores=_parse_json(row["semantic_scores"]),
        vault_features=vault_features,
        public_image_url=public_image_url,
        vault_image_url=vault_image_url,
        found_report_id=UUID(str(found_id)) if found_id else None,
        lost_report_id=(
            UUID(str(row["lost_report_id"])) if row["lost_report_id"] else None
        ),
        found_report_title=row["found_report_title"],
        owner_email=row["owner_email"],
        owner_emergency_contact=row["owner_emergency_contact"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


def decide_review(
    *,
    claim_attempt_id: UUID,
    admin_user_id: UUID,
    decision: str,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Admin overrides REVIEW → PASS (chat) or BLOCK (trust penalty)."""
    decision = decision.upper().strip()
    if decision not in ("PASS", "BLOCK"):
        raise ValueError("decision must be PASS or BLOCK")

    detail = get_review_detail(claim_attempt_id)
    if detail is None:
        raise ValueError(f"Claim attempt {claim_attempt_id} not found")

    if detail.status not in ("review", "started") and detail.decision not in (
        "REVIEW",
        None,
    ):
        if detail.status in ("passed", "blocked"):
            raise ValueError(f"Claim already decided as {detail.status}")

    new_status = "passed" if decision == "PASS" else "blocked"
    fraud_risk = 0.1 if decision == "PASS" else 0.9

    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE claim_attempts
                SET status = :status, fraud_risk = :risk, updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": str(claim_attempt_id), "status": new_status, "risk": fraud_risk},
        )
        if detail.verification_session_id:
            session.execute(
                text(
                    """
                    UPDATE verification_sessions
                    SET decision = :decision,
                        completed_at = COALESCE(completed_at, now())
                    WHERE id = :sid
                    """
                ),
                {
                    "sid": str(detail.verification_session_id),
                    "decision": decision,
                },
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    from pipelines.fraud_pipeline import record_verification_result

    record_verification_result(detail.claimant_id, decision)

    chat_room_id: Optional[str] = None
    if decision == "PASS":
        from services.chat_service import create_chat_room

        try:
            chat_room_id = str(
                create_chat_room(
                    match_id=detail.match_id,
                    claimant_id=detail.claimant_id,
                )
            )
        except Exception as exc:
            logger.warning("admin decide PASS but chat provision failed: {}", exc)

        if chat_room_id:
            from services.claim_service import mark_match_reports_matched

            mark_match_reports_matched(detail.match_id)
            _notify_chat_participants(
                match_id=detail.match_id,
                chat_room_id=UUID(chat_room_id),
                claimant_id=detail.claimant_id,
                report_id=detail.found_report_id,
            )

    _write_audit(
        actor_id=admin_user_id,
        action=f"admin_review_{decision.lower()}",
        entity_type="claim_attempt",
        entity_id=claim_attempt_id,
        meta={
            "note": note or "",
            "previous_status": detail.status,
            "chat_room_id": chat_room_id,
        },
    )

    logger.info(
        "admin_decide claim={} decision={} admin={} chat={}",
        claim_attempt_id,
        decision,
        admin_user_id,
        chat_room_id,
    )
    return {
        "claim_attempt_id": str(claim_attempt_id),
        "decision": decision,
        "status": new_status,
        "chat_room_id": chat_room_id,
    }


def get_user_role(user_id: UUID) -> Optional[str]:
    session = get_session()
    try:
        row = session.execute(
            text("SELECT role FROM users WHERE id = :id OR auth_user_id = :id LIMIT 1"),
            {"id": str(user_id)},
        ).mappings().first()
    finally:
        session.close()
    return row["role"] if row else None


def _notify_chat_participants(
    *,
    match_id: UUID,
    chat_room_id: UUID,
    claimant_id: UUID,
    report_id: Optional[UUID],
) -> None:
    """Tell both room members chat is open after admin PASS."""
    from services.chat_service import get_room
    from services.notification_service import notify_chat_ready

    room = get_room(chat_room_id)
    recipients: list[UUID] = []
    if room is not None:
        recipients = [UUID(str(room.owner_id)), UUID(str(room.finder_id))]
    else:
        recipients = [claimant_id]

    seen: set[str] = set()
    for uid in recipients:
        key = str(uid)
        if key in seen:
            continue
        seen.add(key)
        notify_chat_ready(
            user_id=uid,
            match_id=match_id,
            chat_room_id=chat_room_id,
            report_id=report_id,
        )


def _resolve_images(
    found_report_id: Any,
    session_vault_features: Any,
) -> tuple[Optional[str], Optional[str], Optional[dict[str, Any]]]:
    if not found_report_id:
        return None, None, _parse_json(session_vault_features)

    session = get_session()
    try:
        img = session.execute(
            text(
                """
                SELECT ri.public_path, iv.vault_path, iv.hidden_features
                FROM report_images ri
                LEFT JOIN image_vaults iv ON iv.report_image_id = ri.id
                WHERE ri.report_id = :rid
                ORDER BY ri.is_primary DESC, ri.created_at ASC
                LIMIT 1
                """
            ),
            {"rid": str(found_report_id)},
        ).mappings().first()
    finally:
        session.close()

    if img is None:
        return None, None, _parse_json(session_vault_features)

    pub = public_url(img["public_path"]) if img.get("public_path") else None
    vault = signed_vault_url(img["vault_path"]) if img.get("vault_path") else None
    features = _parse_json(img.get("hidden_features")) or _parse_json(
        session_vault_features
    )
    return pub, vault, features


def _write_audit(
    *,
    actor_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    meta: dict[str, Any],
) -> None:
    session = get_session()
    try:
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
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("audit_logs write failed: {}", exc)
    finally:
        session.close()


def _parse_json(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return None
    return v
