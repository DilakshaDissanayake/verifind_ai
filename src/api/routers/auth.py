"""Auth routes — login + signup (Supabase Auth)."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from api.deps import CurrentUser, get_current_user
from api.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
)
from infrastructure.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(body: RegisterRequest) -> RegisterResponse:
    """Public signup — creates Supabase auth user + app `users` profile row."""
    settings = get_settings()
    email = str(body.email).strip().lower()
    display_name = (body.display_name or "").strip() or None
    emergency_contact = (body.emergency_contact or "").strip()
    if not settings.auth_dev_bypass and not emergency_contact:
        raise HTTPException(status_code=422, detail="Emergency contact number is required")

    if settings.auth_dev_bypass:
        logger.warning("AUTH_DEV_BYPASS register for {}", email)
        try:
            from services.user_service import ensure_app_user

            ensure_app_user(
                auth_user_id=settings.auth_dev_user_id,
                email=email,
                emergency_contact=emergency_contact,
            )
        except Exception as exc:
            logger.warning("ensure_app_user skipped in bypass: {}", exc)
        return RegisterResponse(
            user_id=settings.auth_dev_user_id,
            email=email,
            access_token="dev-bypass-token",
            mode="dev_bypass",
            message="Account ready (dev bypass)",
            requires_email_confirmation=False,
        )

    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=503,
            detail="Signup unavailable — Supabase Auth not configured",
        )

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        meta = {"display_name": display_name, "emergency_contact": emergency_contact}
        result = client.auth.sign_up(
            {
                "email": email,
                "password": body.password,
                "options": {"data": meta},
            }
        )
        if not result.user:
            raise HTTPException(status_code=400, detail="Signup failed")

        user_id = str(result.user.id)
        try:
            from services.user_service import ensure_app_user

            ensure_app_user(
                auth_user_id=user_id,
                email=email,
                emergency_contact=emergency_contact,
            )
            if display_name:
                from sqlalchemy import text

                from infrastructure.db.sql_client import get_session

                session = get_session()
                try:
                    session.execute(
                        text(
                            "UPDATE users SET display_name = :dn, updated_at = now() "
                            "WHERE auth_user_id = CAST(:aid AS uuid) "
                            "OR id = CAST(:aid AS uuid)"
                        ),
                        {"dn": display_name, "aid": user_id},
                    )
                    session.execute(
                        text(
                            "UPDATE users SET emergency_contact = :contact, updated_at = now() "
                            "WHERE auth_user_id = CAST(:aid AS uuid) OR id = CAST(:aid AS uuid)"
                        ),
                        {"contact": emergency_contact, "aid": user_id},
                    )
                    session.commit()
                except Exception:
                    session.rollback()
                finally:
                    session.close()
        except Exception as exc:
            logger.warning("App user profile upsert skipped: {}", exc)

        session_token = (
            result.session.access_token if result.session else None
        )
        needs_confirm = session_token is None
        return RegisterResponse(
            user_id=user_id,
            email=result.user.email or email,
            access_token=session_token,
            mode="supabase",
            message=(
                "Check your email to confirm the account"
                if needs_confirm
                else "Account created"
            ),
            requires_email_confirmation=needs_confirm,
        )
    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "already" in msg or "registered" in msg or "exists" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            ) from exc
        logger.error("register failed: {}", exc)
        raise HTTPException(
            status_code=400, detail=f"Signup failed: {exc}"
        ) from exc


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    settings = get_settings()
    # AUTH_DEV_BYPASS always wins — local smoke without a real Supabase user.
    if settings.auth_dev_bypass:
        logger.warning("AUTH_DEV_BYPASS for {}", body.email)
        return LoginResponse(
            access_token="dev-bypass-token",
            user_id=settings.auth_dev_user_id,
            email=body.email,
            role=settings.auth_dev_role or "admin",
            mode="dev_bypass",
        )
    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        result = client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
        if not result.session or not result.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not getattr(result.user, "email_confirmed_at", None):
            raise HTTPException(
                status_code=403,
                detail="Email not verified. Check your inbox or request a new verification email.",
            )
        user_id = str(result.user.id)
        app_role = "user"
        try:
            from services.admin_service import get_user_role
            from services.user_service import ensure_app_user
            from uuid import UUID

            app_uid = ensure_app_user(
                auth_user_id=user_id,
                email=result.user.email or body.email,
            )
            db_role = get_user_role(UUID(str(app_uid)))
            if db_role:
                app_role = db_role
        except Exception as exc:
            logger.warning("ensure_app_user on login skipped: {}", exc)
        return LoginResponse(
            access_token=result.session.access_token,
            user_id=user_id,
            email=result.user.email or body.email,
            role=app_role,
            mode="supabase",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("login failed: {}", exc)
        raise HTTPException(status_code=401, detail="Login failed") from exc


@router.post("/resend-verification", response_model=ResendVerificationResponse)
async def resend_verification(body: ResendVerificationRequest) -> ResendVerificationResponse:
    """Send a fresh confirmation link without exposing account existence."""
    settings = get_settings()
    if settings.auth_dev_bypass:
        return ResendVerificationResponse(message="Verification is bypassed in development")
    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        client.auth.resend({"type": "signup", "email": str(body.email).strip().lower()})
    except Exception as exc:
        logger.warning("verification resend failed: {}", exc)
    return ResendVerificationResponse()


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    from services.user_service import ensure_app_user, get_profile_summary

    app_uid = await asyncio.to_thread(
        ensure_app_user, auth_user_id=user.id, email=user.email
    )
    summary = await asyncio.to_thread(get_profile_summary, UUID(str(app_uid)))
    return MeResponse(
        user_id=str(app_uid),
        email=summary.get("email") or user.email,
        display_name=summary.get("display_name"),
        role=summary.get("role") or user.role,
        lost_count=int(summary.get("lost_count") or 0),
        found_count=int(summary.get("found_count") or 0),
        active_chats=int(summary.get("active_chats") or 0),
    )
