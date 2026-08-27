"""Match service — Sprint 4.

Finds candidate LOST/FOUND pairs via PostGIS ST_DWithin, computes multimodal
fusion scores, persists to matches table, returns ranked results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import text

from infrastructure.config import FRAUD, FUSION_WEIGHTS, GEO_RADIUS_M, MATCH_HIGH, MATCH_MEDIUM
from infrastructure.db.sql_client import get_session
from pipelines.fusion import (
    category_match_score,
    compute_fusion_score,
    cosine_similarity,
    geo_score_from_distance,
)


@dataclass
class MatchRecord:
    id: UUID
    report_a_id: UUID
    report_b_id: UUID
    score: float
    band: str
    vision_score: float
    text_score: float
    geo_score: float
    category_score: float
    distance_m: Optional[float]
    notified: bool
    created_at: Optional[datetime]
    claim_status: Optional[str] = None
    verification_decision: Optional[str] = None
    chat_room_id: Optional[UUID] = None


@dataclass
class CandidatePair:
    """Raw spatial candidate before fusion scoring."""
    report_id: UUID
    report_type: str
    category: Optional[str]
    distance_m: float
    embedding: Optional[list[float]]
    ai_category: Optional[str]
    vision_score_hint: Optional[float]


def find_candidates(
    report_id: UUID,
    *,
    radius_m: int = GEO_RADIUS_M,
    limit: int = 20,
) -> list[CandidatePair]:
    """Spatial candidates for a report using ST_DWithin.

    Returns opposite-type reports within radius_m that are active/pending.
    """
    session = get_session()
    try:
        # Get source report
        src = session.execute(
            text(
                """
                SELECT r.report_type, r.category, r.status,
                       r.text_embedding::text AS embedding_str,
                       r.location
                FROM reports r
                WHERE r.id = :id AND r.location IS NOT NULL
                  AND r.status NOT IN ('matched', 'closed', 'flagged')
                """
            ),
            {"id": str(report_id)},
        ).mappings().first()

        if src is None:
            logger.warning("find_candidates: report {} not found or has no location", report_id)
            return []

        # Opposite type
        opp_type = "FOUND" if src["report_type"] == "LOST" else "LOST"

        rows = session.execute(
            text(
                """
                SELECT
                    r.id,
                    r.report_type,
                    r.category,
                    ST_Distance(r.location, src.location) AS distance_m,
                    r.text_embedding::text AS embedding_str,
                    t.category AS ai_category
                FROM reports r
                CROSS JOIN (
                    SELECT location FROM reports WHERE id = :src_id
                ) src
                LEFT JOIN LATERAL (
                    SELECT category FROM ai_tags
                    WHERE report_id = r.id
                    ORDER BY created_at DESC LIMIT 1
                ) t ON TRUE
                WHERE
                    r.id <> :src_id
                    AND r.report_type = :opp_type
                    AND r.status IN ('active', 'pending')
                    AND r.location IS NOT NULL
                    AND ST_DWithin(r.location, src.location, :radius_m)
                ORDER BY distance_m ASC
                LIMIT :limit
                """
            ),
            {
                "src_id": str(report_id),
                "opp_type": opp_type,
                "radius_m": radius_m,
                "limit": limit,
            },
        ).mappings().all()

    finally:
        session.close()

    def _parse_embedding(emb_str: Any) -> Optional[list[float]]:
        if not emb_str:
            return None
        try:
            s = str(emb_str).strip()
            if s.startswith("["):
                return [float(x) for x in s[1:-1].split(",")]
        except Exception:
            pass
        return None

    results: list[CandidatePair] = []
    for row in rows:
        results.append(
            CandidatePair(
                report_id=row["id"],
                report_type=row["report_type"],
                category=row["category"],
                distance_m=float(row["distance_m"] or 0),
                embedding=_parse_embedding(row["embedding_str"]),
                ai_category=row["ai_category"],
                vision_score_hint=None,
            )
        )
    return results


def _get_report_embedding(report_id: UUID) -> Optional[list[float]]:
    session = get_session()
    try:
        row = session.execute(
            text("SELECT text_embedding::text AS e FROM reports WHERE id = :id"),
            {"id": str(report_id)},
        ).mappings().first()
    finally:
        session.close()

    if row is None or not row["e"]:
        return None
    try:
        s = str(row["e"]).strip()
        if s.startswith("["):
            return [float(x) for x in s[1:-1].split(",")]
    except Exception:
        pass
    return None


def _get_report_category(report_id: UUID) -> Optional[str]:
    session = get_session()
    try:
        row = session.execute(
            text("SELECT category FROM reports WHERE id = :id"),
            {"id": str(report_id)},
        ).mappings().first()
    finally:
        session.close()
    return row["category"] if row else None


def _fetch_vision_features(report_id: UUID) -> dict[str, Any]:
    """AI tags + primary image pHash for vision similarity."""
    session = get_session()
    try:
        tag = session.execute(
            text(
                """
                SELECT brand, colors, category, attributes
                FROM ai_tags
                WHERE report_id = :rid
                ORDER BY
                    CASE WHEN COALESCE(model, '') <> '' THEN 0 ELSE 1 END,
                    created_at DESC
                LIMIT 1
                """
            ),
            {"rid": str(report_id)},
        ).mappings().first()
        img = session.execute(
            text(
                """
                SELECT phash FROM report_images
                WHERE report_id = :rid AND is_primary = TRUE
                LIMIT 1
                """
            ),
            {"rid": str(report_id)},
        ).mappings().first()
    finally:
        session.close()

    colors = list(tag["colors"] or []) if tag else []
    attrs = dict(tag["attributes"] or {}) if tag else {}
    return {
        "brand": (tag["brand"] if tag else None),
        "colors": [str(c).lower().strip() for c in colors if c],
        "category": (tag["category"] if tag else None),
        "attributes": attrs,
        "phash": int(img["phash"]) if img and img.get("phash") is not None else None,
    }


def vision_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Image/tag similarity in [0,1]: brand + colors + attrs + pHash.

    Same (or near-dup) photos and matching AI tags → high vision score so
    fusion can reach HIGH (≥0.80) when geo/text also agree.
    """
    scores: list[float] = []
    weights: list[float] = []

    # Brand (0.25)
    ba = (a.get("brand") or "").strip().lower()
    bb = (b.get("brand") or "").strip().lower()
    if ba and bb:
        scores.append(1.0 if ba == bb else (0.5 if ba in bb or bb in ba else 0.0))
        weights.append(0.25)

    # Colors Jaccard (0.25)
    ca = set(a.get("colors") or [])
    cb = set(b.get("colors") or [])
    if ca or cb:
        union = ca | cb
        inter = ca & cb
        scores.append(len(inter) / len(union) if union else 0.0)
        weights.append(0.25)

    # Attribute key overlap (0.20)
    aa = {str(k).lower(): str(v).lower() for k, v in (a.get("attributes") or {}).items()}
    ab = {str(k).lower(): str(v).lower() for k, v in (b.get("attributes") or {}).items()}
    if aa or ab:
        keys = set(aa) | set(ab)
        if keys:
            hits = sum(1 for k in keys if k in aa and k in ab and aa[k] == ab[k])
            scores.append(hits / len(keys))
            weights.append(0.20)

    # Category from vision tags (0.10)
    cata = (a.get("category") or "").strip().lower()
    catb = (b.get("category") or "").strip().lower()
    if cata and catb:
        scores.append(1.0 if cata == catb else 0.0)
        weights.append(0.10)

    # pHash Hamming (0.20) — ≤5 near-dup → 1.0, decays to 0 at 20
    pa, pb = a.get("phash"), b.get("phash")
    if pa is not None and pb is not None:
        dist = bin(int(pa) ^ int(pb)).count("1")
        if dist <= 5:
            scores.append(1.0)
        elif dist >= 20:
            scores.append(0.0)
        else:
            scores.append(round(1.0 - (dist - 5) / 15.0, 4))
        weights.append(0.20)

    if not scores or not weights:
        return 0.0
    total_w = sum(weights)
    return round(sum(s * w for s, w in zip(scores, weights)) / total_w, 4)


def compute_match_scores(
    source_id: UUID,
    candidates: list[CandidatePair],
    *,
    source_category: Optional[str] = None,
    source_embedding: Optional[list[float]] = None,
) -> list[dict[str, Any]]:
    """Compute fusion scores for each candidate.

    Returns sorted list of dicts with score, band, component scores.
    """
    results = []
    src_emb = source_embedding
    src_cat = source_category
    src_vision = _fetch_vision_features(source_id)

    for cand in candidates:
        geo_s = geo_score_from_distance(cand.distance_m, float(GEO_RADIUS_M))

        text_s = 0.0
        if src_emb and cand.embedding:
            text_s = cosine_similarity(src_emb, cand.embedding)

        cat_s = category_match_score(src_cat, cand.category or cand.ai_category)

        cand_vision = _fetch_vision_features(cand.report_id)
        vis_s = float(cand.vision_score_hint) if cand.vision_score_hint is not None else vision_similarity(
            src_vision, cand_vision
        )

        fusion = compute_fusion_score(
            vision_score=vis_s,
            text_score=text_s,
            geo_score=geo_s,
            category_score=cat_s,
        )

        results.append(
            {
                "source_id": str(source_id),
                "candidate_id": str(cand.report_id),
                "score": fusion["score"],
                "band": fusion["band"],
                "vision_score": vis_s,
                "text_score": text_s,
                "geo_score": geo_s,
                "category_score": cat_s,
                "distance_m": cand.distance_m,
                "weights": fusion["weights_used"],
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def score_pair(report_a_id: UUID, report_b_id: UUID) -> dict[str, Any]:
    """Score a specific LOST↔FOUND pair (finder selected a lost post)."""
    from services.geo_service import haversine_m

    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT id, report_type, category,
                       text_embedding::text AS emb,
                       ST_Y(location::geometry) AS lat,
                       ST_X(location::geometry) AS lon
                FROM reports
                WHERE id = :a OR id = :b
                """
            ),
            {"a": str(report_a_id), "b": str(report_b_id)},
        ).mappings().all()
    finally:
        session.close()

    by_id = {str(r["id"]): r for r in rows}
    ra, rb = by_id.get(str(report_a_id)), by_id.get(str(report_b_id))
    if not ra or not rb:
        raise ValueError("One or both reports not found")

    def _emb(s: Any) -> Optional[list[float]]:
        if not s:
            return None
        try:
            t = str(s).strip()
            if t.startswith("["):
                return [float(x) for x in t[1:-1].split(",")]
        except Exception:
            return None
        return None

    dist = 0.0
    if ra.get("lat") is not None and rb.get("lat") is not None:
        try:
            dist = float(
                haversine_m(
                    float(ra["lat"]), float(ra["lon"]),
                    float(rb["lat"]), float(rb["lon"]),
                )
            )
        except Exception:
            dist = 0.0

    cand = CandidatePair(
        report_id=report_b_id,
        report_type=str(rb["report_type"]),
        category=rb.get("category"),
        distance_m=dist,
        embedding=_emb(rb.get("emb")),
        ai_category=None,
        vision_score_hint=None,
    )
    scored = compute_match_scores(
        report_a_id,
        [cand],
        source_category=ra.get("category"),
        source_embedding=_emb(ra.get("emb")),
    )
    return scored[0] if scored else {
        "score": 0.0,
        "band": "LOW",
        "vision_score": 0.0,
        "text_score": 0.0,
        "geo_score": 0.0,
        "category_score": 0.0,
        "distance_m": dist,
    }


def upsert_match(
    *,
    report_a_id: UUID,
    report_b_id: UUID,
    score: float,
    band: str,
    vision_score: float = 0.0,
    text_score: float = 0.0,
    geo_score: float = 0.0,
    category_score: float = 0.0,
    distance_m: Optional[float] = None,
) -> UUID:
    """Insert or update a match row. Returns match id."""
    from uuid import uuid4

    session = get_session()
    try:
        # Canonical order: smaller UUID first so (a,b) == (b,a)
        a, b = sorted([str(report_a_id), str(report_b_id)])
        existing = session.execute(
            text(
                "SELECT id FROM matches WHERE report_a_id = :a AND report_b_id = :b"
            ),
            {"a": a, "b": b},
        ).mappings().first()

        if existing:
            match_id = existing["id"]
            session.execute(
                text(
                    """
                    UPDATE matches SET
                        score = :score, band = :band,
                        vision_score = :vs, text_score = :ts,
                        geo_score = :gs, category_score = :cs,
                        distance_m = :dist, updated_at = now()
                    WHERE id = :id
                    """
                ),
                {
                    "id": str(match_id),
                    "score": score,
                    "band": band,
                    "vs": vision_score,
                    "ts": text_score,
                    "gs": geo_score,
                    "cs": category_score,
                    "dist": distance_m,
                },
            )
        else:
            match_id = uuid4()
            session.execute(
                text(
                    """
                    INSERT INTO matches (
                        id, report_a_id, report_b_id, score, band,
                        vision_score, text_score, geo_score, category_score,
                        distance_m, notified
                    ) VALUES (
                        :id, :a, :b, :score, :band,
                        :vs, :ts, :gs, :cs,
                        :dist, false
                    )
                    """
                ),
                {
                    "id": str(match_id),
                    "a": a,
                    "b": b,
                    "score": score,
                    "band": band,
                    "vs": vision_score,
                    "ts": text_score,
                    "gs": geo_score,
                    "cs": category_score,
                    "dist": distance_m,
                },
            )
        session.commit()
        return UUID(str(match_id))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_matches_for_report(
    report_id: UUID,
    *,
    min_band: str = "LOW",
    limit: int = 20,
) -> list[MatchRecord]:
    """Return matches involving this report, ordered by score desc."""
    band_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    min_score = (
        MATCH_HIGH if min_band == "HIGH"
        else MATCH_MEDIUM if min_band == "MEDIUM"
        else 0.0
    )

    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT m.id, m.report_a_id, m.report_b_id, m.score, m.band,
                       m.vision_score, m.text_score, m.geo_score, m.category_score,
                       m.distance_m, m.notified, m.created_at,
                       ca.status AS claim_status,
                       vs.decision AS verification_decision,
                       cr.id AS chat_room_id
                FROM matches m
                LEFT JOIN LATERAL (
                    SELECT ca2.id, ca2.status
                    FROM claim_attempts ca2
                    WHERE ca2.match_id = m.id
                    ORDER BY
                      CASE ca2.status
                        WHEN 'passed' THEN 0
                        WHEN 'review' THEN 1
                        WHEN 'started' THEN 2
                        WHEN 'blocked' THEN 3
                        ELSE 4
                      END,
                      ca2.created_at DESC
                    LIMIT 1
                ) ca ON TRUE
                LEFT JOIN verification_sessions vs ON vs.claim_attempt_id = ca.id
                LEFT JOIN chat_rooms cr ON cr.match_id = m.id AND cr.is_active = true
                WHERE (m.report_a_id = :rid OR m.report_b_id = :rid)
                  AND m.score >= :min_score
                  AND COALESCE(m.admin_status, 'pending') <> 'rejected'
                ORDER BY m.score DESC
                LIMIT :limit
                """
            ),
            {"rid": str(report_id), "min_score": min_score, "limit": limit},
        ).mappings().all()
    finally:
        session.close()

    return [
        MatchRecord(
            id=row["id"],
            report_a_id=row["report_a_id"],
            report_b_id=row["report_b_id"],
            score=float(row["score"]),
            band=row["band"],
            vision_score=float(row["vision_score"] or 0),
            text_score=float(row["text_score"] or 0),
            geo_score=float(row["geo_score"] or 0),
            category_score=float(row["category_score"] or 0),
            distance_m=float(row["distance_m"]) if row["distance_m"] else None,
            notified=bool(row["notified"]),
            created_at=row["created_at"],
            claim_status=row.get("claim_status"),
            verification_decision=row.get("verification_decision"),
            chat_room_id=UUID(str(row["chat_room_id"])) if row.get("chat_room_id") else None,
        )
        for row in rows
    ]


def mark_match_notified(match_id: UUID) -> None:
    session = get_session()
    try:
        session.execute(
            text("UPDATE matches SET notified = true WHERE id = :id"),
            {"id": str(match_id)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
