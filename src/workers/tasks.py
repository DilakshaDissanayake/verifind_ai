"""Arq worker tasks — Sprint 4: AI dual pipeline + match scoring + notifications."""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from loguru import logger

from workers.enqueue import redis_settings_from_env


async def startup(ctx: dict) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    from infrastructure.log import setup_logging

    setup_logging()
    logger.info("Arq worker started (Sprint 4 — AI pipeline + matching + notifications)")


async def shutdown(ctx: dict) -> None:
    logger.info("Arq worker stopped")


async def process_report_ai(ctx: dict, **payload: Any) -> dict[str, Any]:
    """Full Sprint 3 AI pipeline.

    Steps:
      1. Mark report status = 'processing'
      2. Fetch primary image bytes from vault (if available)
      3. Run dual pipeline: vision ∥ text embed (asyncio.gather)
      4. Run metadata pipeline: pHash + HSV histogram
      5. Store ai_tags row in DB
      6. Store text_embedding vector on reports row
      7. Update report_images.phash + hsv_histogram
      8. Mark report status = 'active'
    """
    report_id_str: Optional[str] = payload.get("report_id")
    description: str = payload.get("description") or ""
    title: Optional[str] = payload.get("title")
    category: Optional[str] = payload.get("category")

    logger.info("process_report_ai START report_id={}", report_id_str)

    if not report_id_str:
        logger.warning("process_report_ai: missing report_id in payload")
        return {"status": "error", "reason": "missing report_id"}

    report_id = UUID(str(report_id_str))

    # --- Step 1: mark processing ---
    _safe_set_status(report_id, "processing")

    # --- Step 2: fetch primary image bytes ---
    image_bytes: Optional[bytes] = None
    image_id: Optional[str] = None
    content_type: str = "image/jpeg"

    try:
        image_bytes, image_id, content_type = await _fetch_primary_image(report_id)
    except Exception as exc:
        logger.warning("process_report_ai: image fetch failed for {}: {}", report_id_str, exc)

    # --- Step 3: dual pipeline ---
    try:
        from pipelines.dual_executor import run_dual_pipeline

        dual_result = await run_dual_pipeline(
            report_id=report_id_str,
            image_bytes=image_bytes,
            content_type=content_type,
            title=title,
            description=description,
            category=category,
        )
    except Exception as exc:
        logger.error("process_report_ai: dual pipeline failed for {}: {}", report_id_str, exc)
        _safe_set_status(report_id, "active")  # don't block report on AI failure
        return {"report_id": report_id_str, "status": "pipeline_error", "error": str(exc)}

    vision = dual_result.get("vision", {})
    text_result = dual_result.get("text", {})

    # --- Step 4: metadata pipeline ---
    meta_result: dict[str, Any] = {}
    if image_bytes:
        try:
            from pipelines.metadata_pipeline import run_metadata_pipeline

            meta_result = await run_metadata_pipeline(image_bytes, report_id=report_id_str)
        except Exception as exc:
            logger.warning("process_report_ai: metadata pipeline failed for {}: {}", report_id_str, exc)

    # --- Step 5: store ai_tags (skip stub when no image yet — photo job will overwrite) ---
    vision_source = str(vision.get("_source") or "")
    if vision_source == "no_image":
        logger.info(
            "process_report_ai: skipping stub ai_tags (no_image) report_id={}",
            report_id_str,
        )
    else:
        try:
            _store_ai_tags(
                report_id=report_id,
                brand=vision.get("brand"),
                colors=vision.get("colors") or [],
                ai_category=vision.get("category"),
                attributes=vision.get("attributes") or {},
                mask_boxes=vision.get("mask_boxes") or [],
                model=vision.get("model") or "",
            )
        except Exception as exc:
            logger.warning("process_report_ai: ai_tags store failed for {}: {}", report_id_str, exc)

    # --- Step 6: store text_embedding ---
    embedding: list[float] = text_result.get("embedding") or []
    if embedding and any(v != 0.0 for v in embedding):
        try:
            _store_text_embedding(report_id, embedding)
        except Exception as exc:
            logger.warning("process_report_ai: embedding store failed for {}: {}", report_id_str, exc)

    # --- Step 7: update report_images metadata ---
    if image_id and meta_result:
        try:
            _update_image_metadata(
                image_id=UUID(image_id),
                phash=meta_result.get("phash"),
                hsv_histogram=meta_result.get("hsv_histogram"),
            )
        except Exception as exc:
            logger.warning("process_report_ai: image metadata update failed for {}: {}", image_id, exc)

    # --- Step 8: sanitize image (Sprint 4 — blur mask boxes → public bucket) ---
    san_result: dict[str, Any] = {}
    if image_bytes and image_id:
        mask_boxes = vision.get("mask_boxes") or []
        try:
            from pipelines.sanitization_pipeline import run_sanitization_pipeline

            san_result = await run_sanitization_pipeline(
                image_bytes,
                report_id=report_id_str,
                image_id=image_id,
                mask_boxes=mask_boxes,
                content_type=content_type,
            )
            if san_result.get("public_path"):
                _update_image_public_path(UUID(image_id), san_result["public_path"])
                logger.info(
                    "process_report_ai: sanitized image {} regions_blurred={}",
                    report_id_str,
                    san_result.get("regions_blurred", 0),
                )
        except Exception as exc:
            logger.warning("process_report_ai: sanitization failed for {}: {}", report_id_str, exc)

    # --- Step 8b: near-dup pHash flag (Sprint 4 — Hamming ≤ 5 = flag report) ---
    phash_val = meta_result.get("phash")
    near_dup = False
    if phash_val is not None:
        try:
            near_dup = _check_near_dup(report_id, phash_val)
            if near_dup:
                logger.warning(
                    "process_report_ai: near-duplicate image detected report_id={} phash={}",
                    report_id_str,
                    phash_val,
                )
                _safe_set_status(report_id, "flagged")
        except Exception as exc:
            logger.warning("process_report_ai: near-dup check failed for {}: {}", report_id_str, exc)

    # --- Step 9: mark active (unless already flagged as near-dup) ---
    if not near_dup:
        _safe_set_status(report_id, "active")

    # --- Step 10: enqueue compute_matches (Sprint 4) ---
    if not near_dup:
        try:
            from workers.enqueue import enqueue_compute_matches

            await enqueue_compute_matches(
                report_id=report_id_str,
                user_id=str(payload.get("user_id") or ""),
                report_type=str(payload.get("report_type") or ""),
                matched_to_report_id=(
                    str(payload["matched_to_report_id"])
                    if payload.get("matched_to_report_id")
                    else None
                ),
                redis=ctx.get("redis"),
            )
        except Exception as exc:
            logger.warning(
                "process_report_ai: enqueue compute_matches failed for {}: {}",
                report_id_str,
                exc,
            )

    logger.info(
        "process_report_ai COMPLETE report_id={} category={} dims={} within_budget={} near_dup={}",
        report_id_str,
        vision.get("category"),
        text_result.get("dims"),
        dual_result.get("within_budget"),
        near_dup,
    )

    return {
        "report_id": report_id_str,
        "status": "complete",
        "category": vision.get("category"),
        "embedding_dims": text_result.get("dims"),
        "total_latency_s": dual_result.get("total_latency_s"),
        "within_budget": dual_result.get("within_budget"),
        "mask_regions": len(vision.get("mask_boxes") or []),
        "has_phash": phash_val is not None,
        "near_dup": near_dup,
        "public_path": san_result.get("public_path"),
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _safe_set_status(report_id: UUID, status_val: str) -> None:
    try:
        from services.report_service import set_report_status

        set_report_status(report_id, status_val)
    except Exception as exc:
        logger.warning("set_report_status {} failed: {}", status_val, exc)


def _store_ai_tags(
    *,
    report_id: UUID,
    brand: Optional[str],
    colors: list[str],
    ai_category: Optional[str],
    attributes: dict[str, Any],
    mask_boxes: list[dict[str, Any]],
    model: str,
) -> None:
    from sqlalchemy import text

    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        # One canonical tag row per report (replace race stubs / prior runs)
        session.execute(
            text("DELETE FROM ai_tags WHERE report_id = :report_id"),
            {"report_id": str(report_id)},
        )
        session.execute(
            text(
                """
                INSERT INTO ai_tags (report_id, brand, colors, category, attributes, mask_boxes, model)
                VALUES (
                    :report_id,
                    :brand,
                    :colors,
                    :category,
                    CAST(:attributes AS jsonb),
                    CAST(:mask_boxes AS jsonb),
                    :model
                )
                """
            ),
            {
                "report_id": str(report_id),
                "brand": brand,
                "colors": colors,
                "category": ai_category,
                "attributes": json.dumps(attributes),
                "mask_boxes": json.dumps(mask_boxes),
                "model": model,
            },
        )
        session.commit()
        logger.info("ai_tags stored for report_id={}", report_id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _store_text_embedding(report_id: UUID, embedding: list[float]) -> None:
    from sqlalchemy import text

    from infrastructure.db.sql_client import get_session

    # pgvector accepts the canonical "[v1,v2,...]" literal via CAST — avoid
    # ":emb::vector" which SQLAlchemy/psycopg2 leave unexpanded and fail.
    vector_str = "[" + ",".join(str(float(v)) for v in embedding) + "]"
    session = get_session()
    try:
        session.execute(
            text(
                "UPDATE reports SET text_embedding = CAST(:emb AS vector), "
                "updated_at = now() WHERE id = :id"
            ),
            {"emb": vector_str, "id": str(report_id)},
        )
        session.commit()
        logger.info("text_embedding stored for report_id={}", report_id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _update_image_metadata(
    *,
    image_id: UUID,
    phash: Optional[int],
    hsv_histogram: Optional[dict[str, Any]],
) -> None:
    from sqlalchemy import text

    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE report_images
                SET phash = :phash,
                    hsv_histogram = CAST(:hsv AS jsonb)
                WHERE id = :id
                """
            ),
            {
                "phash": phash,
                "hsv": json.dumps(hsv_histogram) if hsv_histogram else "null",
                "id": str(image_id),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _update_image_public_path(image_id: UUID, public_path: str) -> None:
    from sqlalchemy import text

    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        session.execute(
            text("UPDATE report_images SET public_path = :path WHERE id = :id"),
            {"path": public_path, "id": str(image_id)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def _fetch_primary_image(report_id: UUID) -> tuple[Optional[bytes], Optional[str], str]:
    """Fetch primary image bytes from Supabase vault.

    Returns (bytes, image_id_str, content_type) or (None, None, 'image/jpeg') on failure.
    """
    from sqlalchemy import text

    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT ri.id, ri.content_type, iv.vault_path
                FROM report_images ri
                JOIN image_vaults iv ON iv.report_image_id = ri.id
                WHERE ri.report_id = :rid AND ri.is_primary = TRUE
                LIMIT 1
                """
            ),
            {"rid": str(report_id)},
        ).mappings().first()
    finally:
        session.close()

    if row is None:
        return None, None, "image/jpeg"

    image_id = str(row["id"])
    content_type = str(row["content_type"] or "image/jpeg")
    vault_path = str(row["vault_path"])

    try:
        from infrastructure.config import STORAGE_VAULT_BUCKET
        from infrastructure.db.supabase_client import get_supabase

        client = get_supabase()
        data = client.storage.from_(STORAGE_VAULT_BUCKET).download(vault_path)
        if isinstance(data, bytes) and data:
            return data, image_id, content_type
    except Exception as exc:
        logger.warning("_fetch_primary_image: vault download failed: {}", exc)

    return None, image_id, content_type


async def compute_matches(ctx: dict, **payload: Any) -> dict[str, Any]:
    """Sprint 4/5: spatial + multimodal match scoring + HIGH-match notifications.

    If matched_to_report_id is set (finder selected a LOST post), score that
    pair first and always upsert/notify when band is HIGH/MEDIUM.
    """
    report_id_str: Optional[str] = payload.get("report_id")
    user_id_str: Optional[str] = payload.get("user_id")
    matched_to_str: Optional[str] = payload.get("matched_to_report_id")

    logger.info(
        "compute_matches START report_id={} matched_to={}",
        report_id_str,
        matched_to_str,
    )

    if not report_id_str:
        return {"status": "error", "reason": "missing report_id"}

    report_id = UUID(str(report_id_str))

    try:
        from services.match_service import (
            compute_match_scores,
            find_candidates,
            mark_match_notified,
            score_pair,
            upsert_match,
        )
        from services.notification_service import notify_match

        scored: list[dict[str, Any]] = []

        # Preferred path: finder explicitly selected a LOST report
        if matched_to_str:
            try:
                pair = score_pair(UUID(str(matched_to_str)), report_id)
                pair["source_id"] = str(matched_to_str)
                pair["candidate_id"] = report_id_str
                scored = [pair]
                logger.info(
                    "compute_matches: linked pair score={:.3f} band={}",
                    pair["score"],
                    pair["band"],
                )
            except Exception as exc:
                logger.warning("compute_matches: score_pair failed: {}", exc)

        # Also scan spatial candidates (may add more matches)
        candidates = find_candidates(report_id)
        if candidates:
            src_emb = _get_report_embedding_sync(report_id)
            src_cat = _get_report_category_sync(report_id)
            spatial = compute_match_scores(
                report_id,
                candidates,
                source_category=src_cat,
                source_embedding=src_emb,
            )
            # Avoid duplicating the linked pair
            linked = set()
            if matched_to_str:
                linked.add(frozenset({report_id_str, str(matched_to_str)}))
            for s in spatial:
                key = frozenset({s["source_id"], s["candidate_id"]})
                if key not in linked:
                    scored.append(s)

        if not scored:
            logger.info("compute_matches: no candidates for report_id={}", report_id_str)
            return {"report_id": report_id_str, "status": "no_candidates", "matches": 0}

        src_user_id = _get_report_user_id(report_id)
        high_count = 0
        total_upserted = 0

        for s in scored:
            try:
                a_id = UUID(s["source_id"]) if s.get("source_id") else report_id
                b_id = UUID(s["candidate_id"])
                # When source is this report, swap for upsert canonical pair
                if str(a_id) == report_id_str:
                    a_id, b_id = report_id, b_id
                else:
                    a_id, b_id = a_id, report_id if str(b_id) == report_id_str else b_id

                match_id = upsert_match(
                    report_a_id=UUID(s.get("source_id", report_id_str)),
                    report_b_id=UUID(s["candidate_id"]),
                    score=s["score"],
                    band=s["band"],
                    vision_score=s["vision_score"],
                    text_score=s["text_score"],
                    geo_score=s["geo_score"],
                    category_score=s["category_score"],
                    distance_m=s["distance_m"],
                )
                total_upserted += 1

                # Notify on HIGH (≥0.80); MEDIUM when explicitly linked; always
                # notify the LOST report owner when a FOUND candidate scores ≥ medium.
                should_notify = s["band"] == "HIGH" or (
                    matched_to_str and s["band"] in ("HIGH", "MEDIUM")
                )
                if not should_notify and s["band"] == "MEDIUM":
                    # Threshold path: lost owner gets alert when found is close enough
                    should_notify = True
                if should_notify and src_user_id:
                    other_id = UUID(s["candidate_id"])
                    if str(other_id) == report_id_str:
                        other_id = UUID(s["source_id"])

                    notified = notify_match(
                        user_id=src_user_id,
                        match_id=match_id,
                        report_id=report_id,
                        matched_report_id=other_id,
                        score=s["score"],
                        band=s["band"],
                        distance_m=s["distance_m"],
                    )
                    if notified:
                        mark_match_notified(match_id)
                        high_count += 1

                    other_user = _get_report_user_id(other_id)
                    if other_user and other_user != src_user_id:
                        if notify_match(
                            user_id=other_user,
                            match_id=match_id,
                            report_id=other_id,
                            matched_report_id=report_id,
                            score=s["score"],
                            band=s["band"],
                            distance_m=s["distance_m"],
                        ):
                            high_count += 1

            except Exception as exc:
                logger.warning(
                    "compute_matches: upsert/notify failed candidate={}: {}",
                    s.get("candidate_id"),
                    exc,
                )

        logger.info(
            "compute_matches COMPLETE report_id={} upserted={} notified={}",
            report_id_str,
            total_upserted,
            high_count,
        )
        return {
            "report_id": report_id_str,
            "status": "complete",
            "matches_upserted": total_upserted,
            "high_notified": high_count,
            "linked": bool(matched_to_str),
        }

    except Exception as exc:
        logger.error("compute_matches FAILED report_id={}: {}", report_id_str, exc)
        return {"report_id": report_id_str, "status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Sprint 4 sync DB helpers (called from async worker tasks)
# ---------------------------------------------------------------------------

def _check_near_dup(report_id: UUID, phash: int) -> bool:
    """Return True if another active report has Hamming distance ≤ 5 from phash."""
    from sqlalchemy import text as sqla_text
    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        rows = session.execute(
            sqla_text(
                """
                SELECT ri.phash
                FROM report_images ri
                JOIN reports r ON r.id = ri.report_id
                WHERE ri.phash IS NOT NULL
                  AND ri.report_id <> :rid
                  AND r.status IN ('active', 'pending', 'processing')
                LIMIT 200
                """
            ),
            {"rid": str(report_id)},
        ).mappings().all()
    finally:
        session.close()

    for row in rows:
        other_hash = row["phash"]
        if other_hash is None:
            continue
        # Hamming distance between two 64-bit integers
        xor = int(phash) ^ int(other_hash)
        distance = bin(xor).count("1")
        if distance <= 5:
            return True
    return False


def _get_report_embedding_sync(report_id: UUID):
    from sqlalchemy import text as sqla_text
    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        row = session.execute(
            sqla_text("SELECT text_embedding::text AS e FROM reports WHERE id = :id"),
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


def _get_report_category_sync(report_id: UUID) -> Optional[str]:
    from sqlalchemy import text as sqla_text
    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        row = session.execute(
            sqla_text("SELECT category FROM reports WHERE id = :id"),
            {"id": str(report_id)},
        ).mappings().first()
    finally:
        session.close()
    return row["category"] if row else None


def _get_report_user_id(report_id: UUID) -> Optional[UUID]:
    from sqlalchemy import text as sqla_text
    from infrastructure.db.sql_client import get_session

    session = get_session()
    try:
        row = session.execute(
            sqla_text("SELECT user_id FROM reports WHERE id = :id"),
            {"id": str(report_id)},
        ).mappings().first()
    finally:
        session.close()
    if row is None:
        return None
    try:
        return UUID(str(row["user_id"]))
    except Exception:
        return None


class WorkerSettings:
    functions = [process_report_ai, compute_matches]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings_from_env()
    # Docker Desktop DNS/TCP can exceed Arq's 1s default after a long AI job.
    job_timeout = 180
    max_tries = 5
