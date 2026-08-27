"""Report MCP server — wraps report get/create helpers."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


def tool_get_report(report_id: str) -> dict[str, Any]:
    from services.report_service import get_report

    rec = get_report(UUID(report_id))
    if rec is None:
        return {"ok": False, "error": "not_found"}
    return {
        "ok": True,
        "report_id": str(rec.id),
        "report_type": rec.report_type,
        "status": rec.status,
        "category": rec.category,
        "title": rec.title,
        "latitude": rec.latitude,
        "longitude": rec.longitude,
    }


def tool_create_report(
    *,
    auth_user_id: str,
    report_type: str,
    email: Optional[str] = None,
    category: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    location_label: Optional[str] = None,
) -> dict[str, Any]:
    from services.report_service import create_report

    rec = create_report(
        auth_user_id=auth_user_id,
        email=email,
        report_type=report_type,
        category=category,
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        location_label=location_label,
    )
    return {
        "ok": True,
        "report_id": str(rec.id),
        "status": rec.status,
        "latitude": rec.latitude,
        "longitude": rec.longitude,
    }


def main() -> None:
    print("verifind report MCP — tools: get_report, create_report (stdio wiring later)")


if __name__ == "__main__":
    main()
