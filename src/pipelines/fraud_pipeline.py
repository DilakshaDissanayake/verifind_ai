"""Fraud pipeline — Sprint 5 (Zero-Fraud L4 Behavioral).

Checks:
  1. Velocity: ≤3 claim attempts in 24h (from trust_scores.claim_count_24h)
  2. Fail cooldown: ≥3 fails → 24h lockout (trust_scores.lockout_until)
  3. Trust score decay: each BLOCK lowers trust (floor 0.0)
  4. Composite risk score → PASS / REVIEW / BLOCK gate

All thresholds from config/param.yaml via FRAUD dict.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import text

from infrastructure.config import FRAUD
from infrastructure.db.sql_client import get_session


def check_fraud_gate(user_id: UUID) -> dict[str, Any]:
    """Return fraud gate decision for a claimant before allowing a claim attempt.

    Returns:
        {
          allowed: bool,
          reason: str,
          risk_score: float,
          claim_count_24h: int,
          fail_count: int,
          locked_until: datetime | None,
        }
    """
    trust = _get_or_create_trust(user_id)

    velocity_max = int(FRAUD.get("claim_velocity_max", 3))
    velocity_window_h = int(FRAUD.get("claim_velocity_window_h", 24))
    fail_max = int(FRAUD.get("fail_lockout_count", 3))

    # Check hard lockout first
    lockout = trust.get("lockout_until")
    if lockout and lockout > datetime.now(tz=timezone.utc):
        logger.warning("fraud_gate: user={} is locked out until {}", user_id, lockout)
        return {
            "allowed": False,
            "reason": f"Account locked until {lockout.isoformat()}",
            "risk_score": 1.0,
            "claim_count_24h": trust["claim_count_24h"],
            "fail_count": trust["fail_count"],
            "locked_until": lockout,
        }

    # Check velocity
    count_24h = int(trust.get("claim_count_24h") or 0)
    if count_24h >= velocity_max:
        logger.warning("fraud_gate: user={} velocity exceeded {}/{}", user_id, count_24h, velocity_max)
        return {
            "allowed": False,
            "reason": f"Too many claim attempts in {velocity_window_h}h ({count_24h}/{velocity_max})",
            "risk_score": 0.8,
            "claim_count_24h": count_24h,
            "fail_count": trust["fail_count"],
            "locked_until": None,
        }

    # Compute composite risk score
    base_trust = float(trust.get("score") or 1.0)
    fail_count = int(trust.get("fail_count") or 0)
    velocity_ratio = count_24h / max(velocity_max, 1)
    fail_ratio = min(fail_count / max(fail_max, 1), 1.0)

    risk_score = round(
        (1 - base_trust) * 0.5 + velocity_ratio * 0.25 + fail_ratio * 0.25,
        4,
    )
    risk_score = max(0.0, min(1.0, risk_score))

    return {
        "allowed": True,
        "reason": "OK",
        "risk_score": risk_score,
        "claim_count_24h": count_24h,
        "fail_count": fail_count,
        "locked_until": None,
    }


def record_claim_attempt(user_id: UUID) -> None:
    """Increment claim_count_24h in trust_scores."""
    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE trust_scores
                SET claim_count_24h = claim_count_24h + 1,
                    updated_at = now()
                WHERE user_id = :uid
                """
            ),
            {"uid": str(user_id)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def record_verification_result(user_id: UUID, decision: str) -> None:
    """Update trust_scores after a claim verification completes.

    PASS  → reset fail_count; mild trust bump
    REVIEW → no change
    BLOCK  → increment fail_count; maybe apply lockout; decay trust
    """
    fail_max = int(FRAUD.get("fail_lockout_count", 3))
    lockout_h = int(FRAUD.get("fail_lockout_h", 24))

    session = get_session()
    try:
        if decision == "PASS":
            session.execute(
                text(
                    """
                    UPDATE trust_scores
                    SET fail_count = GREATEST(fail_count - 1, 0),
                        score = LEAST(score + 0.05, 1.0),
                        updated_at = now()
                    WHERE user_id = :uid
                    """
                ),
                {"uid": str(user_id)},
            )
        elif decision == "BLOCK":
            session.execute(
                text(
                    f"""
                    UPDATE trust_scores
                    SET fail_count = fail_count + 1,
                        score = GREATEST(score - 0.15, 0.0),
                        lockout_until = CASE
                            WHEN fail_count + 1 >= {fail_max}
                            THEN now() + interval '{lockout_h} hours'
                            ELSE lockout_until
                        END,
                        updated_at = now()
                    WHERE user_id = :uid
                    """
                ),
                {"uid": str(user_id)},
            )
        session.commit()
        logger.info(
            "record_verification_result user={} decision={}", user_id, decision
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_or_create_trust(user_id: UUID) -> dict[str, Any]:
    """Fetch trust_scores row; create default if missing."""
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT score, claim_count_24h, fail_count, lockout_until
                FROM trust_scores WHERE user_id = :uid
                """
            ),
            {"uid": str(user_id)},
        ).mappings().first()

        if row is None:
            session.execute(
                text(
                    """
                    INSERT INTO trust_scores (user_id, score, claim_count_24h, fail_count)
                    VALUES (:uid, 1.0, 0, 0)
                    ON CONFLICT (user_id) DO NOTHING
                    """
                ),
                {"uid": str(user_id)},
            )
            session.commit()
            return {"score": 1.0, "claim_count_24h": 0, "fail_count": 0, "lockout_until": None}

        return dict(row)
    finally:
        session.close()
