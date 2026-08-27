"""Sprint 1 smoke tests — health + report intake (DB mocked for create)."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["AUTH_DEV_BYPASS"] = "true"
os.environ["ARQ_WORKER_ENABLED"] = "false"
try:
    from infrastructure.config import get_settings

    get_settings.cache_clear()
except Exception:
    pass

from api.main import create_app  # noqa: E402
from services.report_service import ReportRecord  # noqa: E402


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in ("ok", "degraded")
    assert body["components"]["api"] == "online"


def test_login_dev_bypass(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "password"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["mode"] == "dev_bypass"


def test_register_dev_bypass(client):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "secret12",
            "display_name": "New User",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "newuser@example.com"
    assert body["access_token"]
    assert body["mode"] == "dev_bypass"
    assert body["requires_email_confirmation"] is False


def test_create_report_202(client):
    rid = uuid4()
    fake = ReportRecord(
        id=rid,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        report_type="LOST",
        category="electronics",
        title="Black laptop",
        description="Dell XPS with sticker",
        status="pending",
        latitude=6.9271,
        longitude=79.8612,
        location_label=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    with patch(
        "api.routers.reports.report_service.create_report", return_value=fake
    ):
        res = client.post(
            "/api/v1/reports",
            json={
                "report_type": "LOST",
                "category": "electronics",
                "title": "Black laptop",
                "description": "Dell XPS with sticker",
                "latitude": 6.9271,
                "longitude": 79.8612,
            },
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "pending"
    assert body["report_id"] == str(rid)
