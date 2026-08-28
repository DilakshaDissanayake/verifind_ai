"""Admin REVIEW + moderation router — Sprint 6/9.

GET  /admin/reviews                     → fraud REVIEW queue
GET  /admin/reviews/{id}                → vault vs public + contacts
POST /admin/reviews/{id}/decide         → PASS | BLOCK
POST /admin/suggestions/{id}/decide     → PASS | REJECT match
POST /admin/users/{id}/block|unblock
POST /admin/users/{id}/reveal-contact
GET  /admin/moderation                  → content strikes / blocks
POST /admin/reports/{id}/resolve        → approve | quarantine | remove
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import bindparam, text

from api.deps import CurrentUser, require_admin
from api.schemas import (
    AdminAuditLogListResponse,
    AdminAuditLogOut,
    AdminContactRevealRequest,
    AdminContactRevealResponse,
    AdminDecideRequest,
    AdminDecideResponse,
    AdminMatchDecideRequest,
    AdminMatchDecideResponse,
    AdminModerationEventOut,
    AdminModerationListResponse,
    AdminOverviewOut,
    AdminReportListResponse,
    AdminReportOut,
    AdminReportResolveRequest,
    AdminReportResolveResponse,
    AdminReviewDetailOut,
    AdminReviewItemOut,
    AdminReviewListResponse,
    AdminSuggestionListResponse,
    AdminSuggestionOut,
    AdminUserBlockRequest,
    AdminUserBlockResponse,
    AdminUserListResponse,
    AdminUserOut,
)
from infrastructure.db.sql_client import get_session
from services.user_service import ensure_app_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewOut)
async def overview(user: CurrentUser = Depends(require_admin)) -> AdminOverviewOut:
    _ = user
    try:
        data = await asyncio.to_thread(_overview)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminOverviewOut(**data)


@router.get("/reports", response_model=AdminReportListResponse)
async def reports(
    search: str | None = Query(default=None, max_length=100),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    report_type: str | None = Query(default=None, pattern="^(LOST|FOUND)$"),
    category: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_admin),
) -> AdminReportListResponse:
    _ = user
    try:
        rows = await asyncio.to_thread(
            _list_admin_reports,
            search,
            status_filter,
            report_type,
            category,
            limit,
            offset,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    url_map: dict = {}
    try:
        from services.image_service import public_urls_for_reports

        ids = [row["report_id"] for row in rows if row.get("report_id")]
        if ids:
            url_map = await asyncio.to_thread(public_urls_for_reports, ids)
    except Exception as exc:
        logger.warning("admin report public images failed: {}", exc)

    items = []
    for row in rows:
        rid = row["report_id"]
        payload = dict(row)
        payload["public_image_urls"] = url_map.get(rid, [])
        items.append(AdminReportOut(**payload))
    return AdminReportListResponse(items=items, count=len(items))


@router.get("/export")
async def export_reports(
    kind: str = Query(
        default="all",
        pattern="^(lost|found|handovers|all)$",
        description="lost | found | handovers | all",
    ),
    ids: str | None = Query(
        default=None,
        max_length=12000,
        description="Comma-separated report UUIDs. Omit to export the full set.",
    ),
    user: CurrentUser = Depends(require_admin),
) -> StreamingResponse:
    """CSV export — lost items, found items, or successful handover report.

    If ``ids`` is set, only those reports (or handovers involving them) are exported.
    If ``ids`` is omitted, the full matching set is exported.
    """
    _ = user
    id_list = _parse_export_ids(ids)
    try:
        csv_text, filename = await asyncio.to_thread(_build_export_csv, kind, id_list)
    except Exception as exc:
        logger.exception("admin export failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/users", response_model=AdminUserListResponse)
async def users(
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_admin),
) -> AdminUserListResponse:
    _ = user
    try:
        rows = await asyncio.to_thread(_list_admin_users, search, limit, offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminUserListResponse(items=[AdminUserOut(**row) for row in rows], count=len(rows))


@router.get("/suggestions", response_model=AdminSuggestionListResponse)
async def suggestions(
    band: str | None = Query(default=None, pattern="^(HIGH|MEDIUM|LOW)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_admin),
) -> AdminSuggestionListResponse:
    _ = user
    try:
        rows = await asyncio.to_thread(_list_suggestions, band, limit, offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminSuggestionListResponse(items=[AdminSuggestionOut(**row) for row in rows], count=len(rows))


@router.get("/audit-logs", response_model=AdminAuditLogListResponse)
async def audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_admin),
) -> AdminAuditLogListResponse:
    _ = user
    try:
        rows = await asyncio.to_thread(_list_audit_logs, limit, offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminAuditLogListResponse(items=[AdminAuditLogOut(**row) for row in rows], count=len(rows))


@router.get("/reviews", response_model=AdminReviewListResponse)
async def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_admin),
) -> AdminReviewListResponse:
    """List claim attempts in REVIEW status."""
    _ = user
    from services.admin_service import list_review_queue

    try:
        items = await asyncio.to_thread(list_review_queue, limit=limit, offset=offset)
    except Exception as exc:
        logger.exception("list_reviews failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AdminReviewListResponse(
        items=[
            AdminReviewItemOut(
                claim_attempt_id=i.claim_attempt_id,
                verification_session_id=i.verification_session_id,
                match_id=i.match_id,
                claimant_id=i.claimant_id,
                claimant_email=i.claimant_email,
                status=i.status,
                risk_score=i.risk_score,
                fraud_risk=i.fraud_risk,
                overall_score=i.overall_score,
                decision=i.decision,
                found_report_title=i.found_report_title,
                created_at=i.created_at,
            )
            for i in items
        ],
        count=len(items),
    )


@router.get("/reviews/{claim_attempt_id}", response_model=AdminReviewDetailOut)
async def get_review(
    claim_attempt_id: UUID,
    user: CurrentUser = Depends(require_admin),
) -> AdminReviewDetailOut:
    """Side-by-side vault (signed) vs public — admin only."""
    _ = user
    from services.admin_service import get_review_detail

    try:
        detail = await asyncio.to_thread(get_review_detail, claim_attempt_id)
    except Exception as exc:
        logger.exception("get_review failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if detail is None:
        raise HTTPException(status_code=404, detail="Review item not found")

    return AdminReviewDetailOut(
        claim_attempt_id=detail.claim_attempt_id,
        verification_session_id=detail.verification_session_id,
        match_id=detail.match_id,
        claimant_id=detail.claimant_id,
        claimant_email=detail.claimant_email,
        claimant_emergency_contact=detail.claimant_emergency_contact,
        status=detail.status,
        risk_score=detail.risk_score,
        fraud_risk=detail.fraud_risk,
        overall_score=detail.overall_score,
        decision=detail.decision,
        questions=detail.questions,
        answers=detail.answers,
        semantic_scores=detail.semantic_scores or [],
        vault_features=detail.vault_features,
        public_image_url=detail.public_image_url,
        vault_image_url=detail.vault_image_url,
        found_report_id=detail.found_report_id,
        lost_report_id=detail.lost_report_id,
        found_report_title=detail.found_report_title,
        owner_email=detail.owner_email,
        owner_emergency_contact=detail.owner_emergency_contact,
        created_at=detail.created_at,
        completed_at=detail.completed_at,
    )


@router.post(
    "/reviews/{claim_attempt_id}/decide",
    response_model=AdminDecideResponse,
)
async def decide_review(
    claim_attempt_id: UUID,
    body: AdminDecideRequest,
    user: CurrentUser = Depends(require_admin),
) -> AdminDecideResponse:
    """Admin PASS → chat; BLOCK → trust penalty + audit."""
    from services.admin_service import decide_review as _decide

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )

    try:
        result = await asyncio.to_thread(
            _decide,
            claim_attempt_id=claim_attempt_id,
            admin_user_id=UUID(str(app_user_id)),
            decision=body.decision,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("decide_review failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AdminDecideResponse(
        claim_attempt_id=UUID(result["claim_attempt_id"]),
        decision=result["decision"],  # type: ignore[arg-type]
        status=result["status"],
        chat_room_id=(
            UUID(result["chat_room_id"]) if result.get("chat_room_id") else None
        ),
        message=(
            "Ownership approved — chat room provisioned."
            if result["decision"] == "PASS"
            else "Claim blocked — trust score penalized."
        ),
    )


@router.post(
    "/suggestions/{match_id}/decide",
    response_model=AdminMatchDecideResponse,
)
async def decide_suggestion(
    match_id: UUID,
    body: AdminMatchDecideRequest,
    user: CurrentUser = Depends(require_admin),
) -> AdminMatchDecideResponse:
    """Admin PASS → approve match for users; REJECT → hide false positive."""
    from services.moderation_service import decide_match

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    try:
        row = await asyncio.to_thread(
            decide_match,
            match_id=match_id,
            admin_user_id=UUID(str(app_user_id)),
            decision=body.decision,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("decide_suggestion failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    approved = body.decision == "PASS"
    return AdminMatchDecideResponse(
        match_id=match_id,
        admin_status=str(row["admin_status"]),
        decision=body.decision,
        message=(
            "Match approved — users can proceed."
            if approved
            else "Match rejected — hidden from user feeds."
        ),
    )


@router.post("/users/{user_id}/block", response_model=AdminUserBlockResponse)
async def block_user(
    user_id: UUID,
    body: AdminUserBlockRequest,
    user: CurrentUser = Depends(require_admin),
) -> AdminUserBlockResponse:
    from services.moderation_service import set_user_active

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    try:
        await asyncio.to_thread(
            set_user_active,
            user_id=user_id,
            admin_user_id=UUID(str(app_user_id)),
            active=False,
            reason=body.reason or "admin_block",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminUserBlockResponse(
        user_id=user_id, is_active=False, message="User blocked."
    )


@router.post("/users/{user_id}/unblock", response_model=AdminUserBlockResponse)
async def unblock_user(
    user_id: UUID,
    body: AdminUserBlockRequest,
    user: CurrentUser = Depends(require_admin),
) -> AdminUserBlockResponse:
    from services.moderation_service import set_user_active

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    try:
        await asyncio.to_thread(
            set_user_active,
            user_id=user_id,
            admin_user_id=UUID(str(app_user_id)),
            active=True,
            reason=body.reason or "admin_unblock",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminUserBlockResponse(
        user_id=user_id, is_active=True, message="User unblocked."
    )


@router.post(
    "/users/{user_id}/reveal-contact",
    response_model=AdminContactRevealResponse,
)
async def reveal_contact(
    user_id: UUID,
    body: AdminContactRevealRequest,
    user: CurrentUser = Depends(require_admin),
) -> AdminContactRevealResponse:
    """Reveal emergency contact for safety issues — audited."""
    from services.moderation_service import reveal_user_contact

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    try:
        row = await asyncio.to_thread(
            reveal_user_contact,
            user_id=user_id,
            admin_user_id=UUID(str(app_user_id)),
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminContactRevealResponse(
        user_id=user_id,
        email=str(row["email"]),
        display_name=row.get("display_name"),
        emergency_contact=row.get("emergency_contact"),
        is_active=bool(row["is_active"]),
    )


@router.get("/moderation", response_model=AdminModerationListResponse)
async def moderation_queue(
    open_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_admin),
) -> AdminModerationListResponse:
    _ = user
    from services.moderation_service import list_moderation_events

    try:
        items = await asyncio.to_thread(
            list_moderation_events, open_only=open_only, limit=limit, offset=offset
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminModerationListResponse(
        items=[
            AdminModerationEventOut(
                event_id=i.event_id,
                user_id=i.user_id,
                user_email=i.user_email,
                emergency_contact=i.emergency_contact,
                kind=i.kind,
                source=i.source,
                snippet=i.snippet,
                strike_number=i.strike_number,
                report_id=i.report_id,
                match_id=i.match_id,
                resolved=i.resolved,
                meta=i.meta,
                created_at=i.created_at,
            )
            for i in items
        ],
        count=len(items),
    )


@router.post("/moderation/{event_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_moderation_event(
    event_id: UUID,
    user: CurrentUser = Depends(require_admin),
) -> None:
    from services.moderation_service import mark_event_resolved

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    try:
        await asyncio.to_thread(
            mark_event_resolved,
            event_id=event_id,
            admin_user_id=UUID(str(app_user_id)),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/reports/{report_id}/resolve",
    response_model=AdminReportResolveResponse,
)
async def resolve_admin_report(
    report_id: UUID,
    body: AdminReportResolveRequest,
    user: CurrentUser = Depends(require_admin),
) -> AdminReportResolveResponse:
    from services.moderation_service import resolve_report

    app_user_id = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    try:
        row = await asyncio.to_thread(
            resolve_report,
            report_id=report_id,
            admin_user_id=UUID(str(app_user_id)),
            action=body.action,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdminReportResolveResponse(
        report_id=report_id,
        status=str(row["status"]),
        message=f"Report marked {row['status']}.",
    )


def _overview() -> dict[str, int]:
    session = get_session()
    try:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM reports) AS reports,
                      (SELECT count(*) FROM users) AS users,
                      (SELECT count(*) FROM claim_attempts WHERE status = 'review') AS pending_reviews,
                      (SELECT count(*) FROM matches
                         WHERE band IN ('HIGH', 'MEDIUM')
                           AND COALESCE(admin_status, 'pending') = 'pending') AS open_suggestions,
                      (SELECT count(*) FROM reports WHERE status = 'flagged') AS flagged_reports,
                      (SELECT count(*) FROM users WHERE is_active = false) AS blocked_users,
                      (SELECT count(*) FROM matches
                         WHERE COALESCE(admin_status, 'pending') = 'pending'
                           AND band IN ('HIGH', 'MEDIUM')) AS pending_match_approvals,
                      (SELECT count(*) FROM moderation_events WHERE resolved = false) AS open_moderation,
                      (SELECT count(*) FROM claim_attempts WHERE status = 'passed') AS successful_handovers,
                      (SELECT count(*) FROM reports WHERE status = 'closed') AS closed_reports
                    """
                )
            ).mappings().one()
        except Exception:
            session.rollback()
            row = session.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM reports) AS reports,
                      (SELECT count(*) FROM users) AS users,
                      (SELECT count(*) FROM claim_attempts WHERE status = 'review') AS pending_reviews,
                      (SELECT count(*) FROM matches WHERE band IN ('HIGH', 'MEDIUM')) AS open_suggestions,
                      (SELECT count(*) FROM reports WHERE status = 'flagged') AS flagged_reports,
                      (SELECT count(*) FROM users WHERE is_active = false) AS blocked_users
                    """
                )
            ).mappings().one()
            data = {key: int(row[key] or 0) for key in row.keys()}
            data.setdefault("pending_match_approvals", data.get("open_suggestions", 0))
            data.setdefault("open_moderation", 0)
            data.setdefault("successful_handovers", 0)
            data.setdefault("closed_reports", 0)
            return data
        return {key: int(row[key] or 0) for key in row.keys()}
    finally:
        session.close()


def _list_admin_reports(
    search: str | None,
    status_filter: str | None,
    report_type: str | None,
    category: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT r.id AS report_id, r.report_type, r.title, r.category, r.status,
                       r.user_id, u.email AS user_email, u.emergency_contact,
                       r.created_at, r.updated_at, r.description, r.location_label,
                       CASE WHEN r.location IS NULL THEN NULL
                            ELSE ST_Y(r.location::geometry) END AS latitude,
                       CASE WHEN r.location IS NULL THEN NULL
                            ELSE ST_X(r.location::geometry) END AS longitude
                FROM reports r
                LEFT JOIN users u ON u.id = r.user_id
                WHERE (:search IS NULL OR r.title ILIKE :pattern OR r.category ILIKE :pattern
                       OR u.email ILIKE :pattern OR r.description ILIKE :pattern)
                  AND (:status IS NULL OR r.status = :status)
                  AND (:report_type IS NULL OR r.report_type = :report_type)
                  AND (:category IS NULL OR r.category ILIKE :cat_pattern)
                ORDER BY r.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                "search": search,
                "pattern": f"%{search}%" if search else None,
                "status": status_filter,
                "report_type": report_type,
                "category": category,
                "cat_pattern": f"%{category}%" if category else None,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        session.close()


def _list_admin_users(search: str | None, limit: int, offset: int) -> list[dict]:
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                  SELECT u.id AS user_id, u.email, u.display_name, u.emergency_contact,
                      u.role, u.is_active,
                       ts.score AS trust_score, COALESCE(ts.fail_count, 0) AS fail_count,
                       COALESCE(ts.content_strike_count, 0) AS content_strike_count,
                       (SELECT count(*) FROM reports r WHERE r.user_id = u.id) AS reports_count,
                       u.created_at
                FROM users u
                LEFT JOIN trust_scores ts ON ts.user_id = u.id
                WHERE (:search IS NULL OR u.email ILIKE :pattern OR u.display_name ILIKE :pattern)
                ORDER BY u.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"search": search, "pattern": f"%{search}%" if search else None,
             "limit": limit, "offset": offset},
        ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        session.close()


def _list_suggestions(band: str | None, limit: int, offset: int) -> list[dict]:
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT m.id AS match_id, m.report_a_id, m.report_b_id,
                       a.title AS lost_title, b.title AS found_title,
                       m.score, m.band, COALESCE(m.notified, false) AS notified,
                       COALESCE(m.admin_status, 'pending') AS admin_status,
                       m.created_at
                FROM matches m
                LEFT JOIN reports a ON a.id = m.report_a_id
                LEFT JOIN reports b ON b.id = m.report_b_id
                WHERE (:band IS NULL OR m.band = :band)
                ORDER BY
                  CASE COALESCE(m.admin_status, 'pending')
                    WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
                  m.score DESC, m.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"band": band, "limit": limit, "offset": offset},
        ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        session.close()


def _list_audit_logs(limit: int, offset: int) -> list[dict]:
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT id AS audit_id, actor_id, action, entity_type, entity_id, meta, created_at
                FROM audit_logs
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        session.close()


def _parse_export_ids(raw: str | None) -> list[UUID] | None:
    if raw is None or not raw.strip():
        return None
    out: list[UUID] = []
    seen: set[UUID] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            uid = UUID(token)
        except ValueError:
            continue
        if uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
        if len(out) >= 500:
            break
    return out


def _build_export_csv(kind: str, ids: list[UUID] | None = None) -> tuple[str, str]:
    """Build CSV text + filename for admin export."""
    import csv
    import io

    kind = (kind or "all").lower().strip()
    restrict = ids is not None
    id_strs = [str(x) for x in (ids or [])]
    session = get_session()
    try:
        if kind == "handovers":
            ho_sql = """
                    SELECT ca.id AS claim_attempt_id,
                           m.id AS match_id,
                           ra.id AS lost_report_id,
                           ra.title AS lost_title,
                           ra.category AS lost_category,
                           ra.status AS lost_status,
                           ua.email AS lost_owner_email,
                           ua.emergency_contact AS lost_contact,
                           rb.id AS found_report_id,
                           rb.title AS found_title,
                           rb.category AS found_category,
                           rb.status AS found_status,
                           ub.email AS found_owner_email,
                           ub.emergency_contact AS found_contact,
                           ca.status AS claim_status,
                           vs.decision AS verification_decision,
                           cr.id AS chat_room_id,
                           COALESCE(cr.is_active, false) AS chat_active,
                           ca.created_at AS claim_created_at,
                           ra.updated_at AS lost_updated_at,
                           rb.updated_at AS found_updated_at
                    FROM claim_attempts ca
                    JOIN matches m ON m.id = ca.match_id
                    JOIN reports ra ON ra.id = m.report_a_id
                    JOIN reports rb ON rb.id = m.report_b_id
                    LEFT JOIN users ua ON ua.id = ra.user_id
                    LEFT JOIN users ub ON ub.id = rb.user_id
                    LEFT JOIN verification_sessions vs ON vs.claim_attempt_id = ca.id
                    LEFT JOIN chat_rooms cr ON cr.match_id = m.id
                    WHERE (ca.status = 'passed' OR vs.decision = 'PASS')
            """
            if restrict:
                if not id_strs:
                    ho_sql += " AND FALSE"
                    ho_stmt = text(ho_sql + " ORDER BY ca.created_at DESC LIMIT 5000")
                    rows = session.execute(ho_stmt).mappings().all()
                else:
                    ho_sql += " AND (ra.id IN :ids OR rb.id IN :ids)"
                    ho_stmt = text(
                        ho_sql + " ORDER BY ca.created_at DESC LIMIT 5000"
                    ).bindparams(bindparam("ids", expanding=True))
                    rows = session.execute(ho_stmt, {"ids": id_strs}).mappings().all()
            else:
                ho_stmt = text(ho_sql + " ORDER BY ca.created_at DESC LIMIT 5000")
                rows = session.execute(ho_stmt).mappings().all()
            fieldnames = [
                "claim_attempt_id", "match_id",
                "lost_report_id", "lost_title", "lost_category", "lost_status",
                "lost_owner_email", "lost_contact",
                "found_report_id", "found_title", "found_category", "found_status",
                "found_owner_email", "found_contact",
                "claim_status", "verification_decision",
                "chat_room_id", "chat_active",
                "claim_created_at", "lost_updated_at", "found_updated_at",
            ]
            filename = f"verifind_handovers_{_stamp()}.csv"
        else:
            report_type = None
            if kind == "lost":
                report_type = "LOST"
                filename = f"verifind_lost_items_{_stamp()}.csv"
            elif kind == "found":
                report_type = "FOUND"
                filename = f"verifind_found_items_{_stamp()}.csv"
            else:
                filename = f"verifind_all_reports_{_stamp()}.csv"

            rpt_sql = """
                    SELECT r.id AS report_id, r.report_type, r.title, r.category,
                           r.description, r.status, r.location_label,
                           r.user_id, u.email AS user_email,
                           u.emergency_contact, u.display_name,
                           r.created_at, r.updated_at
                    FROM reports r
                    LEFT JOIN users u ON u.id = r.user_id
                    WHERE (:rtype IS NULL OR r.report_type = :rtype)
            """
            params: dict = {"rtype": report_type}
            if restrict:
                if not id_strs:
                    rpt_sql += " AND FALSE"
                    rpt_stmt = text(rpt_sql + " ORDER BY r.created_at DESC LIMIT 10000")
                    rows = session.execute(rpt_stmt, params).mappings().all()
                else:
                    rpt_sql += " AND r.id IN :ids"
                    rpt_stmt = text(
                        rpt_sql + " ORDER BY r.created_at DESC LIMIT 10000"
                    ).bindparams(bindparam("ids", expanding=True))
                    params["ids"] = id_strs
                    rows = session.execute(rpt_stmt, params).mappings().all()
            else:
                rpt_stmt = text(rpt_sql + " ORDER BY r.created_at DESC LIMIT 10000")
                rows = session.execute(rpt_stmt, params).mappings().all()
            fieldnames = [
                "report_id", "report_type", "title", "category", "description",
                "status", "location_label", "user_id", "user_email",
                "emergency_contact", "display_name", "created_at", "updated_at",
            ]
    finally:
        session.close()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_cell(row.get(k)) for k in fieldnames})
    return buf.getvalue(), filename


def _stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value)
