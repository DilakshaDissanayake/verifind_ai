"""Text pipeline — Sprint 3.

Embeds report title + description using text-embedding-3-small (1536d).
Stores embedding in reports.text_embedding (pgvector).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, List, Optional

from loguru import logger

from infrastructure.config import EMBEDDING_DIM, EMBEDDING_MODEL, get_api_key
from infrastructure.observability import get_tracer

_MAX_CHARS = 2000  # truncate combined text to ~500 tokens


async def run_text_pipeline(
    description: str,
    *,
    report_id: str,
    title: Optional[str] = None,
    category: Optional[str] = None,
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    """Embed combined text; return embedding vector and metadata.

    Returns:
        {report_id, embedding: List[float], dims: int, model, latency_s}
    Never raises — returns zero-vector on error.
    """
    tracer = get_tracer()
    start = time.monotonic()

    api_key = get_api_key("openai")
    if not api_key:
        logger.warning("text_pipeline: OPENAI_API_KEY not set — returning zero vector")
        return _zero_result(report_id, "no_api_key")

    combined = _build_text(title=title, description=description, category=category)

    try:
        vector = await asyncio.wait_for(
            _embed(api_key, combined),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        logger.warning("text_pipeline: timeout after {}s for report_id={}", timeout_s, report_id)
        return _zero_result(report_id, "timeout")
    except Exception as exc:
        logger.warning("text_pipeline error for report_id={}: {}", report_id, exc)
        return _zero_result(report_id, f"error:{type(exc).__name__}")

    latency_s = round(time.monotonic() - start, 3)

    if tracer:
        try:
            tracer.trace(
                name="text_pipeline",
                input={"report_id": report_id, "text_len": len(combined)},
                output={"dims": len(vector), "latency_s": latency_s},
            )
        except Exception as exc:
            logger.debug("text_pipeline tracing failed: {}", exc)

    logger.info(
        "text_pipeline report_id={} dims={} latency_s={}",
        report_id, len(vector), latency_s,
    )
    return {
        "report_id": report_id,
        "embedding": vector,
        "dims": len(vector),
        "model": EMBEDDING_MODEL,
        "latency_s": latency_s,
        "_source": "model",
    }


async def _embed(api_key: str, text: str) -> List[float]:
    """Single embedding call to OpenAI."""
    import httpx

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": EMBEDDING_MODEL, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return list(data["data"][0]["embedding"])


def _build_text(
    *,
    title: Optional[str],
    description: Optional[str],
    category: Optional[str],
) -> str:
    parts = []
    if category:
        parts.append(f"Category: {category}")
    if title:
        parts.append(f"Title: {title}")
    if description:
        parts.append(f"Description: {description}")
    combined = " | ".join(parts) if parts else "(no description)"
    return combined[:_MAX_CHARS]


def _zero_result(report_id: str, source: str) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "embedding": [0.0] * EMBEDDING_DIM,
        "dims": EMBEDDING_DIM,
        "model": EMBEDDING_MODEL,
        "latency_s": 0.0,
        "_source": source,
    }
