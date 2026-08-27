"""Auth dependencies — Supabase JWT (legacy HS256 secret or JWKS) / AUTH_DEV_BYPASS."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from infrastructure.config import get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: Optional[str] = None
    role: str = "user"


@lru_cache(maxsize=4)
def _jwks_client(supabase_url: str):
    """Supabase asymmetric / rotated signing keys (docs: Auth → Signing keys)."""
    import jwt

    base = supabase_url.rstrip("/")
    return jwt.PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json", cache_keys=True)


def _decode_supabase_jwt(token: str, *, secret: str, supabase_url: str) -> dict[str, Any]:
    import jwt

    algorithms_sym = ["HS256"]
    algorithms_asym = ["ES256", "RS256"]
    last_err: Exception | None = None

    # 1) Legacy shared JWT secret (Settings → JWT Keys → Legacy JWT secret)
    if secret and secret not in ("replace-me", "your-jwt-secret"):
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=algorithms_sym,
                audience="authenticated",
                leeway=60,
            )
        except jwt.InvalidAudienceError:
            return jwt.decode(
                token,
                secret,
                algorithms=algorithms_sym,
                options={"verify_aud": False},
                leeway=60,
            )
        except Exception as exc:
            last_err = exc
            logger.debug("HS256 JWT decode failed, trying JWKS: {}", exc)

    # 2) New signing keys via JWKS
    # https://supabase.com/docs/guides/auth/signing-keys
    if supabase_url:
        try:
            client = _jwks_client(supabase_url)
            signing_key = client.get_signing_key_from_jwt(token)
            try:
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=algorithms_asym + algorithms_sym,
                    audience="authenticated",
                    leeway=60,
                )
            except jwt.InvalidAudienceError:
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=algorithms_asym + algorithms_sym,
                    options={"verify_aud": False},
                    leeway=60,
                )
        except Exception as exc:
            last_err = exc
            logger.debug("JWKS JWT decode failed: {}", exc)

    raise last_err or RuntimeError(
        "No SUPABASE_JWT_SECRET and JWKS verification failed — "
        "see Dashboard → Project Settings → JWT Keys "
        "(https://supabase.com/docs/guides/auth/signing-keys)"
    )


def verify_token(token: str) -> CurrentUser:
    """Synchronous token verify — used by WebSocket endpoints."""
    settings = get_settings()
    if settings.auth_dev_bypass:
        return CurrentUser(
            id=settings.auth_dev_user_id,
            email=settings.auth_dev_email,
            role=settings.auth_dev_role or "user",
        )
    try:
        payload = _decode_supabase_jwt(
            token,
            secret=(settings.supabase_jwt_secret or "").strip(),
            supabase_url=(settings.supabase_url or "").strip(),
        )
        sub = payload.get("sub")
        if not sub:
            raise ValueError("Invalid token (no sub)")
        return CurrentUser(
            id=str(sub),
            email=payload.get("email"),
            role=str(payload.get("role") or "user"),
        )
    except Exception as exc:
        raise PermissionError(f"Token validation failed: {exc}") from exc


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> CurrentUser:
    settings = get_settings()
    if settings.auth_dev_bypass:
        return CurrentUser(
            id=settings.auth_dev_user_id,
            email=settings.auth_dev_email,
            role=settings.auth_dev_role or "user",
        )
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        payload = _decode_supabase_jwt(
            credentials.credentials,
            secret=(settings.supabase_jwt_secret or "").strip(),
            supabase_url=(settings.supabase_url or "").strip(),
        )
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token (no sub)")
        # Prefer app users.role; JWT app_metadata.role is a fallback
        role = str(
            (payload.get("app_metadata") or {}).get("role")
            or payload.get("role")
            or "user"
        )
        return CurrentUser(
            id=str(sub),
            email=payload.get("email"),
            role=role,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("JWT validation failed: {}", exc)
        raise HTTPException(
            status_code=401,
            detail=(
                "Token validation failed. For current Supabase UI open "
                "Project Settings → JWT Keys (legacy JWT secret) or rely on "
                "JWKS at /auth/v1/.well-known/jwks.json. "
                f"({exc})"
            ),
        ) from exc


async def require_admin(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Admin REVIEW APIs — vault side-by-side is never public."""
    if user.role == "admin":
        return user

    # Resolve app users.role (source of truth for production)
    try:
        from uuid import UUID

        from services.admin_service import get_user_role
        from services.user_service import ensure_app_user

        app_uid = ensure_app_user(auth_user_id=user.id, email=user.email)
        db_role = get_user_role(UUID(str(app_uid)))
        if db_role == "admin":
            user.role = "admin"
            return user
    except Exception as exc:
        logger.debug("require_admin DB role lookup failed: {}", exc)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin role required",
    )
