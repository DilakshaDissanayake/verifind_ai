"""Claim service — Sprint 5.

Orchestrates the full verification flow:
  1. Fraud gate check (velocity + lockout)
  2. Create claim_attempt row
  3. Generate adversarial questions from vault
  4. Create verification_session with questions
  5. Accept answers → score → PASS/REVIEW/BLOCK
  6. Update trust_scores
  7. Provision chat room on PASS
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text

from infrastructure.config import FRAUD
from infrastructure.db.sql_client import get_session
from pipelines.fraud_pipeline import (
    check_fraud_gate,
    record_claim_attempt,
    record_verification_result,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClaimAttemptRecord:
    id: UUID
    match_id: UUID
    claimant_id: UUID
    status: str
    risk_score: Optional[float]
    fraud_risk: Optional[float]
    created_at: Optional[datetime]


@dataclass
class VerificationSessionRecord:
    id: UUID
    claim_attempt_id: UUID
    questions: list[dict]
    answers: list[str]
    semantic_scores: Optional[list[float]]
    overall_score: Optional[float]
    decision: Optional[str]
    created_at: Optional[datetime]
    completed_at: Optional[datetime]


# ---------------------------------------------------------------------------
# Start a claim
# ---------------------------------------------------------------------------

async def start_claim(
    *,
    match_id: UUID,
    claimant_user_id: UUID,
    found_report_id: UUID,
) -> dict[str, Any]:
    """Fraud gate → create claim_attempt → generate questions → verification_session.

    Returns:
        {
          claim_attempt_id, verification_session_id,
          questions: [{question_id, question}],  ← no expected_hint
          allowed: bool, reason: str,
        }
    """
    # --- Fraud gate ---
    gate = check_fraud_gate(claimant_user_id)
    if not gate["allowed"]:
        return {
            "allowed": False,
            "reason": gate["reason"],
            "claim_attempt_id": None,
            "verification_session_id": None,
            "questions": [],
        }

    closed_reason = _closed_match_reason(match_id)
    if closed_reason:
        return {
            "allowed": False,
            "reason": closed_reason,
            "claim_attempt_id": None,
            "verification_session_id": None,
            "questions": [],
        }

    # --- Already decided? Don't allow re-claim ---
    existing = _latest_claim_for_match(match_id)
    if existing is not None:
        status = (existing.get("status") or "").lower()
        decision = (existing.get("decision") or "").upper()
        if status == "passed" or decision == "PASS":
            return {
                "allowed": False,
                "reason": "Already verified (PASS). Open chat from Matches or Chats.",
                "claim_attempt_id": str(existing["id"]) if existing.get("id") else None,
                "verification_session_id": None,
                "questions": [],
                "chat_room_id": (
                    str(existing["chat_room_id"]) if existing.get("chat_room_id") else None
                ),
            }
        if status == "review" or decision == "REVIEW":
            return {
                "allowed": False,
                "reason": "Claim is under admin review.",
                "claim_attempt_id": str(existing["id"]) if existing.get("id") else None,
                "verification_session_id": None,
                "questions": [],
            }
        if status == "blocked" or decision == "BLOCK":
            return {
                "allowed": False,
                "reason": "This claim was blocked.",
                "claim_attempt_id": str(existing["id"]) if existing.get("id") else None,
                "verification_session_id": None,
                "questions": [],
            }

    # --- Fetch vault features for the FOUND report ---
    from pipelines.verification_pipeline import (
        fetch_vault_features,
        generate_adversarial_questions,
    )

    vault_features = await fetch_vault_features(str(found_report_id))
    category = _get_report_category(found_report_id)

    # --- Create claim_attempt ---
    attempt_id = _create_claim_attempt(
        match_id=match_id,
        claimant_id=claimant_user_id,
        risk_score=gate["risk_score"],
    )
    record_claim_attempt(claimant_user_id)

    # --- Generate questions ---
    questions = await generate_adversarial_questions(
        hidden_features=vault_features,
        category=category,
        report_id=str(found_report_id),
    )

    # --- Store verification_session (questions only; answers empty) ---
    session_id = _create_verification_session(
        claim_attempt_id=attempt_id,
        questions=questions,
        vault_features=vault_features,
    )

    # Strip expected_hint from client response — NEVER leak
    safe_questions: list[dict[str, str]] = []
    for i, q in enumerate(questions):
        if isinstance(q, dict):
            safe_questions.append(
                {
                    "question_id": str(q.get("question_id") or f"q{i+1}"),
                    "question": str(q.get("question") or ""),
                }
            )
        elif isinstance(q, str) and len(q.strip()) > 8:
            safe_questions.append(
                {"question_id": f"q{i+1}", "question": q.strip()}
            )
    if not safe_questions:
        from pipelines.verification_pipeline import _stub_questions

        safe_questions = [
            {"question_id": s["question_id"], "question": s["question"]}
            for s in _stub_questions(3)
        ]

    logger.info(
        "start_claim: match_id={} claimant={} attempt_id={} session_id={}",
        match_id,
        claimant_user_id,
        attempt_id,
        session_id,
    )
    return {
        "allowed": True,
        "reason": "OK",
        "claim_attempt_id": str(attempt_id),
        "verification_session_id": str(session_id),
        "questions": safe_questions,
    }


# ---------------------------------------------------------------------------
# Submit answers
# ---------------------------------------------------------------------------

async def submit_answers(
    *,
    verification_session_id: UUID,
    claim_attempt_id: UUID,
    answers: list[str],
    claimant_user_id: UUID,
) -> dict[str, Any]:
    """Score answers → PASS/REVIEW/BLOCK → update DB → maybe provision chat.

    Returns:
        {
          decision, overall_score, semantic_scores,
          chat_room_id (if PASS),
          claim_attempt_id, verification_session_id,
        }
    """
    from pipelines.verification_pipeline import score_answers

    session_rec = _get_verification_session(verification_session_id)
    if session_rec is None:
        raise ValueError(f"Verification session {verification_session_id} not found")

    if session_rec.completed_at is not None:
        raise ValueError("Verification session already completed")

    questions = session_rec.questions

    result = await score_answers(
        questions=questions,
        answers=answers,
        report_id=str(verification_session_id),
    )

    decision = result["decision"]
    overall_score = result["overall_score"]
    semantic_scores = result["semantic_scores"]

    # --- Persist to DB ---
    _complete_verification_session(
        session_id=verification_session_id,
        answers=answers,
        semantic_scores=semantic_scores,
        overall_score=overall_score,
        decision=decision,
    )

    _update_claim_attempt_status(
        attempt_id=claim_attempt_id,
        status=_decision_to_status(decision),
        fraud_risk=_overall_to_fraud_risk(overall_score),
    )

    # --- Update trust_scores ---
    record_verification_result(claimant_user_id, decision)

    # --- Provision chat room on PASS ---
    chat_room_id: Optional[str] = None
    match_id = _get_match_id_for_attempt(claim_attempt_id)
    if decision == "PASS":
        if match_id:
            chat_room_id = _provision_chat_room(match_id, claimant_user_id)
            if chat_room_id:
                mark_match_reports_matched(match_id)
                _notify_pass_chat(
                    match_id=match_id,
                    chat_room_id=UUID(chat_room_id),
                    claimant_id=claimant_user_id,
                )

    logger.info(
        "submit_answers: session={} decision={} overall={:.3f} chat_room={}",
        verification_session_id,
        decision,
        overall_score,
        chat_room_id,
    )
    return {
        "decision": decision,
        "overall_score": overall_score,
        "semantic_scores": semantic_scores,
        "chat_room_id": chat_room_id,
        "match_id": str(match_id) if match_id else None,
        "claim_attempt_id": str(claim_attempt_id),
        "verification_session_id": str(verification_session_id),
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _create_claim_attempt(
    *,
    match_id: UUID,
    claimant_id: UUID,
    risk_score: float,
) -> UUID:
    attempt_id = uuid4()
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO claim_attempts
                    (id, match_id, claimant_id, status, risk_score)
                VALUES (:id, :mid, :cid, 'started', :risk)
                """
            ),
            {
                "id": str(attempt_id),
                "mid": str(match_id),
                "cid": str(claimant_id),
                "risk": risk_score,
            },
        )
        session.commit()
        return attempt_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _create_verification_session(
    *,
    claim_attempt_id: UUID,
    questions: list[dict],
    vault_features: dict,
) -> UUID:
    session_id = uuid4()
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO verification_sessions
                    (id, claim_attempt_id, questions, answers, vault_features)
                VALUES (:id, :aid, CAST(:qs AS jsonb), '[]'::jsonb, CAST(:vf AS jsonb))
                """
            ),
            {
                "id": str(session_id),
                "aid": str(claim_attempt_id),
                "qs": json.dumps(questions),
                "vf": json.dumps(vault_features),
            },
        )
        session.commit()
        return session_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_verification_session(session_id: UUID) -> Optional[VerificationSessionRecord]:
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT id, claim_attempt_id, questions, answers,
                       semantic_scores, overall_score, decision,
                       created_at, completed_at
                FROM verification_sessions WHERE id = :id
                """
            ),
            {"id": str(session_id)},
        ).mappings().first()
    finally:
        session.close()

    if row is None:
        return None

    def _parse_json(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return json.loads(v)
        return v

    return VerificationSessionRecord(
        id=row["id"],
        claim_attempt_id=row["claim_attempt_id"],
        questions=_parse_json(row["questions"]) or [],
        answers=_parse_json(row["answers"]) or [],
        semantic_scores=_parse_json(row["semantic_scores"]),
        overall_score=row["overall_score"],
        decision=row["decision"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


def _complete_verification_session(
    *,
    session_id: UUID,
    answers: list[str],
    semantic_scores: list[float],
    overall_score: float,
    decision: str,
) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE verification_sessions
                SET answers = CAST(:ans AS jsonb),
                    semantic_scores = CAST(:scores AS jsonb),
                    overall_score = :score,
                    decision = :decision,
                    completed_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": str(session_id),
                "ans": json.dumps(answers),
                "scores": json.dumps(semantic_scores),
                "score": overall_score,
                "decision": decision,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _update_claim_attempt_status(
    *, attempt_id: UUID, status: str, fraud_risk: float
) -> None:
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
            {"id": str(attempt_id), "status": status, "risk": fraud_risk},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_match_id_for_attempt(attempt_id: UUID) -> Optional[UUID]:
    session = get_session()
    try:
        row = session.execute(
            text("SELECT match_id FROM claim_attempts WHERE id = :id"),
            {"id": str(attempt_id)},
        ).mappings().first()
    finally:
        session.close()
    if row is None:
        return None
    return UUID(str(row["match_id"]))


def _provision_chat_room(match_id: UUID, claimant_id: UUID) -> Optional[str]:
    """Create chat_room if not exists; return room id."""
    from services.chat_service import create_chat_room

    try:
        room_id = create_chat_room(match_id=match_id, claimant_id=claimant_id)
        return str(room_id)
    except Exception as exc:
        logger.warning("_provision_chat_room failed: {}", exc)
        return None


def _latest_claim_for_match(match_id: UUID) -> Optional[dict]:
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT ca.id, ca.status, vs.decision, cr.id AS chat_room_id
                FROM claim_attempts ca
                LEFT JOIN verification_sessions vs ON vs.claim_attempt_id = ca.id
                LEFT JOIN chat_rooms cr ON cr.match_id = ca.match_id AND cr.is_active = true
                WHERE ca.match_id = :mid
                ORDER BY
                  CASE ca.status
                    WHEN 'passed' THEN 0
                    WHEN 'review' THEN 1
                    WHEN 'started' THEN 2
                    WHEN 'blocked' THEN 3
                    ELSE 4
                  END,
                  ca.created_at DESC
                LIMIT 1
                """
            ),
            {"mid": str(match_id)},
        ).mappings().first()
    finally:
        session.close()
    return dict(row) if row else None


def mark_match_reports_matched(match_id: UUID) -> None:
    """Set both reports on a match to status=matched after PASS (hidden from public)."""
    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE reports
                SET status = 'matched', updated_at = now()
                WHERE id IN (
                    SELECT report_a_id FROM matches WHERE id = :mid
                    UNION
                    SELECT report_b_id FROM matches WHERE id = :mid
                )
                """
            ),
            {"mid": str(match_id)},
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("mark_match_reports_matched failed: {}", exc)
    finally:
        session.close()


def mark_match_reports_closed(match_id: UUID) -> None:
    """Hide posts after successful handover — status=closed (admin export still sees them)."""
    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE reports
                SET status = 'closed', updated_at = now()
                WHERE id IN (
                    SELECT report_a_id FROM matches WHERE id = :mid
                    UNION
                    SELECT report_b_id FROM matches WHERE id = :mid
                )
                """
            ),
            {"mid": str(match_id)},
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("mark_match_reports_closed failed: {}", exc)
        raise
    finally:
        session.close()


def _notify_pass_chat(
    *,
    match_id: UUID,
    chat_room_id: UUID,
    claimant_id: UUID,
) -> None:
    from services.chat_service import get_room
    from services.notification_service import notify_chat_ready

    room = get_room(chat_room_id)
    recipients = (
        [UUID(str(room.owner_id)), UUID(str(room.finder_id))]
        if room is not None
        else [claimant_id]
    )
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
        )


def _closed_match_reason(match_id: UUID) -> Optional[str]:
    """Block new claims when either listing was closed (self-find / handover / withdraw)."""
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT r.status
                FROM matches m
                JOIN reports r ON r.id IN (m.report_a_id, m.report_b_id)
                WHERE m.id = :mid
                """
            ),
            {"mid": str(match_id)},
        ).mappings().all()
    finally:
        session.close()
    statuses = {(row["status"] or "").lower() for row in rows}
    if "closed" in statuses:
        return "This listing is closed (found or taken down) and cannot be claimed."
    if "flagged" in statuses:
        return "This listing is under review and cannot be claimed."
    return None


def _get_report_category(report_id: UUID) -> Optional[str]:
    session = get_session()
    try:
        row = session.execute(
            text("SELECT category FROM reports WHERE id = :id"),
            {"id": str(report_id)},
        ).mappings().first()
    finally:
        session.close()
    return row["category"] if row else None


def _decision_to_status(decision: str) -> str:
    return {"PASS": "passed", "REVIEW": "review", "BLOCK": "blocked"}.get(decision, "failed")


def _overall_to_fraud_risk(overall_score: float) -> float:
    # Invert: high answer score → low fraud risk
    return round(max(0.0, min(1.0, 1.0 - overall_score)), 4)


def get_claim_status(claim_attempt_id: UUID) -> Optional[dict]:
    """Return claim attempt row + chat_room_id when provisioned (after PASS)."""
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT ca.id, ca.match_id, ca.claimant_id, ca.status,
                       ca.risk_score, ca.fraud_risk, ca.created_at,
                       vs.decision,
                       cr.id AS chat_room_id
                FROM claim_attempts ca
                LEFT JOIN verification_sessions vs ON vs.claim_attempt_id = ca.id
                LEFT JOIN chat_rooms cr ON cr.match_id = ca.match_id AND cr.is_active = true
                WHERE ca.id = :id
                """
            ),
            {"id": str(claim_attempt_id)},
        ).mappings().first()
    finally:
        session.close()

    if row is None:
        return None
    return dict(row)
