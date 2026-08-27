"""Health endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from api.schemas import HealthResponse

router = APIRouter(tags=["health"])
START = time.time()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    resilience: dict = {}
    try:
        from infrastructure.llm.llm_provider import resilience_status

        resilience = resilience_status()
    except Exception:
        resilience = {"error": "unavailable"}

    breakers = resilience.get("breakers") or {}
    any_open = any(
        isinstance(v, dict) and v.get("state") == "open" for v in breakers.values()
    )

    components = {
        "api": "online",
        "orchestrator": "online"
        if getattr(request.app.state, "agent", None)
        else "offline",
        "redis": getattr(request.app.state, "redis_status", "unknown"),
        "db": getattr(request.app.state, "db_status", "unknown"),
        "circuit_breakers": breakers,
        "fallback_chains": resilience.get("fallback_chains") or {},
        "ai_resilience": "degraded" if any_open else "closed",
    }
    ok = components["api"] == "online" and components["orchestrator"] == "online"
    status = "ok" if ok and not any_open else ("degraded" if ok else "degraded")
    return HealthResponse(
        status=status,
        uptime_seconds=round(time.time() - START, 2),
        components=components,
    )
