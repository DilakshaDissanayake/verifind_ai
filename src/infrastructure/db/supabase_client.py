"""Supabase helpers."""
from __future__ import annotations

import os
from functools import lru_cache

from loguru import logger

from infrastructure.config import STORAGE_PUBLIC_BUCKET, STORAGE_VAULT_BUCKET


@lru_cache(maxsize=1)
def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Supabase env missing")
    from supabase import create_client
    return create_client(url, key)


def ensure_buckets() -> dict:
    try:
        client = get_supabase()
        existing = {b.name for b in client.storage.list_buckets()}
        created = []
        for name, public in ((STORAGE_PUBLIC_BUCKET, True), (STORAGE_VAULT_BUCKET, False)):
            if name not in existing:
                client.storage.create_bucket(name, options={"public": public})
                created.append(name)
        return {"ok": True, "created": created}
    except Exception as exc:
        logger.warning("ensure_buckets skipped: {}", exc)
        return {"ok": False, "error": str(exc)}
