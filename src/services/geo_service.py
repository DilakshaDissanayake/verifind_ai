"""GPS fuzz + PostGIS nearby queries."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text

from infrastructure.config import GEO_RADIUS_M, GPS_FUZZ_METERS
from infrastructure.db.sql_client import get_session

# Earth radius (WGS84 mean) for offset math
_EARTH_RADIUS_M = 6_371_000.0


def fuzz_coordinates(
    lat: float,
    lon: float,
    meters: int = GPS_FUZZ_METERS,
    *,
    rng: Optional[random.Random] = None,
) -> tuple[float, float]:
    """Offset a point by a random distance in [0, meters] (client + server defense)."""
    if meters <= 0:
        return lat, lon
    r = rng or random
    # Uniform in disk: radius ~ sqrt(U) * R
    distance = meters * math.sqrt(r.random())
    bearing = r.random() * 2 * math.pi
    lat_rad = math.radians(lat)
    d_lat = (distance * math.cos(bearing)) / _EARTH_RADIUS_M
    d_lon = (distance * math.sin(bearing)) / (
        _EARTH_RADIUS_M * max(math.cos(lat_rad), 1e-6)
    )
    new_lat = lat + math.degrees(d_lat)
    new_lon = lon + math.degrees(d_lon)
    new_lat = max(-90.0, min(90.0, new_lat))
    new_lon = ((new_lon + 180.0) % 360.0) - 180.0
    return new_lat, new_lon


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters (unit tests / no-DB fallback)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class NearbyHit:
    id: UUID
    report_type: str
    category: Optional[str]
    title: Optional[str]
    status: str
    latitude: Optional[float]
    longitude: Optional[float]
    distance_m: float
    location_label: Optional[str] = None


def nearby_reports(
    lat: float,
    lon: float,
    *,
    radius_m: int = GEO_RADIUS_M,
    report_type: Optional[str] = None,
    exclude_id: Optional[UUID] = None,
    limit: int = 50,
) -> list[NearbyHit]:
    """PostGIS ST_DWithin ≤ radius_m (default 5 km)."""
    sql = """
        SELECT
            id,
            report_type,
            category,
            title,
            status,
            location_label,
            ST_Y(location::geometry) AS lat,
            ST_X(location::geometry) AS lon,
            ST_Distance(
                location,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) AS dist_m
        FROM reports
        WHERE location IS NOT NULL
          AND status IN ('pending', 'processing', 'active')
          AND ST_DWithin(
                location,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
              )
          AND (:report_type IS NULL OR report_type = :report_type)
          AND (:exclude_id IS NULL OR id <> :exclude_id)
        ORDER BY dist_m ASC
        LIMIT :limit
    """
    session = get_session()
    try:
        rows = session.execute(
            text(sql),
            {
                "lat": lat,
                "lon": lon,
                "radius_m": radius_m,
                "report_type": report_type,
                "exclude_id": str(exclude_id) if exclude_id else None,
                "limit": limit,
            },
        ).mappings().all()
        return [
            NearbyHit(
                id=row["id"],
                report_type=row["report_type"],
                category=row["category"],
                title=row["title"],
                status=row["status"],
                latitude=row["lat"],
                longitude=row["lon"],
                distance_m=float(row["dist_m"]),
                location_label=row["location_label"],
            )
            for row in rows
        ]
    finally:
        session.close()


def row_to_dict(hit: NearbyHit) -> dict[str, Any]:
    return {
        "id": hit.id,
        "report_type": hit.report_type,
        "category": hit.category,
        "title": hit.title,
        "status": hit.status,
        "latitude": hit.latitude,
        "longitude": hit.longitude,
        "distance_m": hit.distance_m,
        "location_label": hit.location_label,
    }
