"""Claims router — Sprint 5.

POST /matches/{match_id}/claim          → start claim, get questions
POST /claims/{session_id}/answer        → submit answers, get decision
GET  /claims/{attempt_id}/status        → poll claim status
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from api.deps import CurrentUser, get_current_user
from api.schemas import (
    AnswerSubmitRequest,
    ClaimStartRequest,
    ClaimStartResponse,
    ClaimStatusOut,
    VerificationQuestion,
    VerificationResultResponse,
)
from services.user_service import ensure_app_user

router = APIRouter(tags=["claims"])


@router.post(
    "/matches/{match_id}/claim",
    response_model=ClaimStartResponse,
    status_code=status.HTTP_200_OK,
)
async def start_claim(
    match_id: UUID,
    body: ClaimStartRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ClaimStartResponse:
    """Fraud gate + generate adversarial questions from vault features."""
    from services.claim_service import start_claim as _start

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    claimant_id = UUID(str(app_user_id))

    try:
        result = await _start(
            match_id=match_id,
            claimant_user_id=claimant_id,
            found_report_id=body.found_report_id,
        )
    except Exception as exc:
        logger.exception("start_claim failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not result["allowed"]:
        return ClaimStartResponse(
            allowed=False,
            reason=result["reason"],
        )

    questions = [
        VerificationQuestion(
            question_id=q["question_id"],
            question=q["question"],
        )
        for q in result.get("questions", [])
    ]
    return ClaimStartResponse(
        allowed=True,
        reason="OK",
        claim_attempt_id=UUID(result["claim_attempt_id"]),
        verification_session_id=UUID(result["verification_session_id"]),
        questions=questions,
    )


@router.post(
    "/claims/{verification_session_id}/answer",
    response_model=VerificationResultResponse,
)
async def submit_answers(
    verification_session_id: UUID,
    body: AnswerSubmitRequest,
    user: CurrentUser = Depends(get_current_user),
) -> VerificationResultResponse:
    """Submit answers → score → PASS/REVIEW/BLOCK decision."""
    from services.claim_service import submit_answers as _submit

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    claimant_id = UUID(str(app_user_id))

    try:
        result = await _submit(
            verification_session_id=verification_session_id,
            claim_attempt_id=body.claim_attempt_id,
            answers=body.answers,
            claimant_user_id=claimant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("submit_answers failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    decision = result["decision"]
    message = {
        "PASS": "Ownership verified — chat room is now open.",
        "REVIEW": "Partial verification — your claim is under admin review.",
        "BLOCK": "Verification failed. Please contact support if this is an error.",
    }.get(decision, "")

    return VerificationResultResponse(
        decision=decision,  # type: ignore[arg-type]
        overall_score=result["overall_score"],
        semantic_scores=result.get("semantic_scores", []),
        chat_room_id=UUID(result["chat_room_id"]) if result.get("chat_room_id") else None,
        claim_attempt_id=UUID(result["claim_attempt_id"]),
        verification_session_id=UUID(result["verification_session_id"]),
        message=message,
    )


@router.get("/claims/{attempt_id}/status", response_model=ClaimStatusOut)
async def get_claim_status(
    attempt_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> ClaimStatusOut:
    """Poll the status of a claim attempt."""
    _ = user
    from services.claim_service import get_claim_status

    try:
        rec = await asyncio.to_thread(get_claim_status, attempt_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if rec is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    chat_room_id = rec.get("chat_room_id")
    return ClaimStatusOut(
        claim_attempt_id=rec["id"],
        match_id=rec["match_id"],
        status=rec["status"],
        decision=rec.get("decision"),
        risk_score=rec.get("risk_score"),
        fraud_risk=rec.get("fraud_risk"),
        chat_room_id=UUID(str(chat_room_id)) if chat_room_id else None,
        created_at=rec.get("created_at"),
    )
