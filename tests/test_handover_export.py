"""Handover hide + admin CSV export."""

from __future__ import annotations

import os
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("AUTH_DEV_BYPASS", "true")
os.environ.setdefault("AUTH_DEV_ROLE", "admin")
os.environ.setdefault("ARQ_WORKER_ENABLED", "false")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_handover_complete_endpoint():
    room_id = uuid4()
    match_id = uuid4()
    with patch(
        "services.chat_service.complete_handover",
        return_value={
            "room_id": str(room_id),
            "match_id": str(match_id),
            "already_complete": False,
            "message": "Handover complete — posts are hidden from the public.",
        },
    ):
        res = client.post(
            f"/api/v1/chat/rooms/{room_id}/handover-complete",
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["match_id"] == str(match_id)
    assert "hidden" in body["message"].lower()


def test_admin_export_kinds():
    csv_body = "report_id,report_type\nr1,LOST\n"
    with patch(
        "api.routers.admin._build_export_csv",
        return_value=(csv_body, "verifind_lost_items_test.csv"),
    ):
        res = client.get(
            "/api/v1/admin/export?kind=lost",
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert b"LOST" in res.content
