"""Health endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from api.schemas import HealthResponse

router = APIRouter(tags=["health"])
START = time.time()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    components = {
        "api": "online",
        "orchestrator": "online"
        if getattr(request.app.state, "agent", None)
        else "offline",
        "redis": getattr(request.app.state, "redis_status", "unknown"),
        "db": getattr(request.app.state, "db_status", "unknown"),
    }
    ok = components["api"] == "online" and components["orchestrator"] == "online"
    return HealthResponse(
        status="ok" if ok else "degraded",
        uptime_seconds=round(time.time() - START, 2),
        components=components,
    )
