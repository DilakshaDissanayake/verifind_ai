"""Image upload service — vault store + EXIF (public blur is Sprint 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import text

from infrastructure.config import STORAGE_VAULT_BUCKET
from infrastructure.db.sql_client import get_session
from pipelines.metadata_pipeline import extract_exif, public_exif
from services.report_service import get_report
from services.user_service import ensure_app_user

ALLOWED_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/jpg", "image/png", "image/webp"}
)
# Clients (Flutter Dio) often send application/octet-stream for MultipartFile
_GENERIC_CONTENT_TYPES = frozenset(
    {"", "application/octet-stream", "binary/octet-stream"}
)
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass
class ReportImageRecord:
    id: UUID
    report_id: UUID
    public_path: Optional[str]
    content_type: Optional[str]
    is_primary: bool
    exif_public: Optional[dict[str, Any]]
    has_vault: bool = True


def resolve_content_type(
    content_type: Optional[str],
    *,
    filename: Optional[str] = None,
    data: bytes = b"",
) -> str:
    """Normalize MIME type from header, magic bytes, or filename.

    Flutter MultipartFile.fromBytes often omits contentType → octet-stream.
    """
    raw = (content_type or "").split(";")[0].strip().lower()
    if raw in ALLOWED_CONTENT_TYPES:
        return "image/jpeg" if raw == "image/jpg" else raw

    # Magic-byte sniff (preferred over filename)
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"

    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        mapped = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }.get(ext)
        if mapped:
            return mapped

    if raw in _GENERIC_CONTENT_TYPES or not raw:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type: could not detect image type",
        )
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Unsupported content type: {content_type}",
    )


def upload_report_image(
    *,
    report_id: UUID,
    auth_user_id: str,
    email: Optional[str],
    data: bytes,
    content_type: str,
    filename: Optional[str] = None,
    is_primary: bool = False,
) -> ReportImageRecord:
    content_type = resolve_content_type(
        content_type, filename=filename, data=data
    )
    if not data:
        raise HTTPException(status_code=400, detail="Empty image")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

    app_user_id = ensure_app_user(auth_user_id=auth_user_id, email=email)
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id != app_user_id:
        raise HTTPException(status_code=403, detail="Not report owner")

    image_id = uuid4()
    ext = _ext_for(content_type, filename)
    vault_path = f"{report_id}/{image_id}{ext}"
    exif = extract_exif(data)

    # Original → private-vault only (never put unsanitized original on public bucket)
    try:
        from infrastructure.storage.image_storage import upload_vault

        upload_vault(vault_path, data, content_type=content_type)
    except Exception as exc:
        logger.warning("Vault upload failed (DB row still saved): {}", exc)
        # Persist metadata even if storage is unreachable in local smoke;
        # vault_path records intended location.

    session = get_session()
    try:
        if is_primary:
            session.execute(
                text(
                    "UPDATE report_images SET is_primary = FALSE "
                    "WHERE report_id = :rid"
                ),
                {"rid": str(report_id)},
            )
        session.execute(
            text(
                """
                INSERT INTO report_images (
                    id, report_id, public_path, content_type, exif_json, is_primary
                ) VALUES (
                    :id, :report_id, NULL, :content_type,
                    CAST(:exif_json AS jsonb), :is_primary
                )
                """
            ),
            {
                "id": str(image_id),
                "report_id": str(report_id),
                "content_type": content_type,
                "exif_json": _json_dumps(exif),
                "is_primary": is_primary,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO image_vaults (report_image_id, vault_path, hidden_features)
                VALUES (:image_id, :vault_path, CAST(:hf AS jsonb))
                """
            ),
            {
                "image_id": str(image_id),
                "vault_path": vault_path,
                "hf": _json_dumps({"bucket": STORAGE_VAULT_BUCKET, "pending_sanitize": True}),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return ReportImageRecord(
        id=image_id,
        report_id=report_id,
        public_path=None,  # filled after S4 sanitization
        content_type=content_type,
        is_primary=is_primary,
        exif_public=public_exif(exif),
        has_vault=True,
    )


def list_report_images(report_id: UUID) -> list[ReportImageRecord]:
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT ri.id, ri.report_id, ri.public_path, ri.content_type,
                       ri.is_primary, ri.exif_json,
                       (iv.id IS NOT NULL) AS has_vault
                FROM report_images ri
                LEFT JOIN image_vaults iv ON iv.report_image_id = ri.id
                WHERE ri.report_id = :rid
                ORDER BY ri.is_primary DESC, ri.created_at ASC
                """
            ),
            {"rid": str(report_id)},
        ).mappings().all()
        out: list[ReportImageRecord] = []
        for row in rows:
            exif = row["exif_json"] if isinstance(row["exif_json"], dict) else None
            out.append(
                ReportImageRecord(
                    id=row["id"],
                    report_id=row["report_id"],
                    public_path=row["public_path"],
                    content_type=row["content_type"],
                    is_primary=bool(row["is_primary"]),
                    exif_public=public_exif(exif),
                    has_vault=bool(row["has_vault"]),
                )
            )
        return out
    finally:
        session.close()


def public_urls_for_reports(report_ids: list[UUID]) -> dict[UUID, list[str]]:
    """Batch-resolve sanitized public image URLs for nearby/list feeds."""
    if not report_ids:
        return {}
    from infrastructure.storage.image_storage import public_url

    from sqlalchemy import bindparam

    session = get_session()
    try:
        stmt = text(
            """
            SELECT report_id, public_path
            FROM report_images
            WHERE report_id IN :ids
              AND public_path IS NOT NULL
            ORDER BY is_primary DESC, created_at ASC
            """
        ).bindparams(bindparam("ids", expanding=True))
        rows = session.execute(
            stmt,
            {"ids": [str(r) for r in report_ids]},
        ).mappings().all()
    finally:
        session.close()

    out: dict[UUID, list[str]] = {rid: [] for rid in report_ids}
    for row in rows:
        rid = row["report_id"]
        if isinstance(rid, str):
            rid = UUID(rid)
        url = public_url(row["public_path"])
        if url:
            out.setdefault(rid, []).append(url)
    return out


def set_image_public_path(image_id: UUID, public_path: str) -> None:
    session = get_session()
    try:
        session.execute(
            text("UPDATE report_images SET public_path = :path WHERE id = :id"),
            {"path": public_path, "id": str(image_id)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ext_for(content_type: str, filename: Optional[str]) -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()[:8]
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(content_type, ".bin")


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, default=str)
