"""Chat router — Sprint 5/7.

REST:
  GET  /chat/rooms                       → list rooms (claim-named)
  GET  /chat/rooms/{room_id}             → room info
  GET  /chat/rooms/{room_id}/messages    → message history
  POST /chat/rooms/{room_id}/messages    → send text
  POST /chat/rooms/{room_id}/media       → send image/voice

WebSocket:
  WS   /ws/chat/{room_id}?token=<jwt>   → real-time pub/sub via Redis

Invariant: room is only accessible to the two participants (owner + finder).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from loguru import logger

from api.deps import CurrentUser, get_current_user
from api.schemas import (
    ChatHistoryResponse,
    ChatMessageOut,
    ChatRoomListResponse,
    ChatRoomOut,
    HandoverCompleteResponse,
    SendMessageRequest,
)

router = APIRouter(prefix="/chat", tags=["chat"])
ws_router = APIRouter(tags=["chat-ws"])


def _room_out(room, viewer_id: UUID) -> ChatRoomOut:
    return ChatRoomOut(
        room_id=room.id,
        match_id=room.match_id,
        owner_id=room.owner_id,
        finder_id=room.finder_id,
        is_active=room.is_active,
        created_at=room.created_at,
        title=room.title,
        lost_title=room.lost_title,
        found_title=room.found_title,
        match_score=room.match_score,
        match_band=room.match_band,
        viewer_id=viewer_id,
    )


def _msg_out(m, viewer_id: UUID) -> ChatMessageOut:
    from services.chat_service import media_public_url

    mtype = getattr(m, "message_type", None) or "text"
    if mtype not in ("text", "image", "voice", "system"):
        mtype = "text"
    return ChatMessageOut(
        message_id=m.id,
        room_id=m.room_id,
        sender_id=m.sender_id,
        body=m.body,
        created_at=m.created_at,
        message_type=mtype,  # type: ignore[arg-type]
        media_url=media_public_url(getattr(m, "media_path", None)),
        is_mine=str(m.sender_id) == str(viewer_id) and mtype != "system",
    )


@router.get("/rooms", response_model=ChatRoomListResponse)
async def list_my_rooms(
    user: CurrentUser = Depends(get_current_user),
) -> ChatRoomListResponse:
    """List active chat rooms for the current user (both lost + found parties)."""
    from services.chat_service import list_rooms_for_user
    from services.user_service import ensure_app_user

    app_uid = UUID(str(await asyncio.to_thread(ensure_app_user, auth_user_id=user.id, email=user.email)))
    rooms = await asyncio.to_thread(list_rooms_for_user, app_uid)
    items = [_room_out(r, app_uid) for r in rooms]
    return ChatRoomListResponse(items=items, count=len(items))


@router.get("/rooms/by-match/{match_id}", response_model=ChatRoomOut)
async def get_room_for_match(
    match_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> ChatRoomOut:
    """Lookup chat room after admin PASS — mobile polls this when claim was REVIEW."""
    from services.chat_service import assert_room_member, get_room_by_match
    from services.user_service import ensure_app_user

    app_uid = UUID(str(await asyncio.to_thread(ensure_app_user, auth_user_id=user.id, email=user.email)))
    room = await asyncio.to_thread(get_room_by_match, match_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Chat room not ready yet")
    try:
        assert_room_member(room, app_uid)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _room_out(room, app_uid)


@router.get("/rooms/{room_id}", response_model=ChatRoomOut)
async def get_room(
    room_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> ChatRoomOut:
    from services.chat_service import assert_room_member, get_room
    from services.user_service import ensure_app_user

    app_uid = UUID(str(await asyncio.to_thread(ensure_app_user, auth_user_id=user.id, email=user.email)))
    room = await asyncio.to_thread(get_room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        assert_room_member(room, app_uid)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _room_out(room, app_uid)


@router.post(
    "/rooms/{room_id}/handover-complete",
    response_model=HandoverCompleteResponse,
)
async def handover_complete(
    room_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> HandoverCompleteResponse:
    """Mark safe handover done — hide both posts from public; admin can still export."""
    from services.chat_service import complete_handover
    from services.user_service import ensure_app_user

    app_uid = UUID(
        str(await asyncio.to_thread(ensure_app_user, auth_user_id=user.id, email=user.email))
    )
    try:
        result = await asyncio.to_thread(
            complete_handover, room_id=room_id, actor_id=app_uid
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("handover_complete failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return HandoverCompleteResponse(
        room_id=UUID(result["room_id"]),
        match_id=UUID(result["match_id"]),
        already_complete=bool(result.get("already_complete")),
        message=str(result.get("message") or ""),
    )


@router.get("/rooms/{room_id}/messages", response_model=ChatHistoryResponse)
async def get_messages(
    room_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> ChatHistoryResponse:
    from services.chat_service import assert_room_member, get_messages, get_room
    from services.user_service import ensure_app_user

    app_uid = UUID(str(await asyncio.to_thread(ensure_app_user, auth_user_id=user.id, email=user.email)))
    room = await asyncio.to_thread(get_room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        assert_room_member(room, app_uid)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    messages = await asyncio.to_thread(get_messages, room_id, limit=limit)
    items = [_msg_out(m, app_uid) for m in messages]
    return ChatHistoryResponse(
        room_id=room_id,
        messages=items,
        count=len(items),
        viewer_id=app_uid,
        title=room.title,
    )


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageOut, status_code=201)
async def send_message(
    room_id: UUID,
    body: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ChatMessageOut:
    from services.chat_service import assert_room_member, get_room, save_message
    from services.user_service import ensure_app_user

    app_uid = UUID(str(await asyncio.to_thread(ensure_app_user, auth_user_id=user.id, email=user.email)))
    room = await asyncio.to_thread(get_room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.is_active:
        raise HTTPException(status_code=400, detail="Chat room is closed")
    try:
        assert_room_member(room, app_uid)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    msg = await asyncio.to_thread(save_message, room_id=room_id, sender_id=app_uid, body=body.body)
    out = _msg_out(msg, app_uid)

    payload = {
        "message_id": str(msg.id),
        "room_id": str(room_id),
        "sender_id": str(app_uid),
        "body": msg.body,
        "message_type": "text",
        "media_url": None,
        "is_mine": False,
    }
    await _manager.broadcast(str(room_id), payload)
    await _redis_publish(str(room_id), payload)

    try:
        from services.chat_service import other_participant
        from services.notification_service import notify_chat_message

        other = other_participant(room, app_uid)
        await asyncio.to_thread(
            notify_chat_message,
            recipient_id=other,
            sender_id=app_uid,
            room_id=room_id,
            match_id=UUID(str(room.match_id)),
            preview=msg.body,
        )
    except Exception as exc:
        logger.debug("chat message notify skipped: {}", exc)

    return out


@router.post("/rooms/{room_id}/media", response_model=ChatMessageOut, status_code=201)
async def send_media(
    room_id: UUID,
    file: UploadFile = File(...),
    message_type: str = Form(..., pattern="^(image|voice)$"),
    caption: Optional[str] = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> ChatMessageOut:
    """Upload an image or voice note into the anonymous chat room."""
    from services.chat_service import assert_room_member, get_room, upload_chat_media
    from services.user_service import ensure_app_user

    app_uid = UUID(str(await asyncio.to_thread(ensure_app_user, auth_user_id=user.id, email=user.email)))
    room = await asyncio.to_thread(get_room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.is_active:
        raise HTTPException(status_code=400, detail="Chat room is closed")
    try:
        assert_room_member(room, app_uid)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 15MB)")

    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or ("voice.m4a" if message_type == "voice" else "image.jpg")

    try:
        msg = await asyncio.to_thread(
            upload_chat_media,
            room_id=room_id,
            sender_id=app_uid,
            data=data,
            filename=filename,
            content_type=content_type,
            message_type=message_type,
            caption=(caption or "").strip(),
        )
    except Exception as exc:
        logger.exception("chat media upload failed")
        raise HTTPException(status_code=503, detail=f"Upload failed: {exc}") from exc

    out = _msg_out(msg, app_uid)
    payload = {
        "message_id": str(msg.id),
        "room_id": str(room_id),
        "sender_id": str(app_uid),
        "body": msg.body,
        "message_type": message_type,
        "media_url": out.media_url,
        "is_mine": False,
    }
    await _manager.broadcast(str(room_id), payload)
    await _redis_publish(str(room_id), payload)

    try:
        from services.chat_service import other_participant
        from services.notification_service import notify_chat_message

        other = other_participant(room, app_uid)
        preview = "📷 Photo" if message_type == "image" else "🎤 Voice note"
        await asyncio.to_thread(
            notify_chat_message,
            recipient_id=other,
            sender_id=app_uid,
            room_id=room_id,
            match_id=UUID(str(room.match_id)),
            preview=preview,
        )
    except Exception as exc:
        logger.debug("chat media notify skipped: {}", exc)

    return out


# ---------------------------------------------------------------------------
# WebSocket — real-time chat
# ---------------------------------------------------------------------------

class _ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms.setdefault(room_id, []).append(ws)
        logger.info("ws connected room={} total={}", room_id, len(self._rooms[room_id]))

    def disconnect(self, room_id: str, ws: WebSocket) -> None:
        conns = self._rooms.get(room_id, [])
        if ws in conns:
            conns.remove(ws)
        logger.info("ws disconnected room={} total={}", room_id, len(conns))

    async def broadcast(self, room_id: str, payload: dict) -> None:
        text = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in list(self._rooms.get(room_id, [])):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)


_manager = _ConnectionManager()


@ws_router.websocket("/ws/chat/{room_id}")
async def websocket_chat(
    room_id: UUID,
    websocket: WebSocket,
    token: str = Query(..., description="Bearer JWT token"),
) -> None:
    """Anonymous WebSocket chat. Auth via ?token= query param."""
    app_uid: UUID | None = None
    try:
        from api.deps import verify_token
        user_info = verify_token(token)
        from services.user_service import ensure_app_user
        app_uid = UUID(str(ensure_app_user(auth_user_id=user_info.id, email=user_info.email)))
    except Exception as exc:
        logger.warning("ws auth failed room={}: {}", room_id, exc)
        await websocket.close(code=4001)
        return

    from services.chat_service import assert_room_member, get_room, save_message
    room = get_room(room_id)
    if room is None or not room.is_active:
        await websocket.close(code=4004)
        return
    try:
        assert_room_member(room, app_uid)
    except PermissionError:
        await websocket.close(code=4003)
        return

    room_key = str(room_id)
    await _manager.connect(room_key, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                body = str(data.get("body", "")).strip()
                if not body:
                    continue
            except (json.JSONDecodeError, ValueError):
                body = raw.strip()

            if not body:
                continue

            msg = save_message(room_id=room_id, sender_id=app_uid, body=body)
            payload = {
                "message_id": str(msg.id),
                "room_id": str(room_id),
                "sender_id": str(app_uid),
                "body": msg.body,
                "message_type": "text",
                "media_url": None,
                "is_mine": False,
            }
            await _manager.broadcast(room_key, payload)
            await _redis_publish(room_key, payload)
            try:
                from services.chat_service import other_participant
                from services.notification_service import notify_chat_message

                other = other_participant(room, app_uid)
                notify_chat_message(
                    recipient_id=other,
                    sender_id=app_uid,
                    room_id=room_id,
                    match_id=UUID(str(room.match_id)),
                    preview=msg.body,
                )
            except Exception as exc:
                logger.debug("ws chat notify skipped: {}", exc)

    except WebSocketDisconnect:
        _manager.disconnect(room_key, websocket)
    except Exception as exc:
        logger.warning("ws error room={}: {}", room_id, exc)
        _manager.disconnect(room_key, websocket)


async def _redis_publish(room_id: str, payload: dict) -> None:
    """Publish message to Redis channel for multi-instance fan-out."""
    try:
        import redis.asyncio as aioredis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url)
        await r.publish(f"chat:{room_id}", json.dumps(payload))
        await r.aclose()
    except Exception as exc:
        logger.debug("redis_publish skipped ({}): {}", room_id, exc)
