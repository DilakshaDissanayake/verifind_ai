"""Chat service — Sprint 5/7.

Provisions anonymous chat rooms after PASS and manages messages.
Rule: room only created after a claim_attempt reaches 'passed' status.
Sprint 7: claim-named rooms, analysis seed message, image/voice media.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text

from infrastructure.db.sql_client import get_session


@dataclass
class ChatRoomRecord:
    id: UUID
    match_id: UUID
    owner_id: UUID
    finder_id: UUID
    is_active: bool
    created_at: Optional[datetime]
    title: Optional[str] = None
    lost_title: Optional[str] = None
    found_title: Optional[str] = None
    match_score: Optional[float] = None
    match_band: Optional[str] = None


@dataclass
class ChatMessageRecord:
    id: UUID
    room_id: UUID
    sender_id: UUID
    body: str
    created_at: Optional[datetime]
    message_type: str = "text"
    media_path: Optional[str] = None


def _match_context(match_id: UUID) -> dict[str, Any]:
    """Lost/found titles + fusion scores for room naming and analysis seed."""
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT m.score, m.band, m.vision_score, m.text_score, m.geo_score,
                       m.category_score, m.distance_m,
                       ra.title AS title_a, ra.report_type AS type_a,
                       ra.category AS cat_a, ra.description AS desc_a,
                       rb.title AS title_b, rb.report_type AS type_b,
                       rb.category AS cat_b, rb.description AS desc_b
                FROM matches m
                JOIN reports ra ON ra.id = m.report_a_id
                JOIN reports rb ON rb.id = m.report_b_id
                WHERE m.id = :mid
                """
            ),
            {"mid": str(match_id)},
        ).mappings().first()
    finally:
        session.close()

    if row is None:
        return {
            "title": "Verified claim",
            "lost_title": None,
            "found_title": None,
            "score": None,
            "band": None,
            "analysis": (
                "Ownership verified. Coordinate a safe handover — "
                "identities stay anonymous."
            ),
        }

    type_a = (row["type_a"] or "").upper()
    if type_a == "LOST":
        lost_title, found_title = row["title_a"], row["title_b"]
        lost_cat, found_cat = row["cat_a"], row["cat_b"]
        lost_desc, found_desc = row["desc_a"], row["desc_b"]
    else:
        lost_title, found_title = row["title_b"], row["title_a"]
        lost_cat, found_cat = row["cat_b"], row["cat_a"]
        lost_desc, found_desc = row["desc_b"], row["desc_a"]

    claim_name = (lost_title or found_title or "Item").strip() or "Item"
    title = f"Claim · {claim_name}"

    score = float(row["score"] or 0)
    vision = float(row["vision_score"] or 0)
    text_s = float(row["text_score"] or 0)
    geo = float(row["geo_score"] or 0)
    dist = row["distance_m"]
    dist_line = (
        f"{float(dist):.0f} m apart"
        if dist is not None
        else "distance unavailable"
    )

    def _clip(s: Optional[str], n: int = 120) -> str:
        t = (s or "").strip()
        if not t:
            return "—"
        return t if len(t) <= n else t[: n - 1] + "…"

    analysis = (
        "Match analysis\n"
        f"Lost: {_clip(lost_title)}"
        + (f" ({lost_cat})" if lost_cat else "")
        + "\n"
        f"Found: {_clip(found_title)}"
        + (f" ({found_cat})" if found_cat else "")
        + "\n"
        f"Overall {score * 100:.0f}% · Vision {vision * 100:.0f}% · "
        f"Text {text_s * 100:.0f}% · Geo {geo * 100:.0f}% · {dist_line}\n"
        f"Lost notes: {_clip(lost_desc)}\n"
        f"Found notes: {_clip(found_desc)}\n"
        "Ownership verified — coordinate a safe handover. Identities stay anonymous."
    )

    return {
        "title": title,
        "lost_title": lost_title,
        "found_title": found_title,
        "score": score,
        "band": row["band"],
        "analysis": analysis,
    }


def _enrich_room(row: Any) -> ChatRoomRecord:
    ctx = _match_context(UUID(str(row["match_id"])))
    return ChatRoomRecord(
        id=row["id"],
        match_id=row["match_id"],
        owner_id=row["owner_id"],
        finder_id=row["finder_id"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        title=ctx["title"],
        lost_title=ctx.get("lost_title"),
        found_title=ctx.get("found_title"),
        match_score=ctx.get("score"),
        match_band=ctx.get("band"),
    )


def _seed_analysis_message(*, room_id: UUID, match_id: UUID, sender_id: UUID) -> None:
    """First message in every room: lost+found match analysis (system)."""
    ctx = _match_context(match_id)
    try:
        save_message(
            room_id=room_id,
            sender_id=sender_id,
            body=ctx["analysis"],
            message_type="system",
        )
    except Exception as exc:
        logger.warning("_seed_analysis_message failed room={}: {}", room_id, exc)


def create_chat_room(*, match_id: UUID, claimant_id: UUID) -> UUID:
    """Provision a chat room for a match. Idempotent — returns existing room if exists."""
    session = get_session()
    try:
        existing = session.execute(
            text("SELECT id FROM chat_rooms WHERE match_id = :mid"),
            {"mid": str(match_id)},
        ).mappings().first()
        if existing:
            logger.info("create_chat_room: room already exists match_id={}", match_id)
            return UUID(str(existing["id"]))

        match_row = session.execute(
            text(
                """
                SELECT m.report_a_id, m.report_b_id,
                       ra.user_id AS owner_a, rb.user_id AS owner_b
                FROM matches m
                JOIN reports ra ON ra.id = m.report_a_id
                JOIN reports rb ON rb.id = m.report_b_id
                WHERE m.id = :mid
                """
            ),
            {"mid": str(match_id)},
        ).mappings().first()
    finally:
        session.close()

    if match_row is None:
        raise ValueError(f"Match {match_id} not found")

    owner_a = UUID(str(match_row["owner_a"]))
    owner_b = UUID(str(match_row["owner_b"]))

    if claimant_id == owner_a:
        owner_id, finder_id = owner_a, owner_b
    elif claimant_id == owner_b:
        owner_id, finder_id = owner_b, owner_a
    else:
        owner_id, finder_id = owner_a, owner_b

    room_id = uuid4()
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                INSERT INTO chat_rooms (id, match_id, owner_id, finder_id, is_active)
                VALUES (:id, :mid, :oid, :fid, true)
                ON CONFLICT (match_id) DO UPDATE SET is_active = true
                RETURNING id
                """
            ),
            {
                "id": str(room_id),
                "mid": str(match_id),
                "oid": str(owner_id),
                "fid": str(finder_id),
            },
        ).mappings().first()
        session.commit()
        resolved = UUID(str(row["id"])) if row else room_id
        logger.info("create_chat_room: room_id={} match_id={}", resolved, match_id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if not _has_system_message(resolved):
        _seed_analysis_message(room_id=resolved, match_id=match_id, sender_id=owner_id)
    return resolved


def _has_system_message(room_id: UUID) -> bool:
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT 1 FROM chat_messages
                WHERE room_id = :rid
                  AND COALESCE(message_type, 'text') = 'system'
                LIMIT 1
                """
            ),
            {"rid": str(room_id)},
        ).first()
        return row is not None
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def get_room(room_id: UUID) -> Optional[ChatRoomRecord]:
    session = get_session()
    try:
        row = session.execute(
            text(
                "SELECT id, match_id, owner_id, finder_id, is_active, created_at "
                "FROM chat_rooms WHERE id = :id"
            ),
            {"id": str(room_id)},
        ).mappings().first()
    finally:
        session.close()
    if row is None:
        return None
    room = _enrich_room(row)
    if not _has_system_message(room.id):
        _seed_analysis_message(
            room_id=room.id,
            match_id=UUID(str(room.match_id)),
            sender_id=UUID(str(room.owner_id)),
        )
    return room


def get_room_by_match(match_id: UUID) -> Optional[ChatRoomRecord]:
    session = get_session()
    try:
        row = session.execute(
            text(
                "SELECT id, match_id, owner_id, finder_id, is_active, created_at "
                "FROM chat_rooms WHERE match_id = :mid"
            ),
            {"mid": str(match_id)},
        ).mappings().first()
    finally:
        session.close()
    if row is None:
        return None
    return _enrich_room(row)


def list_rooms_for_user(user_id: UUID) -> list[ChatRoomRecord]:
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT id, match_id, owner_id, finder_id, is_active, created_at
                FROM chat_rooms
                WHERE is_active = true
                  AND (owner_id = :uid OR finder_id = :uid)
                ORDER BY created_at DESC
                """
            ),
            {"uid": str(user_id)},
        ).mappings().all()
    finally:
        session.close()
    return [_enrich_room(r) for r in rows]


def other_participant(room: ChatRoomRecord, user_id: UUID) -> UUID:
    uid = str(user_id)
    if uid == str(room.owner_id):
        return UUID(str(room.finder_id))
    return UUID(str(room.owner_id))


def assert_room_member(room: ChatRoomRecord, user_id: UUID) -> None:
    uid = str(user_id)
    if uid not in (str(room.owner_id), str(room.finder_id)):
        raise PermissionError(f"User {user_id} is not a member of room {room.id}")


def save_message(
    *,
    room_id: UUID,
    sender_id: UUID,
    body: str,
    message_type: str = "text",
    media_path: Optional[str] = None,
) -> ChatMessageRecord:
    msg_type = (message_type or "text").lower()
    if msg_type not in ("text", "image", "voice", "system"):
        raise ValueError(f"Invalid message_type: {msg_type}")

    text_body = (body or "").strip()
    if msg_type == "text" and not text_body:
        raise ValueError("Message body cannot be empty")
    if msg_type in ("image", "voice") and not media_path:
        raise ValueError("media_path required for image/voice messages")
    if msg_type == "system" and not text_body:
        raise ValueError("System message body cannot be empty")
    if not text_body:
        text_body = "[image]" if msg_type == "image" else "[voice]" if msg_type == "voice" else ""

    msg_id = uuid4()
    session = get_session()
    try:
        try:
            session.execute(
                text(
                    """
                    INSERT INTO chat_messages
                        (id, room_id, sender_id, body, message_type, media_path)
                    VALUES (:id, :rid, :sid, :body, :mtype, :mpath)
                    """
                ),
                {
                    "id": str(msg_id),
                    "rid": str(room_id),
                    "sid": str(sender_id),
                    "body": text_body,
                    "mtype": msg_type,
                    "mpath": media_path,
                },
            )
        except Exception:
            session.rollback()
            session.execute(
                text(
                    """
                    INSERT INTO chat_messages (id, room_id, sender_id, body)
                    VALUES (:id, :rid, :sid, :body)
                    """
                ),
                {
                    "id": str(msg_id),
                    "rid": str(room_id),
                    "sid": str(sender_id),
                    "body": text_body if msg_type == "text" else f"[{msg_type}] {text_body}",
                },
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return ChatMessageRecord(
        id=msg_id,
        room_id=room_id,
        sender_id=sender_id,
        body=text_body,
        created_at=None,
        message_type=msg_type,
        media_path=media_path,
    )


def get_messages(
    room_id: UUID,
    *,
    limit: int = 100,
    before_id: Optional[UUID] = None,
) -> list[ChatMessageRecord]:
    session = get_session()
    try:
        try:
            if before_id:
                rows = session.execute(
                    text(
                        """
                        SELECT id, room_id, sender_id, body, created_at,
                               COALESCE(message_type, 'text') AS message_type,
                               media_path
                        FROM chat_messages
                        WHERE room_id = :rid
                          AND created_at < (
                            SELECT created_at FROM chat_messages WHERE id = :bid
                          )
                        ORDER BY created_at DESC
                        LIMIT :lim
                        """
                    ),
                    {"rid": str(room_id), "bid": str(before_id), "lim": limit},
                ).mappings().all()
            else:
                rows = session.execute(
                    text(
                        """
                        SELECT id, room_id, sender_id, body, created_at,
                               COALESCE(message_type, 'text') AS message_type,
                               media_path
                        FROM chat_messages
                        WHERE room_id = :rid
                        ORDER BY created_at DESC
                        LIMIT :lim
                        """
                    ),
                    {"rid": str(room_id), "lim": limit},
                ).mappings().all()
        except Exception:
            session.rollback()
            rows = session.execute(
                text(
                    """
                    SELECT id, room_id, sender_id, body, created_at
                    FROM chat_messages
                    WHERE room_id = :rid
                    ORDER BY created_at DESC
                    LIMIT :lim
                    """
                ),
                {"rid": str(room_id), "lim": limit},
            ).mappings().all()
    finally:
        session.close()

    return [
        ChatMessageRecord(
            id=r["id"],
            room_id=r["room_id"],
            sender_id=r["sender_id"],
            body=r["body"],
            created_at=r["created_at"],
            message_type=str(r.get("message_type") or "text"),
            media_path=r.get("media_path"),
        )
        for r in reversed(rows)
    ]


def claim_context_for_reports(
    user_id: UUID,
    report_ids: list[UUID],
) -> dict[UUID, dict[str, Any]]:
    """For nearby: map report_id → best claim status + chat_room for this user."""
    if not report_ids:
        return {}
    params: dict[str, Any] = {"uid": str(user_id)}
    placeholders: list[str] = []
    for i, rid in enumerate(report_ids):
        key = f"rid{i}"
        params[key] = str(rid)
        placeholders.append(f"CAST(:{key} AS uuid)")
    ids_sql = ", ".join(placeholders)

    session = get_session()
    try:
        rows = session.execute(
            text(
                f"""
                SELECT DISTINCT ON (rep_id)
                       rep_id,
                       ca.status AS claim_status,
                       vs.decision AS verification_decision,
                       cr.id AS chat_room_id
                FROM (
                    SELECT m.id AS match_id, m.report_a_id AS rep_id
                    FROM matches m
                    WHERE m.report_a_id IN ({ids_sql})
                    UNION ALL
                    SELECT m.id AS match_id, m.report_b_id AS rep_id
                    FROM matches m
                    WHERE m.report_b_id IN ({ids_sql})
                ) pairs
                JOIN claim_attempts ca
                  ON ca.match_id = pairs.match_id
                 AND (
                      ca.claimant_id = :uid
                      OR EXISTS (
                           SELECT 1 FROM chat_rooms cr0
                           WHERE cr0.match_id = pairs.match_id
                             AND cr0.is_active = true
                             AND (cr0.owner_id = :uid OR cr0.finder_id = :uid)
                      )
                 )
                LEFT JOIN verification_sessions vs ON vs.claim_attempt_id = ca.id
                LEFT JOIN chat_rooms cr
                  ON cr.match_id = pairs.match_id AND cr.is_active = true
                ORDER BY rep_id,
                  CASE ca.status
                    WHEN 'passed' THEN 0
                    WHEN 'review' THEN 1
                    WHEN 'started' THEN 2
                    WHEN 'blocked' THEN 3
                    ELSE 4
                  END,
                  ca.created_at DESC
                """
            ),
            params,
        ).mappings().all()
    finally:
        session.close()

    out: dict[UUID, dict[str, Any]] = {}
    for r in rows:
        rid = UUID(str(r["rep_id"]))
        out[rid] = {
            "claim_status": r.get("claim_status"),
            "verification_decision": r.get("verification_decision"),
            "chat_room_id": (
                UUID(str(r["chat_room_id"])) if r.get("chat_room_id") else None
            ),
        }
    return out


def upload_chat_media(
    *,
    room_id: UUID,
    sender_id: UUID,
    data: bytes,
    filename: str,
    content_type: str,
    message_type: str,
    caption: str = "",
) -> ChatMessageRecord:
    """Store image/voice in public-sanitized and create a chat message."""
    from infrastructure.storage.image_storage import upload_public

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    if message_type == "image" and ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    if message_type == "voice" and ext not in (
        "m4a",
        "aac",
        "mp3",
        "wav",
        "ogg",
        "webm",
    ):
        ext = "m4a"

    msg_id = uuid4()
    path = f"chat/{room_id}/{msg_id}.{ext}"
    upload_public(path, data, content_type=content_type)
    return save_message(
        room_id=room_id,
        sender_id=sender_id,
        body=caption or ("[image]" if message_type == "image" else "[voice]"),
        message_type=message_type,
        media_path=path,
    )


def media_public_url(media_path: Optional[str]) -> Optional[str]:
    if not media_path:
        return None
    from infrastructure.storage.image_storage import public_url

    return public_url(media_path)


def complete_handover(*, room_id: UUID, actor_id: UUID) -> dict[str, Any]:
    """
    Lost + found parties finished handover.
    Closes both reports (hidden from public feeds) and deactivates the chat room.
    """
    room = get_room(room_id)
    if room is None:
        raise ValueError("Chat room not found")
    if str(actor_id) not in (str(room.owner_id), str(room.finder_id)):
        raise PermissionError("Not a participant of this chat")
    if not room.is_active:
        return {
            "room_id": str(room_id),
            "match_id": str(room.match_id),
            "already_complete": True,
            "message": "Handover already marked complete — posts stay hidden.",
        }

    from services.claim_service import mark_match_reports_closed

    mark_match_reports_closed(room.match_id)

    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE chat_rooms
                SET is_active = false
                WHERE id = :rid
                """
            ),
            {"rid": str(room_id)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    save_message(
        room_id=room_id,
        sender_id=actor_id,
        body=(
            "Handover marked complete. Both lost and found posts are now hidden "
            "from public feeds. Thank you for using VERIFIND safely."
        ),
        message_type="system",
    )

    try:
        from services.admin_service import _write_audit

        _write_audit(
            actor_id=actor_id,
            action="handover_complete",
            entity_type="chat_room",
            entity_id=room_id,
            meta={"match_id": str(room.match_id)},
        )
    except Exception as exc:
        logger.warning("handover audit failed: {}", exc)

    logger.info(
        "handover_complete room={} match={} by={}",
        room_id,
        room.match_id,
        actor_id,
    )
    return {
        "room_id": str(room_id),
        "match_id": str(room.match_id),
        "already_complete": False,
        "message": "Handover complete — posts are hidden from the public.",
    }
