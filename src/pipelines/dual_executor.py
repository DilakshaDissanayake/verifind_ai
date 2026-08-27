"""Dual executor — Sprint 3.

Runs vision and text pipelines in parallel via asyncio.gather.
Budget: combined wall time ≤ param.yaml pipeline.ai_budget_seconds (default 8 s).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from loguru import logger

from infrastructure.config import PARAMS
from pipelines.text_pipeline import run_text_pipeline
from pipelines.vision_pipeline import run_vision_pipeline

_BUDGET_S: float = float(
    (PARAMS.get("pipeline") or {}).get("ai_budget_seconds", 8)
)


async def run_dual_pipeline(
    *,
    report_id: str,
    image_bytes: Optional[bytes] = None,
    content_type: str = "image/jpeg",
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
) -> dict[str, Any]:
    """Run vision + text embed in parallel.

    Returns merged result dict with keys:
        vision, text, total_latency_s, within_budget, budget_s
    If no image_bytes, vision result is a stub.
    """
    start = time.monotonic()
    desc = description or ""

    tasks = []
    if image_bytes:
        tasks.append(
            run_vision_pipeline(
                image_bytes,
                report_id=report_id,
                content_type=content_type,
            )
        )
    else:
        tasks.append(_vision_stub(report_id))

    tasks.append(
        run_text_pipeline(
            desc,
            report_id=report_id,
            title=title,
            category=category,
        )
    )

    try:
        vision_result, text_result = await asyncio.gather(*tasks, return_exceptions=False)
    except Exception as exc:
        logger.error("dual_pipeline gather failed for report_id={}: {}", report_id, exc)
        vision_result = {"report_id": report_id, "_source": "gather_error"}
        text_result = {"report_id": report_id, "embedding": [], "_source": "gather_error"}

    total_latency_s = round(time.monotonic() - start, 3)
    within_budget = total_latency_s <= _BUDGET_S

    if not within_budget:
        logger.warning(
            "dual_pipeline OVER BUDGET report_id={} total_latency_s={} budget_s={}",
            report_id, total_latency_s, _BUDGET_S,
        )

    logger.info(
        "dual_pipeline report_id={} total_latency_s={} within_budget={}",
        report_id, total_latency_s, within_budget,
    )

    return {
        "report_id": report_id,
        "vision": vision_result,
        "text": text_result,
        "total_latency_s": total_latency_s,
        "within_budget": within_budget,
        "budget_s": _BUDGET_S,
    }


async def _vision_stub(report_id: str) -> dict[str, Any]:
    """Used when no image is provided."""
    return {
        "report_id": report_id,
        "category": "other",
        "brand": None,
        "colors": [],
        "attributes": {},
        "mask_boxes": [],
        "confidence": 0.0,
        "_source": "no_image",
    }
