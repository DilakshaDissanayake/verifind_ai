"""Report persist / list / get / patch — Sprint 2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import text

from infrastructure.db.sql_client import get_session
from services.geo_service import fuzz_coordinates
from services.user_service import ensure_app_user


@dataclass
class ReportRecord:
    id: UUID
    user_id: UUID
    report_type: str
    category: Optional[str]
    title: Optional[str]
    description: Optional[str]
    status: str
    latitude: Optional[float]
    longitude: Optional[float]
    location_label: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


def _map_row(row: Any) -> ReportRecord:
    return ReportRecord(
        id=row["id"],
        user_id=row["user_id"],
        report_type=row["report_type"],
        category=row["category"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        latitude=row["lat"],
        longitude=row["lon"],
        location_label=row["location_label"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_SELECT = """
    SELECT
        id, user_id, report_type, category, title, description, status,
        location_label, created_at, updated_at,
        ST_Y(location::geometry) AS lat,
        ST_X(location::geometry) AS lon
    FROM reports
"""


def create_report(
    *,
    auth_user_id: str,
    email: Optional[str],
    report_type: str,
    category: Optional[str],
    title: Optional[str],
    description: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    location_label: Optional[str],
    apply_server_fuzz: bool = True,
) -> ReportRecord:
    """Insert LOST/FOUND with fuzzed geography. Returns stored row."""
    app_user_id = ensure_app_user(auth_user_id=auth_user_id, email=email)
    report_id = uuid4()

    fuzzed_lat: Optional[float] = None
    fuzzed_lon: Optional[float] = None
    if latitude is not None and longitude is not None:
        if apply_server_fuzz:
            fuzzed_lat, fuzzed_lon = fuzz_coordinates(latitude, longitude)
        else:
            fuzzed_lat, fuzzed_lon = latitude, longitude

    session = get_session()
    try:
        if fuzzed_lat is not None and fuzzed_lon is not None:
            session.execute(
                text(
                    """
                    INSERT INTO reports (
                        id, user_id, report_type, category, title, description,
                        status, location, location_label
                    ) VALUES (
                        :id, :user_id, :report_type, :category, :title, :description,
                        'pending',
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                        :location_label
                    )
                    """
                ),
                {
                    "id": str(report_id),
                    "user_id": str(app_user_id),
                    "report_type": report_type,
                    "category": category,
                    "title": title,
                    "description": description,
                    "lat": fuzzed_lat,
                    "lon": fuzzed_lon,
                    "location_label": location_label,
                },
            )
        else:
            session.execute(
                text(
                    """
                    INSERT INTO reports (
                        id, user_id, report_type, category, title, description,
                        status, location_label
                    ) VALUES (
                        :id, :user_id, :report_type, :category, :title, :description,
                        'pending', :location_label
                    )
                    """
                ),
                {
                    "id": str(report_id),
                    "user_id": str(app_user_id),
                    "report_type": report_type,
                    "category": category,
                    "title": title,
                    "description": description,
                    "location_label": location_label,
                },
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    record = get_report(report_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report insert failed",
        )
    return record


def get_report(report_id: UUID) -> Optional[ReportRecord]:
    session = get_session()
    try:
        row = session.execute(
            text(_SELECT + " WHERE id = :id"),
            {"id": str(report_id)},
        ).mappings().first()
        return _map_row(row) if row else None
    finally:
        session.close()


def list_reports_for_user(
    *,
    auth_user_id: str,
    email: Optional[str] = None,
    report_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
) -> list[ReportRecord]:
    app_user_id = ensure_app_user(auth_user_id=auth_user_id, email=email)
    clauses = ["user_id = :user_id"]
    params: dict[str, Any] = {"user_id": str(app_user_id), "limit": limit}
    if report_type:
        clauses.append("report_type = :report_type")
        params["report_type"] = report_type
    if status_filter:
        clauses.append("status = :status")
        params["status"] = status_filter
    where = " AND ".join(clauses)
    session = get_session()
    try:
        rows = session.execute(
            text(f"{_SELECT} WHERE {where} ORDER BY created_at DESC LIMIT :limit"),
            params,
        ).mappings().all()
        return [_map_row(r) for r in rows]
    finally:
        session.close()


def update_report(
    *,
    report_id: UUID,
    auth_user_id: str,
    email: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    status_value: Optional[str] = None,
) -> ReportRecord:
    app_user_id = ensure_app_user(auth_user_id=auth_user_id, email=email)
    existing = get_report(report_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if existing.user_id != app_user_id:
        raise HTTPException(status_code=403, detail="Not report owner")

    sets = ["updated_at = now()"]
    params: dict[str, Any] = {"id": str(report_id)}
    if title is not None:
        sets.append("title = :title")
        params["title"] = title
    if description is not None:
        sets.append("description = :description")
        params["description"] = description
    if category is not None:
        sets.append("category = :category")
        params["category"] = category
    if status_value is not None:
        sets.append("status = :status")
        params["status"] = status_value

    session = get_session()
    try:
        session.execute(
            text(f"UPDATE reports SET {', '.join(sets)} WHERE id = :id"),
            params,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    updated = get_report(report_id)
    assert updated is not None
    return updated


def set_report_status(report_id: UUID, status_value: str) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                "UPDATE reports SET status = :status, updated_at = now() "
                "WHERE id = :id"
            ),
            {"id": str(report_id), "status": status_value},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_owner_report(
    *,
    report_id: UUID,
    auth_user_id: str,
    email: Optional[str] = None,
    reason: str = "self_found",
) -> tuple[ReportRecord, bool, int]:
    """Owner self-find / withdraw: status=closed. Never hard-deletes.

    Hides the post from Nearby + matching. Related chats are deactivated.
    The counterpart FOUND/LOST listing is left open (different item / still held).

    Returns (record, already_closed, chats_closed).
    """
    from loguru import logger

    if reason not in ("self_found", "withdrawn"):
        raise HTTPException(status_code=400, detail="Invalid close reason")

    app_user_id = ensure_app_user(auth_user_id=auth_user_id, email=email)
    existing = get_report(report_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if existing.user_id != app_user_id:
        raise HTTPException(status_code=403, detail="Not report owner")
    if existing.status == "flagged":
        raise HTTPException(
            status_code=409,
            detail="This report is flagged for review and cannot be closed here",
        )
    if existing.status == "closed":
        return existing, True, 0

    set_report_status(report_id, "closed")
    chats_closed = _deactivate_chats_for_report(
        report_id=report_id,
        actor_id=app_user_id,
        reason=reason,
    )

    try:
        from services.admin_service import _write_audit

        _write_audit(
            actor_id=app_user_id,
            action="report_owner_close",
            entity_type="report",
            entity_id=report_id,
            meta={"reason": reason, "chats_closed": chats_closed},
        )
    except Exception as exc:
        logger.warning("owner-close audit failed: {}", exc)

    updated = get_report(report_id)
    assert updated is not None
    return updated, False, chats_closed


def _deactivate_chats_for_report(
    *,
    report_id: UUID,
    actor_id: UUID,
    reason: str,
) -> int:
    """Close open handover chats tied to this listing. Does not close the other report."""
    from loguru import logger

    session = get_session()
    room_ids: list[UUID] = []
    try:
        rows = session.execute(
            text(
                """
                SELECT cr.id
                FROM chat_rooms cr
                JOIN matches m ON m.id = cr.match_id
                WHERE cr.is_active = true
                  AND (m.report_a_id = :rid OR m.report_b_id = :rid)
                """
            ),
            {"rid": str(report_id)},
        ).mappings().all()
        room_ids = [UUID(str(r["id"])) for r in rows]
        for rid in room_ids:
            session.execute(
                text("UPDATE chat_rooms SET is_active = false WHERE id = :id"),
                {"id": str(rid)},
            )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("deactivate chats for report {} failed: {}", report_id, exc)
        return 0
    finally:
        session.close()

    if not room_ids:
        return 0

    body = (
        "The owner found this item themselves. The listing is no longer public "
        "and this chat is closed."
        if reason == "self_found"
        else "The poster took this listing down. The listing is no longer public "
        "and this chat is closed."
    )
    try:
        from services.chat_service import save_message

        for rid in room_ids:
            save_message(
                room_id=rid,
                sender_id=actor_id,
                body=body,
                message_type="system",
            )
    except Exception as exc:
        logger.warning("owner-close system messages failed: {}", exc)

    return len(room_ids)
