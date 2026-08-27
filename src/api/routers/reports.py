"""Report CRUD + image upload + nearby (Sprint 2)."""

from __future__ import annotations

import asyncio
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from loguru import logger

from api.deps import CurrentUser, get_current_user
from api.schemas import (
    AIStatusResponse,
    AITagsOut,
    NearbyHitOut,
    NearbyResponse,
    ReportCreateRequest,
    ReportCreateResponse,
    ReportImageOut,
    ReportListResponse,
    ReportOut,
    ReportUpdateRequest,
)
from infrastructure.config import GEO_RADIUS_M
from services import image_service, report_service
from services.geo_service import nearby_reports
from workers.enqueue import enqueue_process_report_ai

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_out(rec: report_service.ReportRecord) -> ReportOut:
    return ReportOut(
        report_id=rec.id,
        report_type=rec.report_type,  # type: ignore[arg-type]
        category=rec.category,
        title=rec.title,
        description=rec.description,
        status=rec.status,
        latitude=rec.latitude,
        longitude=rec.longitude,
        location_label=rec.location_label,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.post(
    "",
    response_model=ReportCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@router.post(
    "/",
    response_model=ReportCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
async def create_report(
    body: ReportCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ReportCreateResponse:
    try:
        from services.content_policy import enforce_report_content
        from services.user_service import ensure_app_user

        app_user_id = await asyncio.to_thread(
            ensure_app_user, auth_user_id=user.id, email=user.email
        )
        await asyncio.to_thread(
            enforce_report_content,
            user_id=app_user_id,
            category=body.category,
            title=body.title,
            description=body.description,
        )
        # Finder linked to a LOST post — validate before insert
        if body.matched_to_report_id is not None:
            if body.report_type != "FOUND":
                raise HTTPException(
                    status_code=400,
                    detail="matched_to_report_id is only valid for FOUND reports",
                )
            linked = await asyncio.to_thread(report_service.get_report, body.matched_to_report_id)
            if linked is None:
                raise HTTPException(status_code=404, detail="Linked LOST report not found")
            if linked.report_type != "LOST":
                raise HTTPException(
                    status_code=400,
                    detail="matched_to_report_id must reference a LOST report",
                )

        record = await asyncio.to_thread(
            report_service.create_report,
            auth_user_id=user.id,
            email=user.email,
            report_type=body.report_type,
            category=body.category,
            title=body.title,
            description=body.description,
            latitude=body.latitude,
            longitude=body.longitude,
            location_label=body.location_label,
            # Always server-fuzz unless client already fuzzed (still re-fuzz by default)
            apply_server_fuzz=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("create_report failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc

    logger.info(
        "Report persisted id={} type={} user={}",
        record.id,
        record.report_type,
        user.id,
    )
    enqueued = await enqueue_process_report_ai(
        report_id=str(record.id),
        user_id=user.id,
        report_type=record.report_type,
        category=record.category,
        title=record.title,
        description=record.description,
        latitude=record.latitude,
        longitude=record.longitude,
        matched_to_report_id=(
            str(body.matched_to_report_id) if body.matched_to_report_id else None
        ),
    )
    return ReportCreateResponse(
        report_id=record.id,
        status=record.status,
        message=(
            "Accepted for AI processing (linked to selected LOST report)"
            if body.matched_to_report_id
            else "Accepted for AI processing"
        ),
        job_enqueued=enqueued,
        latitude=record.latitude,
        longitude=record.longitude,
        matched_to_report_id=body.matched_to_report_id,
    )


@router.get("/nearby", response_model=NearbyResponse)
async def reports_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(default=GEO_RADIUS_M, ge=1, le=50_000),
    report_type: Optional[str] = Query(
        default=None, pattern="^(LOST|FOUND)$"
    ),
    exclude_id: Optional[UUID] = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> NearbyResponse:
    try:
        hits = await asyncio.to_thread(
            nearby_reports,
            lat,
            lon,
            radius_m=radius_m,
            report_type=report_type,
            exclude_id=exclude_id,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("nearby query failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Nearby query failed: {exc}",
        ) from exc
    url_map: dict = {}
    if hits:
        try:
            url_map = await asyncio.to_thread(
                image_service.public_urls_for_reports,
                [h.id for h in hits],
            )
        except Exception as exc:
            logger.warning("nearby image urls failed: {}", exc)

    claim_map: dict = {}
    if hits:
        try:
            from services.chat_service import claim_context_for_reports
            from services.user_service import ensure_app_user

            app_uid = UUID(
                str(
                    await asyncio.to_thread(
                        ensure_app_user, auth_user_id=user.id, email=user.email
                    )
                )
            )
            claim_map = await asyncio.to_thread(
                claim_context_for_reports,
                app_uid,
                [h.id for h in hits],
            )
        except Exception as exc:
            logger.warning("nearby claim context failed: {}", exc)

    items = []
    for h in hits:
        ctx = claim_map.get(h.id) or {}
        items.append(
            NearbyHitOut(
                report_id=h.id,
                report_type=h.report_type,  # type: ignore[arg-type]
                category=h.category,
                title=h.title,
                status=h.status,
                latitude=h.latitude,
                longitude=h.longitude,
                distance_m=round(h.distance_m, 2),
                location_label=h.location_label,
                image_urls=url_map.get(h.id, []),
                claim_status=ctx.get("claim_status"),
                verification_decision=ctx.get("verification_decision"),
                chat_room_id=ctx.get("chat_room_id"),
            )
        )
    return NearbyResponse(
        items=items,
        count=len(items),
        radius_m=radius_m,
        query_lat=lat,
        query_lon=lon,
    )


@router.get("", response_model=ReportListResponse)
@router.get("/", response_model=ReportListResponse, include_in_schema=False)
async def list_my_reports(
    report_type: Optional[str] = Query(default=None, pattern="^(LOST|FOUND)$"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> ReportListResponse:
    try:
        rows = await asyncio.to_thread(
            report_service.list_reports_for_user,
            auth_user_id=user.id,
            email=user.email,
            report_type=report_type,
            status_filter=status_filter,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Database unavailable: {exc}"
        ) from exc
    items = [_to_out(r) for r in rows]
    return ReportListResponse(items=items, count=len(items))


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> ReportOut:
    _ = user
    try:
        rec = await asyncio.to_thread(report_service.get_report, report_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if rec is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_out(rec)


@router.get("/{report_id}/ai-status", response_model=AIStatusResponse)
async def get_ai_status(
    report_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> AIStatusResponse:
    """Return AI processing status + tags for a report (Sprint 3)."""
    _ = user
    try:
        rec = await asyncio.to_thread(report_service.get_report, report_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if rec is None:
        raise HTTPException(status_code=404, detail="Report not found")

    # Fetch ai_tags row
    tags_out: Optional[AITagsOut] = None
    has_embedding = False
    try:
        tags_out, has_embedding = await asyncio.to_thread(_fetch_ai_tags, report_id)
    except Exception as exc:
        logger.warning("ai-status: tags fetch failed for {}: {}", report_id, exc)

    return AIStatusResponse(
        report_id=report_id,
        status=rec.status,
        has_embedding=has_embedding,
        tags=tags_out,
    )


@router.patch("/{report_id}", response_model=ReportOut)
async def patch_report(
    report_id: UUID,
    body: ReportUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ReportOut:
    try:
        rec = await asyncio.to_thread(
            report_service.update_report,
            report_id=report_id,
            auth_user_id=user.id,
            email=user.email,
            title=body.title,
            description=body.description,
            category=body.category,
            status_value=body.status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_out(rec)


@router.post(
    "/{report_id}/images",
    response_model=ReportImageOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_image(
    report_id: UUID,
    file: UploadFile = File(...),
    is_primary: bool = Form(default=True),
    user: CurrentUser = Depends(get_current_user),
) -> ReportImageOut:
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    try:
        rec = await asyncio.to_thread(
            image_service.upload_report_image,
            report_id=report_id,
            auth_user_id=user.id,
            email=user.email,
            data=data,
            content_type=content_type,
            filename=file.filename,
            is_primary=is_primary,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("image upload failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Report create enqueues AI before the photo arrives — re-run after primary upload
    if is_primary:
        try:
            report = await asyncio.to_thread(report_service.get_report, report_id)
            if report is not None:
                await enqueue_process_report_ai(
                    report_id=str(report.id),
                    user_id=user.id,
                    report_type=report.report_type,
                    category=report.category,
                    title=report.title,
                    description=report.description,
                    latitude=report.latitude,
                    longitude=report.longitude,
                )
        except Exception as exc:
            logger.warning("re-enqueue after image upload failed: {}", exc)
    else:
        # Extra angles: publish sanitized copy for nearby slider (no mask boxes yet)
        try:
            from pipelines.sanitization_pipeline import run_sanitization_pipeline

            san = await run_sanitization_pipeline(
                data,
                report_id=str(report_id),
                image_id=str(rec.id),
                mask_boxes=[],
                content_type=rec.content_type or "image/jpeg",
            )
            pub = san.get("public_path")
            if pub:
                await asyncio.to_thread(
                    image_service.set_image_public_path, rec.id, pub
                )
                rec.public_path = pub
        except Exception as exc:
            logger.warning("secondary image sanitize failed: {}", exc)

    return ReportImageOut(
        image_id=rec.id,
        report_id=rec.report_id,
        public_path=rec.public_path,
        content_type=rec.content_type,
        is_primary=rec.is_primary,
        exif=rec.exif_public,
        has_vault=rec.has_vault,
    )


@router.get("/{report_id}/images", response_model=list[ReportImageOut])
async def list_images(
    report_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> list[ReportImageOut]:
    _ = user
    try:
        rows = await asyncio.to_thread(image_service.list_report_images, report_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        ReportImageOut(
            image_id=r.id,
            report_id=r.report_id,
            public_path=r.public_path,
            content_type=r.content_type,
            is_primary=r.is_primary,
            exif=r.exif_public,
            has_vault=r.has_vault,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_ai_tags(report_id: UUID) -> tuple[Optional[AITagsOut], bool]:
    """Return (AITagsOut | None, has_embedding: bool) from DB."""
    from sqlalchemy import text

    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        tag_row = session.execute(
            text(
                """
                SELECT id, brand, colors, category, attributes, mask_boxes, model, created_at
                FROM ai_tags
                WHERE report_id = :rid
                ORDER BY
                    CASE WHEN COALESCE(model, '') <> '' THEN 0 ELSE 1 END,
                    created_at DESC
                LIMIT 1
                """
            ),
            {"rid": str(report_id)},
        ).mappings().first()

        emb_row = session.execute(
            text(
                "SELECT (text_embedding IS NOT NULL) AS has_emb FROM reports WHERE id = :id"
            ),
            {"id": str(report_id)},
        ).mappings().first()
    finally:
        session.close()

    has_embedding = bool(emb_row and emb_row.get("has_emb"))

    if tag_row is None:
        return None, has_embedding

    colors_raw = tag_row.get("colors")
    colors: list[str] = list(colors_raw) if colors_raw else []

    tags_out = AITagsOut(
        tag_id=tag_row["id"],
        brand=tag_row.get("brand"),
        colors=colors,
        category=tag_row.get("category"),
        attributes=tag_row.get("attributes"),
        mask_boxes=tag_row.get("mask_boxes"),
        model=tag_row.get("model"),
        created_at=tag_row.get("created_at"),
    )
    return tags_out, has_embedding
