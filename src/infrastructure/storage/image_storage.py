"""Supabase Storage wrapper — public-sanitized vs private-vault."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from infrastructure.config import STORAGE_PUBLIC_BUCKET, STORAGE_VAULT_BUCKET
from infrastructure.db.supabase_client import get_supabase


def upload_bytes(
    *,
    bucket: str,
    path: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload bytes; returns storage path (not a signed URL)."""
    if bucket not in (STORAGE_PUBLIC_BUCKET, STORAGE_VAULT_BUCKET):
        raise ValueError(f"Unknown bucket {bucket}")
    client = get_supabase()
    client.storage.from_(bucket).upload(
        path,
        data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return path


def upload_vault(
    path: str, data: bytes, content_type: str = "image/jpeg"
) -> str:
    return upload_bytes(
        bucket=STORAGE_VAULT_BUCKET,
        path=path,
        data=data,
        content_type=content_type,
    )


def upload_public(
    path: str, data: bytes, content_type: str = "image/jpeg"
) -> str:
    """Reserved for sanitized copies (S4 blur). Prefer vault-only until then."""
    return upload_bytes(
        bucket=STORAGE_PUBLIC_BUCKET,
        path=path,
        data=data,
        content_type=content_type,
    )


def public_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        client = get_supabase()
        return client.storage.from_(STORAGE_PUBLIC_BUCKET).get_public_url(path)
    except Exception as exc:
        logger.warning("public_url failed: {}", exc)
        return None


def signed_vault_url(path: Optional[str], expires_in: int = 3600) -> Optional[str]:
    """Short-lived signed URL for private-vault — admin REVIEW only."""
    if not path:
        return None
    try:
        client = get_supabase()
        res = client.storage.from_(STORAGE_VAULT_BUCKET).create_signed_url(
            path, expires_in
        )
        if isinstance(res, dict):
            return res.get("signedURL") or res.get("signedUrl")
        # supabase-py may return object with .signed_url / dict-like
        return getattr(res, "signed_url", None) or getattr(res, "signedURL", None)
    except Exception as exc:
        logger.warning("signed_vault_url failed: {}", exc)
        return None
