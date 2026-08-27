"""Geo MCP server — wraps PostGIS nearby / fuzz helpers."""

from __future__ import annotations

from typing import Any, Optional


def tool_fuzz_coordinates(lat: float, lon: float, meters: int = 500) -> dict[str, float]:
    from services.geo_service import fuzz_coordinates

    f_lat, f_lon = fuzz_coordinates(lat, lon, meters)
    return {"latitude": f_lat, "longitude": f_lon, "fuzz_meters": meters}


def tool_nearby(
    lat: float,
    lon: float,
    radius_m: int = 5000,
    report_type: Optional[str] = None,
) -> dict[str, Any]:
    from services.geo_service import nearby_reports, row_to_dict

    hits = nearby_reports(lat, lon, radius_m=radius_m, report_type=report_type)
    return {"count": len(hits), "items": [row_to_dict(h) for h in hits]}


def main() -> None:
    print("verifind geo MCP — tools: fuzz_coordinates, nearby (stdio wiring later)")


if __name__ == "__main__":
    main()
