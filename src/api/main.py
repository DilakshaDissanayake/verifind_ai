"""FastAPI application — Sprint 6 (Admin + Harden)."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from api.middleware import install_middleware  # noqa: E402
from api.routers import auth as auth_router  # noqa: E402
from api.routers import health as health_router  # noqa: E402
from api.routers import reports as reports_router  # noqa: E402
from api.routers.admin import router as admin_router  # noqa: E402
from api.routers.matches import notifications_router  # noqa: E402
from api.routers.matches import router as matches_router  # noqa: E402
from api.routers.claims import router as claims_router  # noqa: E402
from api.routers.chat import router as chat_router  # noqa: E402
from api.routers.chat import ws_router  # noqa: E402
from infrastructure.config import get_settings  # noqa: E402
from infrastructure.log import setup_logging  # noqa: E402
from infrastructure.observability import flush as flush_langfuse  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting VERIFIND AI API (Sprint 6 — Admin + Harden)...")
    from agents.orchestrator import build_agent

    app.state.agent = build_agent()
    app.state.redis_status = "skipped"
    app.state.db_status = "skipped"

    try:
        from infrastructure.db.sql_client import ping_db

        app.state.db_status = "online" if ping_db() else "offline"
    except Exception as exc:
        logger.warning("DB probe skipped: {}", exc)
        app.state.db_status = "offline"

    try:
        import redis as redis_lib

        client = redis_lib.from_url(get_settings().redis_url, socket_connect_timeout=1)
        client.ping()
        app.state.redis_status = "online"
    except Exception as exc:
        logger.warning("Redis probe skipped: {}", exc)
        app.state.redis_status = "offline"

    yield
    flush_langfuse()
    logger.info("Shutting down VERIFIND AI API...")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VERIFIND AI",
        description="Zero-Fraud Lost & Found Matchmaking API",
        version="0.6.0-sprint6",
        lifespan=lifespan,
    )
    # Flutter web (Chrome) uses http://localhost:<random> — allow via regex.
    # Explicit CORS_ORIGINS still applied for admin SPA / production domains.
    origins = settings.cors_origin_list
    allow_all = origins == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else origins,
        allow_origin_regex=(
            None
            if allow_all
            else r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
        ),
        # credentials + "*" is invalid; disable credentials when allowing all
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_middleware(app)
    app.include_router(health_router.router)
    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(reports_router.router, prefix="/api/v1")
    app.include_router(matches_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(claims_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(ws_router)       # WebSocket: /ws/chat/{room_id}
    return app


app = create_app()
