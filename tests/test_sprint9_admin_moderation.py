"""Sprint 9 — content strikes, match decide, admin moderation API."""

from __future__ import annotations

import os
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("AUTH_DEV_BYPASS", "true")
os.environ.setdefault("AUTH_DEV_ROLE", "admin")
os.environ.setdefault("ARQ_WORKER_ENABLED", "false")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from services.content_policy import find_prohibited_match  # noqa: E402

client = TestClient(app)


def test_find_prohibited_sexual_and_drugs():
    assert find_prohibited_match("lost phone", "normal") is None
    assert find_prohibited_match(None, "sexual content here") is not None
    assert find_prohibited_match("cocaine bag", None) is not None


def test_admin_match_decide_pass():
    mid = uuid4()
    with patch(
        "services.moderation_service.decide_match",
        return_value={
            "id": mid,
            "admin_status": "approved",
            "band": "HIGH",
            "score": 0.9,
            "notified": True,
        },
    ):
        res = client.post(
            f"/api/v1/admin/suggestions/{mid}/decide",
            headers={"Authorization": "Bearer dev"},
            json={"decision": "PASS", "note": "Looks real"},
        )
    assert res.status_code == 200
    assert res.json()["admin_status"] == "approved"


def test_admin_block_user():
    uid = uuid4()
    with patch(
        "services.moderation_service.set_user_active",
        return_value={"id": uid, "is_active": False, "email": "u@x.com"},
    ):
        res = client.post(
            f"/api/v1/admin/users/{uid}/block",
            headers={"Authorization": "Bearer dev"},
            json={"reason": "3 strikes"},
        )
    assert res.status_code == 200
    assert res.json()["is_active"] is False


def test_admin_reveal_contact_requires_reason():
    uid = uuid4()
    res = client.post(
        f"/api/v1/admin/users/{uid}/reveal-contact",
        headers={"Authorization": "Bearer dev"},
        json={"reason": "ab"},
    )
    assert res.status_code == 422


def test_admin_reveal_contact_ok():
    uid = uuid4()
    with patch(
        "services.moderation_service.reveal_user_contact",
        return_value={
            "user_id": uid,
            "email": "u@x.com",
            "display_name": "U",
            "emergency_contact": "+94770001111",
            "is_active": True,
        },
    ):
        res = client.post(
            f"/api/v1/admin/users/{uid}/reveal-contact",
            headers={"Authorization": "Bearer dev"},
            json={"reason": "Safety investigation"},
        )
    assert res.status_code == 200
    assert res.json()["emergency_contact"] == "+94770001111"
