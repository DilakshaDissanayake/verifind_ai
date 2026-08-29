"""Notification service — Sprint 4+.

Inserts in-app notification rows; FCM push is a stub until device tokens exist.
Legacy schema may still have NOT NULL `kind` alongside `type` — always set both.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text

from infrastructure.config import GEO_RADIUS_M
from infrastructure.db.sql_client import get_session


def notify_match(
    *,
    user_id: UUID,
    match_id: UUID,
    report_id: UUID,
    matched_report_id: UUID,
    score: float,
    band: str,
    distance_m: Optional[float] = None,
) -> bool:
    """Insert in-app notification for a match event (idempotent per user+match)."""
    try:
        created = _insert_typed_notification(
            user_id=user_id,
            notif_type="match_found",
            match_id=match_id,
            report_id=report_id,
            matched_report_id=matched_report_id,
            band=band,
            score=score,
            distance_m=distance_m,
            dedupe_on_match=True,
        )
        if created:
            _send_fcm_stub(user_id=user_id, band=band, score=score)
        return created
    except Exception as exc:
        logger.warning("notify_match failed user={} match={}: {}", user_id, match_id, exc)
        return False


def notify_chat_ready(
    *,
    user_id: UUID,
    match_id: UUID,
    chat_room_id: UUID,
    report_id: Optional[UUID] = None,
) -> bool:
    """Notify a participant that anonymous chat is open after PASS / admin PASS."""
    try:
        created = _insert_typed_notification(
            user_id=user_id,
            notif_type="chat_ready",
            match_id=match_id,
            report_id=report_id,
            matched_report_id=None,
            band="PASS",
            score=1.0,
            distance_m=None,
            chat_room_id=chat_room_id,
            dedupe_on_match=True,
        )
        if created:
            _send_fcm_stub(user_id=user_id, band="PASS", score=1.0)
        return created
    except Exception as exc:
        logger.warning(
            "notify_chat_ready failed user={} match={}: {}", user_id, match_id, exc
        )
        return False


def notify_nearby_post(
    *,
    poster_user_id: UUID,
    report_id: UUID,
    report_type: str,
    title: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_m: int = GEO_RADIUS_M,
) -> int:
    """Alert other users within radius_m of a newly created report. Fail-soft."""
    if lat is None or lon is None:
        return 0
    try:
        from services.geo_service import nearby_users_to_notify

        nearby = nearby_users_to_notify(
            lat,
            lon,
            exclude_user_id=poster_user_id,
            radius_m=radius_m,
        )
        preview = (title or "").strip()[:80] or f"New {report_type.lower()} nearby"
        created = 0
        for hit in nearby:
            ok = _insert_typed_notification(
                user_id=hit.user_id,
                notif_type="nearby_post",
                match_id=None,
                report_id=report_id,
                matched_report_id=None,
                band=report_type,
                score=1.0,
                distance_m=hit.distance_m,
                dedupe_on_match=False,
                dedupe_on_report=True,
                payload_preview=preview,
            )
            if ok:
                created += 1
        if created:
            logger.info(
                "nearby_post alerts created={} report={} type={}",
                created,
                report_id,
                report_type,
            )
        return created
    except Exception as exc:
        logger.warning(
            "notify_nearby_post failed report={} poster={}: {}",
            report_id,
            poster_user_id,
            exc,
        )
        return 0


def notify_chat_message(
    *,
    recipient_id: UUID,
    sender_id: UUID,
    room_id: UUID,
    match_id: UUID,
    preview: str,
) -> bool:
    """Notify the other participant when a new chat message arrives."""
    if recipient_id == sender_id:
        return False
    try:
        preview_clean = (preview or "").strip()[:120]
        created = _insert_typed_notification(
            user_id=recipient_id,
            notif_type="chat_message",
            match_id=match_id,
            report_id=None,
            matched_report_id=None,
            band="CHAT",
            score=1.0,
            distance_m=None,
            chat_room_id=room_id,
            dedupe_on_match=False,
            payload_preview=preview_clean,
        )
        if created:
            _send_fcm_stub(user_id=recipient_id, band="CHAT", score=1.0)
        return created
    except Exception as exc:
        logger.warning(
            "notify_chat_message failed recipient={} room={}: {}",
            recipient_id,
            room_id,
            exc,
        )
        return False


def _insert_typed_notification(
    *,
    user_id: UUID,
    notif_type: str,
    match_id: Optional[UUID],
    report_id: Optional[UUID],
    matched_report_id: Optional[UUID],
    band: Optional[str],
    score: Optional[float],
    distance_m: Optional[float],
    chat_room_id: Optional[UUID] = None,
    dedupe_on_match: bool = False,
    dedupe_on_report: bool = False,
    payload_preview: Optional[str] = None,
) -> bool:
    """Insert notification; sets both `type` and legacy `kind` when present."""
    session = get_session()
    try:
        if dedupe_on_match and match_id is not None:
            existing = session.execute(
                text(
                    """
                    SELECT id FROM notifications
                    WHERE user_id = :uid
                      AND match_id = :mid
                      AND type = :ntype
                    LIMIT 1
                    """
                ),
                {
                    "uid": str(user_id),
                    "mid": str(match_id),
                    "ntype": notif_type,
                },
            ).mappings().first()
            if existing:
                return False

        if dedupe_on_report and report_id is not None:
            existing = session.execute(
                text(
                    """
                    SELECT id FROM notifications
                    WHERE user_id = :uid
                      AND report_id = :rid
                      AND type = :ntype
                    LIMIT 1
                    """
                ),
                {
                    "uid": str(user_id),
                    "rid": str(report_id),
                    "ntype": notif_type,
                },
            ).mappings().first()
            if existing:
                return False

        has_kind = _column_exists(session, "notifications", "kind")
        has_payload = _column_exists(session, "notifications", "payload")
        has_chat_room = _column_exists(session, "notifications", "chat_room_id")

        cols = [
            "id",
            "user_id",
            "type",
            "match_id",
            "report_id",
            "matched_report_id",
            "band",
            "score",
            "distance_m",
            "is_read",
        ]
        vals = [
            ":id",
            ":uid",
            ":ntype",
            ":mid",
            ":rid",
            ":mrid",
            ":band",
            ":score",
            ":dist",
            "false",
        ]
        params: dict = {
            "id": str(uuid4()),
            "uid": str(user_id),
            "ntype": notif_type,
            "mid": str(match_id) if match_id else None,
            "rid": str(report_id) if report_id else None,
            "mrid": str(matched_report_id) if matched_report_id else None,
            "band": band,
            "score": score,
            "dist": distance_m,
        }

        if has_kind:
            cols.insert(2, "kind")
            vals.insert(2, ":ntype")
        if has_payload:
            cols.append("payload")
            vals.append("CAST(:payload AS jsonb)")
            import json

            params["payload"] = json.dumps(
                {"preview": payload_preview} if payload_preview else {}
            )
        if has_chat_room:
            cols.append("chat_room_id")
            vals.append(":crid")
            params["crid"] = str(chat_room_id) if chat_room_id else None

        sql = (
            f"INSERT INTO notifications ({', '.join(cols)}) "
            f"VALUES ({', '.join(vals)})"
        )
        session.execute(text(sql), params)
        session.commit()
        logger.info(
            "notification created user={} type={} match={}",
            user_id,
            notif_type,
            match_id,
        )
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _column_exists(session, table: str, column: str) -> bool:
    row = session.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :t
              AND column_name = :c
            LIMIT 1
            """
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def _send_fcm_stub(*, user_id: UUID, band: str, score: float) -> None:
    logger.info(
        "FCM stub: would push to user={} band={} score={:.3f}",
        user_id,
        band,
        score,
    )


def get_user_notifications(
    user_id: UUID,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    session = get_session()
    try:
        extra = "AND is_read = false" if unread_only else ""
        has_chat_room = _column_exists(session, "notifications", "chat_room_id")
        has_payload = _column_exists(session, "notifications", "payload")
        chat_col = ", chat_room_id" if has_chat_room else ""
        payload_col = ", payload" if has_payload else ""
        rows = session.execute(
            text(
                f"""
                SELECT id, type, match_id, report_id, matched_report_id,
                       band, score, distance_m, is_read, created_at{chat_col}{payload_col}
                FROM notifications
                WHERE user_id = :uid {extra}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"uid": str(user_id), "limit": limit},
        ).mappings().all()
    finally:
        session.close()

    out = []
    for r in rows:
        d = dict(r)
        if "chat_room_id" not in d:
            d["chat_room_id"] = None
        d["preview"] = _payload_preview(d.pop("payload", None))
        out.append(d)
    return out


def _payload_preview(payload: object) -> Optional[str]:
    if isinstance(payload, str):
        try:
            import json

            payload = json.loads(payload)
        except Exception:
            return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("preview")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:120]
    return None


def mark_notification_read(notif_id: UUID, user_id: UUID) -> bool:
    session = get_session()
    try:
        result = session.execute(
            text(
                "UPDATE notifications SET is_read = true "
                "WHERE id = :id AND user_id = :uid"
            ),
            {"id": str(notif_id), "uid": str(user_id)},
        )
        session.commit()
        return (result.rowcount or 0) > 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
