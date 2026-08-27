"""Vision pipeline — Sprint 3.

Calls gpt-4o-mini with the image bytes via OpenAI vision API.
Returns structured tags: category, brand, colors, attributes, mask_boxes.
Budget: must complete within param.yaml pipeline.ai_budget_seconds (default 8 s).
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any, Optional

from loguru import logger

from infrastructure.config import VISION_MODEL
from infrastructure.llm.llm_provider import chat_completions_with_failover
from infrastructure.observability import get_tracer

_SYSTEM_PROMPT = """\
You are a precise object-recognition assistant for a lost-and-found platform.
Analyze the image and respond with a JSON object only (no markdown fences).

Required JSON schema:
{
  "category": "<electronics|bag|wallet|keys|clothing|jewelry|document|other>",
  "brand": "<brand name or null>",
  "colors": ["<primary color>", "<secondary color or more>"],
  "attributes": {
    "model": "<model name or null>",
    "condition": "<good|fair|damaged|unknown>",
    "distinctive_features": "<brief description or null>"
  },
  "mask_boxes": [
    {"label": "<what to blur>", "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
  ],
  "confidence": 0.0
}

mask_boxes: normalized [0,1] bounding boxes of regions containing unique identifiers
(serial numbers, stickers with text, engravings, QR codes, screen text, labels with IDs).
Include ALL such regions — they will be Gaussian-blurred on the public image.
confidence: your overall confidence 0–1.
"""

_FALLBACK_RESULT: dict[str, Any] = {
    "category": "other",
    "brand": None,
    "colors": [],
    "attributes": {"model": None, "condition": "unknown", "distinctive_features": None},
    "mask_boxes": [],
    "confidence": 0.0,
    "_source": "fallback",
}


async def run_vision_pipeline(
    image_bytes: bytes,
    *,
    report_id: str,
    content_type: str = "image/jpeg",
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    """Run vision tagging on image_bytes.

    Returns a dict with keys: report_id, category, brand, colors, attributes,
    mask_boxes, confidence, model, latency_s.
    Never raises — returns fallback on any error.
    """
    tracer = get_tracer()
    start = time.monotonic()

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{content_type};base64,{b64}"
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url, "detail": "low"},
                },
                {
                    "type": "text",
                    "text": "Identify this item and return the JSON object.",
                },
            ],
        },
    ]

    used_model = VISION_MODEL
    used_provider = "openai"
    try:
        # Multi-provider circuit-breaker chain: OpenAI → OpenRouter(Gemini) → Ollama
        out = await asyncio.wait_for(
            chat_completions_with_failover(
                role="vision",
                messages=messages,
                max_tokens=800,
                temperature=0.0,
                timeout_s=timeout_s,
            ),
            timeout=timeout_s + 5.0,
        )
        result = _parse_tags(out["content"])
        used_model = out.get("model") or VISION_MODEL
        used_provider = out.get("provider") or "openai"
        if out.get("degraded"):
            result["_degraded"] = True
            result["_provider"] = used_provider
    except asyncio.TimeoutError:
        logger.warning("vision_pipeline: timeout after {}s for report_id={}", timeout_s, report_id)
        result = {**_FALLBACK_RESULT, "_source": "timeout"}
    except Exception as exc:
        logger.warning("vision_pipeline error for report_id={}: {}", report_id, exc)
        result = {**_FALLBACK_RESULT, "_source": f"error:{type(exc).__name__}"}

    latency_s = round(time.monotonic() - start, 3)
    result["report_id"] = report_id
    result["model"] = used_model
    result["provider"] = used_provider
    result["latency_s"] = latency_s

    if tracer:
        try:
            tracer.trace(
                name="vision_pipeline",
                input={"report_id": report_id, "bytes_len": len(image_bytes)},
                output={"category": result.get("category"), "confidence": result.get("confidence"), "latency_s": latency_s},
            )
        except Exception as exc:
            logger.debug("vision_pipeline tracing failed: {}", exc)

    logger.info(
        "vision_pipeline report_id={} category={} brand={} confidence={} latency_s={}",
        report_id,
        result.get("category"),
        result.get("brand"),
        result.get("confidence"),
        latency_s,
    )
    return result


async def _call_openai_vision(api_key: str, payload: dict[str, Any]) -> str:
    """Legacy helper kept for unit-test patches; prefer chat_completions_with_failover."""
    messages = payload.get("messages") or []
    out = await chat_completions_with_failover(
        role="vision",
        messages=messages,
        max_tokens=int(payload.get("max_tokens") or 800),
        temperature=float(payload.get("temperature") or 0),
    )
    return out["content"]


def _parse_tags(content: str) -> dict[str, Any]:
    """Parse JSON from model response. Strip markdown fences if present."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.startswith("```")
        )
    try:
        parsed = json.loads(text)
        return {
            "category": str(parsed.get("category") or "other"),
            "brand": parsed.get("brand"),
            "colors": list(parsed.get("colors") or []),
            "attributes": parsed.get("attributes") or {},
            "mask_boxes": _validate_boxes(parsed.get("mask_boxes") or []),
            "confidence": float(parsed.get("confidence") or 0.0),
            "_source": "model",
        }
    except Exception as exc:
        logger.warning("vision_pipeline: failed to parse JSON response: {} — raw: {!r}", exc, content[:200])
        return {**_FALLBACK_RESULT, "_source": "parse_error"}


def _validate_boxes(boxes: Any) -> list[dict[str, Any]]:
    """Keep only valid normalized bounding box entries."""
    if not isinstance(boxes, list):
        return []
    out = []
    for b in boxes:
        if not isinstance(b, dict):
            continue
        try:
            out.append({
                "label": str(b.get("label", "id_region")),
                "x": float(b.get("x", 0)),
                "y": float(b.get("y", 0)),
                "w": float(b.get("w", 0)),
                "h": float(b.get("h", 0)),
            })
        except (TypeError, ValueError):
            continue
    return out
