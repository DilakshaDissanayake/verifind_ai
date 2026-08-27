"""Sanitization pipeline — Sprint 3/4.

Sprint 3: Implements Gaussian blur on mask_box regions (unique identifiers).
Sprint 4: Will complete vault-to-public split with full storage upload.

Public image = original with each mask_box region blurred (σ=15).
Vault = original bytes (stored in Sprint 2 upload).
"""

from __future__ import annotations

import io
import time
from typing import Any, Optional

from loguru import logger

from infrastructure.config import BLUR_SIGMA


def sanitize_image(
    image_bytes: bytes,
    *,
    mask_boxes: list[dict[str, Any]],
    blur_sigma: float = BLUR_SIGMA,
    content_type: str = "image/jpeg",
) -> bytes:
    """Apply Gaussian blur to each mask_box region.

    mask_boxes: list of {x, y, w, h} in normalized [0,1] coordinates.
    Returns sanitized JPEG bytes (original unchanged).
    """
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        logger.warning("sanitize_image: Pillow not installed — returning original")
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        logger.warning("sanitize_image: cannot open image: {} — returning original", exc)
        return image_bytes

    W, H = img.size
    radius = max(1, int(blur_sigma))

    for box in mask_boxes:
        try:
            x = int(float(box.get("x", 0)) * W)
            y = int(float(box.get("y", 0)) * H)
            w = int(float(box.get("w", 0)) * W)
            h = int(float(box.get("h", 0)) * H)
            if w <= 0 or h <= 0:
                continue
            # Clamp to image bounds
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(W, x + w), min(H, y + h)
            if x2 <= x1 or y2 <= y1:
                continue
            region = img.crop((x1, y1, x2, y2))
            blurred = region.filter(ImageFilter.GaussianBlur(radius=radius))
            img.paste(blurred, (x1, y1))
        except Exception as exc:
            logger.warning("sanitize_image: skipping box {}: {}", box, exc)
            continue

    out = io.BytesIO()
    fmt = "PNG" if content_type == "image/png" else "JPEG"
    save_kwargs: dict[str, Any] = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = 85
    img.save(out, **save_kwargs)
    return out.getvalue()


async def run_sanitization_pipeline(
    image_bytes: bytes,
    *,
    report_id: str,
    image_id: str,
    mask_boxes: Optional[list[dict[str, Any]]] = None,
    content_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Blur mask regions; upload sanitized bytes to public bucket.

    Sprint 3: returns sanitized bytes + metadata; storage upload in Sprint 4.
    """
    start = time.monotonic()
    boxes = mask_boxes or []

    sanitized_bytes = sanitize_image(
        image_bytes,
        mask_boxes=boxes,
        content_type=content_type,
    )

    latency_s = round(time.monotonic() - start, 3)
    regions_blurred = len(boxes)

    public_path: Optional[str] = None
    upload_error: Optional[str] = None

    # Sprint 3: attempt storage upload; gracefully skip if unavailable
    if sanitized_bytes:
        ext = ".png" if content_type == "image/png" else ".jpg"
        public_path = f"{report_id}/{image_id}_public{ext}"
        try:
            from infrastructure.storage.image_storage import upload_public

            upload_public(public_path, sanitized_bytes, content_type=content_type)
            logger.info(
                "sanitization: uploaded public_path={} regions_blurred={}",
                public_path, regions_blurred,
            )
        except Exception as exc:
            logger.warning("sanitization: public upload failed (will retry S4): {}", exc)
            upload_error = str(exc)
            public_path = None

    logger.info(
        "sanitization report_id={} image_id={} regions_blurred={} latency_s={}",
        report_id, image_id, regions_blurred, latency_s,
    )
    return {
        "report_id": report_id,
        "image_id": image_id,
        "public_path": public_path,
        "regions_blurred": regions_blurred,
        "sanitized_bytes_len": len(sanitized_bytes),
        "latency_s": latency_s,
        "upload_error": upload_error,
    }
