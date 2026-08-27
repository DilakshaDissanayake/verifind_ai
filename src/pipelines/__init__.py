"""VERIFIND AI pipelines — Sprint 3."""

from pipelines.dual_executor import run_dual_pipeline
from pipelines.fusion import (
    category_match_score,
    compute_fusion_score,
    cosine_similarity,
    geo_score_from_distance,
    score_band,
)
from pipelines.metadata_pipeline import (
    compute_hsv_histogram,
    compute_phash,
    extract_exif,
    is_near_duplicate,
    phash_hamming,
    public_exif,
    run_metadata_pipeline,
)
from pipelines.sanitization_pipeline import run_sanitization_pipeline, sanitize_image
from pipelines.text_pipeline import run_text_pipeline
from pipelines.vision_pipeline import run_vision_pipeline

__all__ = [
    # vision
    "run_vision_pipeline",
    # text / embed
    "run_text_pipeline",
    # dual
    "run_dual_pipeline",
    # fusion
    "compute_fusion_score",
    "score_band",
    "cosine_similarity",
    "geo_score_from_distance",
    "category_match_score",
    # sanitization
    "sanitize_image",
    "run_sanitization_pipeline",
    # metadata
    "extract_exif",
    "public_exif",
    "run_metadata_pipeline",
    "compute_phash",
    "phash_hamming",
    "is_near_duplicate",
    "compute_hsv_histogram",
]
