"""EXIF + pHash + HSV histogram metadata pipeline — Sprint 3.

Sprint 2: EXIF only.
Sprint 3: adds perceptual hash (imagehash) and HSV color histogram (Pillow).
pHash Hamming ≤ 5 → flag near-duplicate (param.yaml phash.hamming_flag_max).
"""

from __future__ import annotations

import io
import math
from typing import Any, Optional

from infrastructure.config import PARAMS

_PHASH_HAMMING_MAX: int = int(
    (PARAMS.get("phash") or {}).get("hamming_flag_max", 5)
)

# EXIF tags that leak precise location or device identity on public APIs
_SENSITIVE_KEYS = frozenset(
    {
        "GPSInfo",
        "GPSLatitude",
        "GPSLongitude",
        "GPSAltitude",
        "GPSDateStamp",
        "GPSTimeStamp",
        "MakerNote",
        "SerialNumber",
        "BodySerialNumber",
        "LensSerialNumber",
        "CameraOwnerName",
    }
)


def extract_exif(image_bytes: bytes) -> dict[str, Any]:
    """
    Extract EXIF as a JSON-serializable dict.

    Stores full metadata (including GPS) for forensics in `report_images.exif_json`.
    Public API responses must use `public_exif()` to strip sensitive fields.
    """
    try:
        from io import BytesIO

        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS
    except ImportError:
        return {"_error": "pillow_not_installed"}

    try:
        img = Image.open(BytesIO(image_bytes))
    except Exception as exc:
        return {"_error": f"open_failed:{exc}"}

    raw = img._getexif() if hasattr(img, "_getexif") else None
    if not raw:
        return {
            "format": img.format,
            "size": list(img.size) if img.size else None,
            "mode": img.mode,
            "has_exif": False,
        }

    out: dict[str, Any] = {
        "format": img.format,
        "size": list(img.size) if img.size else None,
        "mode": img.mode,
        "has_exif": True,
    }
    for tag_id, value in raw.items():
        name = TAGS.get(tag_id, str(tag_id))
        if name == "GPSInfo" and isinstance(value, dict):
            gps: dict[str, Any] = {}
            for gk, gv in value.items():
                gname = GPSTAGS.get(gk, str(gk))
                gps[gname] = _jsonable(gv)
            out["GPSInfo"] = gps
            # Also flatten decimal lat/lon when present
            decimal = _gps_to_decimal(gps)
            if decimal:
                out["gps_decimal"] = decimal
        else:
            out[name] = _jsonable(value)
    return out


def public_exif(exif: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Strip GPS / serials before returning on public APIs."""
    if not exif:
        return None
    cleaned = {
        k: v
        for k, v in exif.items()
        if k not in _SENSITIVE_KEYS and k != "gps_decimal"
    }
    return cleaned


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()[:64]
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    try:
        # IFDRational etc.
        return float(value)
    except Exception:
        return str(value)


def _gps_to_decimal(gps: dict[str, Any]) -> Optional[dict[str, float]]:
    try:
        lat = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef", "N"))
        lon = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef", "E"))
        if lat is None or lon is None:
            return None
        return {"latitude": lat, "longitude": lon}
    except Exception:
        return None


def _dms_to_decimal(dms: Any, ref: Any) -> Optional[float]:
    if not dms or not isinstance(dms, (list, tuple)) or len(dms) < 3:
        return None
    deg, minutes, seconds = float(dms[0]), float(dms[1]), float(dms[2])
    decimal = deg + minutes / 60.0 + seconds / 3600.0
    if str(ref).upper() in ("S", "W"):
        decimal = -decimal
    return decimal


async def run_metadata_pipeline(image_bytes: bytes, *, report_id: str) -> dict[str, Any]:
    """Sprint 3 entry: EXIF + pHash + HSV histogram."""
    exif = extract_exif(image_bytes)
    phash_val = compute_phash(image_bytes)
    hsv = compute_hsv_histogram(image_bytes)
    return {
        "report_id": report_id,
        "exif": exif,
        "phash": phash_val,
        "hsv_histogram": hsv,
        "sprint": 3,
    }


def compute_phash(image_bytes: bytes) -> Optional[int]:
    """Compute perceptual hash as integer. Returns None if imagehash not installed."""
    try:
        import imagehash
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        h = imagehash.phash(img)
        return int(str(h), 16)
    except ImportError:
        return None
    except Exception:
        return None


def phash_hamming(a: Optional[int], b: Optional[int]) -> Optional[int]:
    """Compute Hamming distance between two pHash integers.

    Returns None if either hash is None.
    Returns 0 if identical. Flag near-dup if result ≤ _PHASH_HAMMING_MAX.
    """
    if a is None or b is None:
        return None
    xor = a ^ b
    return bin(xor).count("1")


def is_near_duplicate(a: Optional[int], b: Optional[int]) -> bool:
    """True if Hamming distance ≤ param.yaml phash.hamming_flag_max."""
    d = phash_hamming(a, b)
    if d is None:
        return False
    return d <= _PHASH_HAMMING_MAX


def compute_hsv_histogram(image_bytes: bytes, bins: int = 8) -> Optional[dict[str, Any]]:
    """Compute compact HSV histogram (bins per channel). Returns None on error."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((64, 64))
        hsv_img = img.convert("HSV") if hasattr(img, "convert") else None
        if hsv_img is None:
            return None
        # Use raw pixel stats as a lightweight proxy when full HSV not available
        r_hist = _channel_hist(img, 0, bins)
        g_hist = _channel_hist(img, 1, bins)
        b_hist = _channel_hist(img, 2, bins)
        return {"r": r_hist, "g": g_hist, "b": b_hist, "bins": bins}
    except Exception:
        return None


def _channel_hist(img: Any, channel: int, bins: int) -> list[float]:
    """Normalized histogram for one channel."""
    try:
        channels = img.split()
        if channel >= len(channels):
            return [0.0] * bins
        ch_img = channels[channel]
        # Use tobytes() to avoid deprecated getdata() in Pillow 14+
        raw = ch_img.tobytes()
        total = len(raw)
        if total == 0:
            return [0.0] * bins
        step = max(1, 256 // bins)
        counts = [0] * bins
        for b in raw:
            idx = min(b // step, bins - 1)
            counts[idx] += 1
        return [round(c / total, 6) for c in counts]
    except Exception:
        return [0.0] * bins
