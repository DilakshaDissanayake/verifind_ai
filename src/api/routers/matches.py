"""Matches + Notifications routers — Sprint 4."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.deps import CurrentUser, get_current_user
from api.schemas import (
    MatchOut,
    MatchesResponse,
    NotificationOut,
    NotificationsResponse,
)

router = APIRouter(tags=["matches"])


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

@router.get("/reports/{report_id}/matches", response_model=MatchesResponse)
async def get_report_matches(
    report_id: UUID,
    min_band: str = Query(default="LOW", pattern="^(HIGH|MEDIUM|LOW)$"),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> MatchesResponse:
    """Return match candidates for a report, ranked by fusion score."""
    _ = user
    try:
        from services.match_service import get_matches_for_report

        records = await asyncio.to_thread(
            get_matches_for_report,
            report_id,
            min_band=min_band,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("get_report_matches failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    items = [
        MatchOut(
            match_id=r.id,
            report_a_id=r.report_a_id,
            report_b_id=r.report_b_id,
            score=r.score,
            band=r.band,  # type: ignore[arg-type]
            vision_score=r.vision_score,
            text_score=r.text_score,
            geo_score=r.geo_score,
            category_score=r.category_score,
            distance_m=r.distance_m,
            notified=r.notified,
            created_at=r.created_at,
            claim_status=r.claim_status,
            verification_decision=r.verification_decision,
            chat_room_id=r.chat_room_id,
        )
        for r in records
    ]
    return MatchesResponse(items=items, count=len(items), report_id=report_id)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

notifications_router = APIRouter(tags=["notifications"])


@notifications_router.get("/notifications", response_model=NotificationsResponse)
async def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> NotificationsResponse:
    """List in-app notifications for the current user."""
    try:
        from services.notification_service import get_user_notifications
        from services.user_service import ensure_app_user

        app_user_id_str = await asyncio.to_thread(
            ensure_app_user, auth_user_id=user.id, email=user.email
        )
        app_user_id = UUID(str(app_user_id_str))

        rows = await asyncio.to_thread(
            get_user_notifications,
            app_user_id,
            unread_only=unread_only,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("list_notifications failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    items = [
        NotificationOut(
            notification_id=r["id"],
            type=r.get("type", "match_found"),
            match_id=r.get("match_id"),
            report_id=r.get("report_id"),
            matched_report_id=r.get("matched_report_id"),
            band=r.get("band"),
            score=float(r["score"]) if r.get("score") is not None else None,
            distance_m=float(r["distance_m"]) if r.get("distance_m") is not None else None,
            chat_room_id=r.get("chat_room_id"),
            is_read=bool(r.get("is_read", False)),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]
    unread = sum(1 for i in items if not i.is_read)
    return NotificationsResponse(items=items, count=len(items), unread_count=unread)


@notifications_router.patch("/notifications/{notification_id}/read", status_code=200)
async def mark_read(
    notification_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Mark a notification as read."""
    try:
        from services.notification_service import mark_notification_read
        from services.user_service import ensure_app_user

        app_user_id_str = await asyncio.to_thread(
            ensure_app_user, auth_user_id=user.id, email=user.email
        )
        app_user_id = UUID(str(app_user_id_str))
        updated = await asyncio.to_thread(
            mark_notification_read, notification_id, app_user_id
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"notification_id": str(notification_id), "is_read": True}
