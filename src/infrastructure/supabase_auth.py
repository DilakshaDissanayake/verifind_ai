"""Supabase Auth client helpers.

GoTrue calls from Docker often exceed httpx's default 5s read timeout
(Cloudflare edge / auth/v1 can take 6–15s). Use a longer timeout for Auth.
"""

from __future__ import annotations

import httpx
from supabase import Client, create_client

from infrastructure.config import get_settings

# Auth token / signup / recovery can be slow through Cloudflare from containers.
_AUTH_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def get_supabase_auth_client() -> Client:
    """Anon-key client with Auth HTTP timeout suitable for Docker → Supabase."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("Supabase Auth is not configured")
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    old = client.auth._http_client
    client.auth._http_client = httpx.Client(
        base_url=str(old.base_url) if old.base_url else None,
        headers=dict(old.headers),
        timeout=_AUTH_TIMEOUT,
        follow_redirects=True,
    )
    return client
