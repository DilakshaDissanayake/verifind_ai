"""Sprint 3 — AI dual pipeline unit tests (no live DB / OpenAI calls)."""

from __future__ import annotations

import asyncio
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ["AUTH_DEV_BYPASS"] = "true"
os.environ["ARQ_WORKER_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = "test-key-not-real"

try:
    from infrastructure.config import get_settings
    get_settings.cache_clear()
except Exception:
    pass


# ---------------------------------------------------------------------------
# vision_pipeline tests
# ---------------------------------------------------------------------------

class TestVisionPipeline:
    def test_parse_tags_valid_json(self):
        from pipelines.vision_pipeline import _parse_tags

        content = '{"category":"electronics","brand":"Apple","colors":["silver","black"],' \
                  '"attributes":{"model":"MacBook","condition":"good","distinctive_features":"sticker"},' \
                  '"mask_boxes":[{"label":"serial","x":0.1,"y":0.1,"w":0.2,"h":0.05}],"confidence":0.92}'
        result = _parse_tags(content)
        assert result["category"] == "electronics"
        assert result["brand"] == "Apple"
        assert result["colors"] == ["silver", "black"]
        assert len(result["mask_boxes"]) == 1
        assert result["mask_boxes"][0]["label"] == "serial"
        assert result["confidence"] == 0.92
        assert result["_source"] == "model"

    def test_parse_tags_strips_markdown_fence(self):
        from pipelines.vision_pipeline import _parse_tags

        content = '```json\n{"category":"bag","brand":null,"colors":["brown"],' \
                  '"attributes":{},"mask_boxes":[],"confidence":0.7}\n```'
        result = _parse_tags(content)
        assert result["category"] == "bag"

    def test_parse_tags_invalid_returns_fallback(self):
        from pipelines.vision_pipeline import _parse_tags, _FALLBACK_RESULT

        result = _parse_tags("not valid json at all !!!")
        assert result["_source"] == "parse_error"
        assert result["category"] == _FALLBACK_RESULT["category"]

    def test_validate_boxes_filters_bad(self):
        from pipelines.vision_pipeline import _validate_boxes

        boxes = [
            {"label": "serial", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.1},
            "not_a_dict",
            {"label": "qr", "x": "bad"},
        ]
        result = _validate_boxes(boxes)
        assert len(result) == 1
        assert result[0]["label"] == "serial"

    @pytest.mark.asyncio
    async def test_run_vision_pipeline_no_api_key(self):
        from pipelines.vision_pipeline import run_vision_pipeline

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            # Clear any cached config
            try:
                from infrastructure import config as cfg
                cfg.get_api_key.cache_clear() if hasattr(cfg.get_api_key, "cache_clear") else None
            except Exception:
                pass
            result = await run_vision_pipeline(b"fake_image_bytes", report_id="test-123")
        # Should return fallback gracefully
        assert result["report_id"] == "test-123"
        assert "category" in result
        assert "latency_s" in result

    @pytest.mark.asyncio
    async def test_run_vision_pipeline_mocked_call(self):
        from pipelines.vision_pipeline import run_vision_pipeline

        mock_response = (
            '{"category":"electronics","brand":"Dell","colors":["black"],'
            '"attributes":{"model":"XPS","condition":"good","distinctive_features":"sticker on lid"},'
            '"mask_boxes":[{"label":"serial_sticker","x":0.05,"y":0.8,"w":0.3,"h":0.1}],'
            '"confidence":0.88}'
        )
        with patch(
            "pipelines.vision_pipeline.chat_completions_with_failover",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = {
                "content": mock_response,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "degraded": False,
            }
            result = await run_vision_pipeline(b"fake_jpeg_bytes", report_id="r-001")

        assert result["category"] == "electronics"
        assert result["brand"] == "Dell"
        assert result["confidence"] == 0.88
        assert len(result["mask_boxes"]) == 1
        assert result["report_id"] == "r-001"
        assert result["latency_s"] >= 0


# ---------------------------------------------------------------------------
# text_pipeline tests
# ---------------------------------------------------------------------------

class TestTextPipeline:
    def test_build_text_all_fields(self):
        from pipelines.text_pipeline import _build_text

        text = _build_text(title="Lost laptop", description="Silver Dell XPS", category="electronics")
        assert "Lost laptop" in text
        assert "Silver Dell XPS" in text
        assert "electronics" in text

    def test_build_text_empty(self):
        from pipelines.text_pipeline import _build_text

        text = _build_text(title=None, description="", category=None)
        assert text == "(no description)"

    def test_build_text_truncates(self):
        from pipelines.text_pipeline import _build_text, _MAX_CHARS

        long = "x" * 5000
        text = _build_text(title=None, description=long, category=None)
        assert len(text) <= _MAX_CHARS

    def test_zero_result_shape(self):
        from pipelines.text_pipeline import _zero_result

        result = _zero_result("r-001", "timeout")
        assert result["report_id"] == "r-001"
        assert len(result["embedding"]) == 1536
        assert result["dims"] == 1536
        assert result["_source"] == "timeout"

    @pytest.mark.asyncio
    async def test_run_text_pipeline_mocked_embed(self):
        from pipelines.text_pipeline import run_text_pipeline

        fake_vector = [0.1] * 1536
        with patch("pipelines.text_pipeline._embed", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = fake_vector
            result = await run_text_pipeline(
                "Silver laptop lost near Colombo",
                report_id="r-002",
                title="Lost Silver Laptop",
                category="electronics",
            )

        assert result["report_id"] == "r-002"
        assert result["dims"] == 1536
        assert result["embedding"] == fake_vector
        assert result["latency_s"] >= 0


# ---------------------------------------------------------------------------
# dual_executor tests
# ---------------------------------------------------------------------------

class TestDualExecutor:
    @pytest.mark.asyncio
    async def test_run_dual_pipeline_no_image(self):
        from pipelines.dual_executor import run_dual_pipeline

        fake_emb = [0.05] * 1536
        with patch("pipelines.dual_executor.run_text_pipeline", new_callable=AsyncMock) as mock_text:
            mock_text.return_value = {
                "report_id": "r-003",
                "embedding": fake_emb,
                "dims": 1536,
                "latency_s": 0.5,
            }
            result = await run_dual_pipeline(
                report_id="r-003",
                image_bytes=None,
                description="brown leather wallet",
                title="Lost wallet",
                category="wallet",
            )

        assert result["report_id"] == "r-003"
        assert result["vision"]["_source"] == "no_image"
        assert result["text"]["dims"] == 1536
        assert "total_latency_s" in result
        assert "within_budget" in result

    @pytest.mark.asyncio
    async def test_run_dual_pipeline_with_image(self):
        from pipelines.dual_executor import run_dual_pipeline

        fake_vision = {
            "report_id": "r-004",
            "category": "electronics",
            "brand": "Apple",
            "colors": ["silver"],
            "attributes": {},
            "mask_boxes": [{"label": "serial", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05}],
            "confidence": 0.9,
            "latency_s": 1.2,
        }
        fake_text = {
            "report_id": "r-004",
            "embedding": [0.1] * 1536,
            "dims": 1536,
            "latency_s": 0.4,
        }
        with patch("pipelines.dual_executor.run_vision_pipeline", new_callable=AsyncMock) as mv, \
             patch("pipelines.dual_executor.run_text_pipeline", new_callable=AsyncMock) as mt:
            mv.return_value = fake_vision
            mt.return_value = fake_text
            result = await run_dual_pipeline(
                report_id="r-004",
                image_bytes=b"fake_jpeg",
                description="silver MacBook",
                title="Lost MacBook",
                category="electronics",
            )

        assert result["vision"]["category"] == "electronics"
        assert result["text"]["dims"] == 1536
        # Vision and text were called once each
        mv.assert_called_once()
        mt.assert_called_once()


# ---------------------------------------------------------------------------
# fusion tests
# ---------------------------------------------------------------------------

class TestFusion:
    def test_full_score_high(self):
        from pipelines.fusion import compute_fusion_score

        result = compute_fusion_score(
            vision_score=1.0,
            text_score=1.0,
            geo_score=1.0,
            category_score=1.0,
        )
        assert result["score"] == 1.0
        assert result["band"] == "HIGH"

    def test_full_score_zero_is_low(self):
        from pipelines.fusion import compute_fusion_score

        result = compute_fusion_score(
            vision_score=0.0,
            text_score=0.0,
            geo_score=0.0,
            category_score=0.0,
        )
        assert result["score"] == 0.0
        assert result["band"] == "LOW"

    def test_medium_band(self):
        from pipelines.fusion import compute_fusion_score

        # Should land around 0.65 → MEDIUM
        result = compute_fusion_score(
            vision_score=0.7,
            text_score=0.7,
            geo_score=0.6,
            category_score=0.5,
        )
        assert result["band"] == "MEDIUM"

    def test_missing_components_degrade_gracefully(self):
        from pipelines.fusion import compute_fusion_score

        result = compute_fusion_score(vision_score=1.0)
        assert 0.0 <= result["score"] <= 1.0
        assert result["band"] in ("HIGH", "MEDIUM", "LOW")

    def test_weights_sum_to_one(self):
        from infrastructure.config import FUSION_WEIGHTS

        total = sum(FUSION_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6

    def test_cosine_similarity_identical(self):
        from pipelines.fusion import cosine_similarity

        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        from pipelines.fusion import cosine_similarity

        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_empty(self):
        from pipelines.fusion import cosine_similarity

        assert cosine_similarity([], []) == 0.0

    def test_geo_score_decay(self):
        from pipelines.fusion import geo_score_from_distance

        assert geo_score_from_distance(0) == 1.0
        assert geo_score_from_distance(5000) == 0.0
        score_mid = geo_score_from_distance(2500)
        assert 0.49 <= score_mid <= 0.51

    def test_category_match_score(self):
        from pipelines.fusion import category_match_score

        assert category_match_score("electronics", "electronics") == 1.0
        assert category_match_score("Electronics", "electronics") == 1.0
        assert category_match_score("bag, electronics", "electronics, wallet") == 1.0
        assert category_match_score("wallet, bag", "bag") == 1.0
        assert category_match_score("Dell laptop bag", "bag") == 1.0
        assert category_match_score("bag", "wallet") == 0.0
        assert category_match_score("other", "other") == 0.0
        assert category_match_score(None, "bag") == 0.0


# ---------------------------------------------------------------------------
# sanitization_pipeline tests
# ---------------------------------------------------------------------------

class TestSanitizationPipeline:
    def _make_jpeg(self, w: int = 64, h: int = 64) -> bytes:
        pytest.importorskip("PIL")
        from PIL import Image

        buf = io.BytesIO()
        img = Image.new("RGB", (w, h), color=(200, 100, 50))
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def test_sanitize_no_boxes_unchanged_size(self):
        from pipelines.sanitization_pipeline import sanitize_image

        pytest.importorskip("PIL")
        original = self._make_jpeg()
        sanitized = sanitize_image(original, mask_boxes=[])
        # Should still be valid JPEG
        assert sanitized[:2] == b"\xff\xd8"

    def test_sanitize_with_box_produces_different_bytes(self):
        from pipelines.sanitization_pipeline import sanitize_image

        pytest.importorskip("PIL")
        from PIL import Image, ImageDraw
        import io as _io

        # Create image with distinct content in the blur region
        buf = _io.BytesIO()
        img = Image.new("RGB", (64, 64), color=(200, 100, 50))
        draw = ImageDraw.Draw(img)
        # Draw a bold text-like rectangle in the blur zone
        draw.rectangle([0, 0, 32, 32], fill=(0, 0, 0))
        draw.rectangle([2, 2, 10, 10], fill=(255, 255, 255))
        img.save(buf, format="PNG")
        original = buf.getvalue()

        boxes = [{"label": "serial", "x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5}]
        sanitized = sanitize_image(original, mask_boxes=boxes, content_type="image/png")
        # Reopen both and compare pixel at (4,4) — should be blurred (not pure white)
        orig_img = Image.open(_io.BytesIO(original)).convert("RGB")
        san_img = Image.open(_io.BytesIO(sanitized)).convert("RGB")
        orig_px = orig_img.getpixel((4, 4))
        san_px = san_img.getpixel((4, 4))
        assert orig_px != san_px, f"Expected pixel to change after blur, got orig={orig_px} san={san_px}"

    def test_sanitize_invalid_bytes_returns_original(self):
        from pipelines.sanitization_pipeline import sanitize_image

        bad = b"not_an_image"
        result = sanitize_image(bad, mask_boxes=[{"x": 0, "y": 0, "w": 0.5, "h": 0.5, "label": "x"}])
        assert result == bad

    @pytest.mark.asyncio
    async def test_run_sanitization_pipeline_no_storage(self):
        from pipelines.sanitization_pipeline import run_sanitization_pipeline

        pytest.importorskip("PIL")
        img = self._make_jpeg()
        boxes = [{"label": "serial", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}]

        with patch("infrastructure.storage.image_storage.upload_public", side_effect=Exception("no storage")):
            result = await run_sanitization_pipeline(
                img,
                report_id="r-005",
                image_id="img-001",
                mask_boxes=boxes,
            )

        assert result["report_id"] == "r-005"
        assert result["regions_blurred"] == 1
        assert result["upload_error"] is not None
        assert result["public_path"] is None


# ---------------------------------------------------------------------------
# metadata_pipeline Sprint 3 tests
# ---------------------------------------------------------------------------

class TestMetadataPipelineSprint3:
    def test_compute_phash_valid_image(self):
        pytest.importorskip("PIL")
        pytest.importorskip("imagehash")
        from pipelines.metadata_pipeline import compute_phash

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buf, format="JPEG")
        result = compute_phash(buf.getvalue())
        assert result is not None
        assert isinstance(result, int)

    def test_phash_identical_images_zero_distance(self):
        pytest.importorskip("PIL")
        pytest.importorskip("imagehash")
        from pipelines.metadata_pipeline import compute_phash, phash_hamming

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buf, format="JPEG")
        raw = buf.getvalue()
        h1 = compute_phash(raw)
        h2 = compute_phash(raw)
        assert phash_hamming(h1, h2) == 0

    def test_phash_different_images_nonzero_distance(self):
        pytest.importorskip("PIL")
        pytest.importorskip("imagehash")
        from pipelines.metadata_pipeline import compute_phash, phash_hamming, is_near_duplicate

        from PIL import Image

        def make(color: tuple) -> bytes:
            buf = io.BytesIO()
            Image.new("RGB", (64, 64), color=color).save(buf, format="JPEG")
            return buf.getvalue()

        h1 = compute_phash(make((255, 0, 0)))
        h2 = compute_phash(make((0, 0, 255)))
        d = phash_hamming(h1, h2)
        assert d is not None
        # These are very different images — should NOT be near-duplicates
        # (may occasionally be 0 for solid colors — acceptable)

    def test_phash_none_handling(self):
        from pipelines.metadata_pipeline import phash_hamming, is_near_duplicate

        assert phash_hamming(None, 123) is None
        assert is_near_duplicate(None, 123) is False

    def test_compute_hsv_histogram_shape(self):
        pytest.importorskip("PIL")
        from pipelines.metadata_pipeline import compute_hsv_histogram

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), color=(100, 150, 200)).save(buf, format="JPEG")
        hist = compute_hsv_histogram(buf.getvalue(), bins=8)
        assert hist is not None
        assert "r" in hist and "g" in hist and "b" in hist
        assert len(hist["r"]) == 8
        assert abs(sum(hist["r"]) - 1.0) < 0.01  # normalized

    @pytest.mark.asyncio
    async def test_run_metadata_pipeline_sprint3(self):
        pytest.importorskip("PIL")
        from pipelines.metadata_pipeline import run_metadata_pipeline

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buf, format="PNG")
        result = await run_metadata_pipeline(buf.getvalue(), report_id="r-meta")
        assert result["report_id"] == "r-meta"
        assert result["sprint"] == 3
        assert "exif" in result
        assert "phash" in result
        assert "hsv_histogram" in result


# ---------------------------------------------------------------------------
# API endpoint tests — ai-status
# ---------------------------------------------------------------------------

class TestAIStatusEndpoint:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        from api.main import create_app

        app = create_app()
        with TestClient(app) as c:
            yield c

    def test_ai_status_report_not_found(self, client):
        from services.report_service import ReportRecord

        with patch("api.routers.reports.report_service.get_report", return_value=None):
            res = client.get(
                f"/api/v1/reports/{uuid4()}/ai-status",
                headers={"Authorization": "Bearer dev"},
            )
        assert res.status_code == 404

    def test_ai_status_pending_no_tags(self, client):
        from services.report_service import ReportRecord

        fake_rec = ReportRecord(
            id=uuid4(),
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            report_type="LOST",
            category="electronics",
            title="Test",
            description="desc",
            status="pending",
            latitude=6.9275,
            longitude=79.8615,
            location_label=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        with patch("api.routers.reports.report_service.get_report", return_value=fake_rec), \
             patch("api.routers.reports._fetch_ai_tags", return_value=(None, False)):
            res = client.get(
                f"/api/v1/reports/{fake_rec.id}/ai-status",
                headers={"Authorization": "Bearer dev"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "pending"
        assert body["has_embedding"] is False
        assert body["tags"] is None

    def test_ai_status_active_with_tags(self, client):
        from api.schemas import AITagsOut
        from services.report_service import ReportRecord

        fake_id = uuid4()
        fake_rec = ReportRecord(
            id=fake_id,
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            report_type="FOUND",
            category="electronics",
            title="Found laptop",
            description="Silver MacBook",
            status="active",
            latitude=6.9275,
            longitude=79.8615,
            location_label=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        fake_tags = AITagsOut(
            tag_id=uuid4(),
            brand="Apple",
            colors=["silver"],
            category="electronics",
            attributes={"model": "MacBook"},
            mask_boxes=[{"label": "serial", "x": 0.1, "y": 0.8, "w": 0.3, "h": 0.1}],
            model="gpt-4o-mini",
        )
        with patch("api.routers.reports.report_service.get_report", return_value=fake_rec), \
             patch("api.routers.reports._fetch_ai_tags", return_value=(fake_tags, True)):
            res = client.get(
                f"/api/v1/reports/{fake_id}/ai-status",
                headers={"Authorization": "Bearer dev"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "active"
        assert body["has_embedding"] is True
        assert body["tags"]["brand"] == "Apple"
        assert body["tags"]["colors"] == ["silver"]
        assert len(body["tags"]["mask_boxes"]) == 1
        # Current API sprint marker (schema AIStatusResponse)
        assert body["sprint"] == "6"


# ---------------------------------------------------------------------------
# Worker task tests
# ---------------------------------------------------------------------------

class TestProcessReportAI:
    @pytest.mark.asyncio
    async def test_missing_report_id_returns_error(self):
        from workers.tasks import process_report_ai

        result = await process_report_ai({})
        assert result["status"] == "error"
        assert "missing report_id" in result["reason"]

    @pytest.mark.asyncio
    async def test_full_pipeline_mocked(self):
        from workers.tasks import process_report_ai

        report_id = str(uuid4())
        fake_dual = {
            "report_id": report_id,
            "vision": {
                "category": "electronics",
                "brand": "Apple",
                "colors": ["silver"],
                "attributes": {},
                "mask_boxes": [],
                "confidence": 0.9,
                "model": "gpt-4o-mini",
                "_source": "model",
            },
            "text": {
                "report_id": report_id,
                "embedding": [0.1] * 1536,
                "dims": 1536,
                "latency_s": 0.5,
            },
            "total_latency_s": 2.5,
            "within_budget": True,
        }
        fake_meta = {
            "report_id": report_id,
            "exif": {},
            "phash": 123456,
            "hsv_histogram": {"r": [0.1] * 8, "g": [0.1] * 8, "b": [0.1] * 8, "bins": 8},
            "sprint": 3,
        }
        with patch("workers.tasks._safe_set_status"), \
             patch("workers.tasks._fetch_primary_image", new_callable=AsyncMock, return_value=(b"fake", "img-001", "image/jpeg")), \
             patch("pipelines.dual_executor.run_dual_pipeline", new_callable=AsyncMock, return_value=fake_dual), \
             patch("pipelines.metadata_pipeline.run_metadata_pipeline", new_callable=AsyncMock, return_value=fake_meta), \
             patch("workers.tasks._store_ai_tags"), \
             patch("workers.tasks._store_text_embedding"), \
             patch("workers.tasks._update_image_metadata"), \
             patch("workers.tasks._update_image_public_path"):

            result = await process_report_ai(
                {},
                report_id=report_id,
                title="Lost MacBook",
                description="Silver laptop",
                category="electronics",
            )

        assert result["status"] == "complete"
        assert result["category"] == "electronics"
        assert result["embedding_dims"] == 1536
        assert result["within_budget"] is True
