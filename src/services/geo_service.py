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


@dataclass
class NearbyUser:
    user_id: UUID
    distance_m: float


def merge_nearby_user_hits(
    hits: list[tuple[UUID, float]],
    *,
    limit: int = 200,
) -> list[NearbyUser]:
    """Keep the closest distance per user, then cap the fan-out."""
    best: dict[UUID, float] = {}
    for uid, dist in hits:
        prev = best.get(uid)
        if prev is None or dist < prev:
            best[uid] = dist
    ordered = sorted(best.items(), key=lambda item: item[1])[:limit]
    return [NearbyUser(user_id=uid, distance_m=dist) for uid, dist in ordered]


def nearby_users_to_notify(
    lat: float,
    lon: float,
    *,
    exclude_user_id: UUID,
    radius_m: int = GEO_RADIUS_M,
    location_max_age_hours: int = 24,
    limit: int = 200,
) -> list[NearbyUser]:
    """Users within radius_m of a new post (fresh last_location ∪ active reports)."""
    session = get_session()
    hits: list[tuple[UUID, float]] = []
    try:
        has_last_loc = _column_exists(session, "users", "last_location")
        has_last_at = _column_exists(session, "users", "last_location_at")
        if has_last_loc:
            age_sql = (
                "AND last_location_at > now() - make_interval(hours => :age_h)"
                if has_last_at
                else ""
            )
            rows = session.execute(
                text(
                    f"""
                    SELECT id AS user_id,
                           ST_Distance(
                               last_location,
                               ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                           ) AS dist_m
                    FROM users
                    WHERE last_location IS NOT NULL
                      AND COALESCE(is_active, true) = true
                      AND id <> CAST(:exclude AS uuid)
                      AND ST_DWithin(
                            last_location,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            :radius_m
                          )
                      {age_sql}
                    """
                ),
                {
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "exclude": str(exclude_user_id),
                    "age_h": location_max_age_hours,
                },
            ).mappings().all()
            hits.extend((row["user_id"], float(row["dist_m"])) for row in rows)

        rows = session.execute(
            text(
                """
                SELECT r.user_id,
                       MIN(
                           ST_Distance(
                               r.location,
                               ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                           )
                       ) AS dist_m
                FROM reports r
                WHERE r.location IS NOT NULL
                  AND r.status IN ('pending', 'processing', 'active')
                  AND r.user_id <> CAST(:exclude AS uuid)
                  AND ST_DWithin(
                        r.location,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                        :radius_m
                      )
                GROUP BY r.user_id
                """
            ),
            {
                "lat": lat,
                "lon": lon,
                "radius_m": radius_m,
                "exclude": str(exclude_user_id),
            },
        ).mappings().all()
        hits.extend((row["user_id"], float(row["dist_m"])) for row in rows)
    finally:
        session.close()

    return merge_nearby_user_hits(hits, limit=limit)


def _column_exists(session, table: str, column: str) -> bool:
    row = session.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :t
              AND column_name = :c
            LIMIT 1
            """
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None
