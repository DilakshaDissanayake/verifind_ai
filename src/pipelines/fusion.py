"""Fusion score — Sprint 3.

Weighted combination: Score = α·Vision + β·Text + γ·Geo + δ·Category
Default weights from param.yaml:  0.30 · 0.30 · 0.25 · 0.15 = 1.00

Score bands: HIGH ≥ 0.80 · MEDIUM 0.50–0.79 · LOW < 0.50
"""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from infrastructure.config import FUSION_WEIGHTS, MATCH_HIGH, MATCH_MEDIUM

ScoreBand = Literal["HIGH", "MEDIUM", "LOW"]


def compute_fusion_score(
    *,
    vision_score: Optional[float] = None,
    text_score: Optional[float] = None,
    geo_score: Optional[float] = None,
    category_score: Optional[float] = None,
) -> dict[str, Any]:
    """Compute weighted fusion score from component scores.

    All component scores are optional floats in [0, 1].
    Missing components fall back to 0.0 so partial data degrades gracefully.

    Returns:
        {score, band, vision_score, text_score, geo_score, category_score,
         weights_used}
    """
    w = FUSION_WEIGHTS
    v = float(vision_score or 0.0)
    t = float(text_score or 0.0)
    g = float(geo_score or 0.0)
    c = float(category_score or 0.0)

    # Clamp each component to [0, 1]
    v = max(0.0, min(1.0, v))
    t = max(0.0, min(1.0, t))
    g = max(0.0, min(1.0, g))
    c = max(0.0, min(1.0, c))

    score = (
        w["vision"] * v
        + w["text"] * t
        + w["geo"] * g
        + w["category"] * c
    )
    score = round(min(1.0, max(0.0, score)), 6)
    band = score_band(score)

    return {
        "score": score,
        "band": band,
        "vision_score": v,
        "text_score": t,
        "geo_score": g,
        "category_score": c,
        "weights_used": w,
    }


def score_band(score: float) -> ScoreBand:
    if score >= MATCH_HIGH:
        return "HIGH"
    if score >= MATCH_MEDIUM:
        return "MEDIUM"
    return "LOW"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two equal-length float vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return round(dot / (mag_a * mag_b), 6)


def geo_score_from_distance(distance_m: float, radius_m: float = 5000.0) -> float:
    """Linear decay: 1.0 at 0 m → 0.0 at radius_m."""
    if distance_m <= 0:
        return 1.0
    if distance_m >= radius_m:
        return 0.0
    return round(1.0 - distance_m / radius_m, 6)


_KNOWN_CATEGORIES = {
    "electronics",
    "bag",
    "wallet",
    "keys",
    "clothing",
    "jewelry",
    "document",
}


def parse_categories(value: Optional[str]) -> set[str]:
    """Extract category tokens from a free-text / comma category field."""
    if not value:
        return set()
    categories: set[str] = set()
    for part in value.replace("|", ",").replace("/", ",").split(","):
        words = re.findall(r"[a-z0-9]+", part.strip().lower())
        if len(words) == 1:
            categories.add(words[0])
        categories.update(word for word in words if word in _KNOWN_CATEGORIES)
    categories.discard("other")
    return categories


def category_match_score(cat_a: Optional[str], cat_b: Optional[str]) -> float:
    """Score shared categories; plain ``other`` is an unknown fallback."""
    if not cat_a or not cat_b:
        return 0.0
    return 1.0 if parse_categories(cat_a) & parse_categories(cat_b) else 0.0


def categories_conflict(cat_a: Optional[str], cat_b: Optional[str]) -> bool:
    """True when both sides have *known* taxonomy categories with zero overlap.

    Unknown / empty / ``other`` / free-text-only labels do not force a conflict.
    """
    a = parse_categories(cat_a) & _KNOWN_CATEGORIES
    b = parse_categories(cat_b) & _KNOWN_CATEGORIES
    if not a or not b:
        return False
    return len(a & b) == 0
