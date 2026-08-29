"""Sprint 5–6 core path tests — fraud gate, verify decide, admin REVIEW."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["AUTH_DEV_BYPASS"] = "true"
os.environ["AUTH_DEV_ROLE"] = "admin"
os.environ["ARQ_WORKER_ENABLED"] = "false"
try:
    from infrastructure.config import get_settings

    get_settings.cache_clear()
except Exception:
    pass

from api.main import create_app  # noqa: E402
from pipelines.fraud_pipeline import check_fraud_gate  # noqa: E402
from pipelines.fusion import compute_fusion_score, score_band  # noqa: E402
from pipelines.verification_pipeline import _decide  # noqa: E402
from services.admin_service import ReviewDetail, ReviewQueueItem  # noqa: E402


# ---------------------------------------------------------------------------
# Fusion / verify decision thresholds
# ---------------------------------------------------------------------------

def test_fusion_high_band():
    result = compute_fusion_score(
        vision_score=1.0, text_score=1.0, geo_score=1.0, category_score=1.0
    )
    assert result["band"] == "HIGH"
    assert result["score"] >= 0.80


def test_fusion_medium_band():
    result = compute_fusion_score(
        vision_score=0.6, text_score=0.6, geo_score=0.5, category_score=0.5
    )
    assert result["band"] == "MEDIUM"


def test_score_band_boundaries():
    assert score_band(0.80) == "HIGH"
    assert score_band(0.50) == "MEDIUM"
    assert score_band(0.49) == "LOW"


def test_verify_decide_pass_review_block():
    # Thresholds from param.yaml verify.pass_threshold / block_threshold (0.60 / 0.30)
    assert _decide(0.85) == "PASS"
    assert _decide(0.60) == "PASS"
    assert _decide(0.45) == "REVIEW"
    assert _decide(0.30) == "REVIEW"
    assert _decide(0.10) == "BLOCK"


@pytest.mark.asyncio
async def test_score_answers_empty_hints_force_review_not_point_four():
    """Regression: stub questions must not invent semantic scores of 0.4."""
    from pipelines.verification_pipeline import _stub_questions, score_answers

    stubs = _stub_questions(3)
    assert all(not (q.get("expected_hint") or "").strip() for q in stubs)

    result = await score_answers(
        questions=stubs,
        answers=["Fair condition", "small tear", "red zipper"],
        report_id="test-report",
    )
    assert result["decision"] == "REVIEW"
    assert result["unscored"] is True
    assert result["overall_score"] is None
    assert all(s is None for s in result["semantic_scores"])
    assert result["semantic_scores"] != [0.4, 0.4, 0.4]


def test_questions_from_features_include_hints():
    from pipelines.verification_pipeline import _questions_from_features

    qs = _questions_from_features(
        {"brand": "Nike", "colors": ["black", "red"], "unique_mark": "tear bottom-left"},
        3,
    )
    assert len(qs) == 3
    assert all((q.get("expected_hint") or "").strip() for q in qs)
    assert any("Nike" in q["expected_hint"] for q in qs)


def test_normalize_questions_rejects_character_split_string():
    """Regression: list(str) must not become per-char 'questions'."""
    from pipelines.verification_pipeline import _normalize_question_list

    assert _normalize_question_list("I", 3) == []
    good = _normalize_question_list(
        {
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What is on the sticker?",
                    "feature_key": "sticker",
                    "expected_hint": "CS101",
                }
            ]
        },
        3,
    )
    assert len(good) == 1
    assert good[0]["question"].startswith("What")


def test_normalize_questions_accepts_list_of_dicts():
    from pipelines.verification_pipeline import _normalize_question_list

    out = _normalize_question_list(
        [
            {"question": "Color of the case?", "expected_hint": "blue"},
            {"question": "Any cracks?", "expected_hint": "bottom left"},
        ],
        3,
    )
    assert len(out) == 2
    assert out[0]["question_id"] == "q1"


# ---------------------------------------------------------------------------
# Fraud gate (mocked DB trust row)
# ---------------------------------------------------------------------------

def test_fraud_gate_allows_fresh_user():
    fake = {
        "score": 1.0,
        "claim_count_24h": 0,
        "fail_count": 0,
        "lockout_until": None,
    }
    with patch("pipelines.fraud_pipeline._get_or_create_trust", return_value=fake):
        out = check_fraud_gate(uuid4())
    assert out["allowed"] is True
    assert out["risk_score"] < 0.5


def test_fraud_gate_blocks_velocity():
    fake = {
        "score": 1.0,
        "claim_count_24h": 3,
        "fail_count": 0,
        "lockout_until": None,
    }
    with patch("pipelines.fraud_pipeline._get_or_create_trust", return_value=fake):
        out = check_fraud_gate(uuid4())
    assert out["allowed"] is False
    assert "Too many" in out["reason"]


def test_fraud_gate_blocks_lockout():
    until = datetime.now(tz=timezone.utc) + timedelta(hours=12)
    fake = {
        "score": 0.2,
        "claim_count_24h": 1,
        "fail_count": 3,
        "lockout_until": until,
    }
    with patch("pipelines.fraud_pipeline._get_or_create_trust", return_value=fake):
        out = check_fraud_gate(uuid4())
    assert out["allowed"] is False
    assert "locked" in out["reason"].lower()


# ---------------------------------------------------------------------------
# Admin API (mocked service layer)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_admin_queue_lists_reviews(client):
    claim_id = uuid4()
    item = ReviewQueueItem(
        claim_attempt_id=claim_id,
        verification_session_id=uuid4(),
        match_id=uuid4(),
        claimant_id=uuid4(),
        claimant_email="owner@example.com",
        status="review",
        risk_score=0.4,
        fraud_risk=0.45,
        overall_score=0.42,
        decision="REVIEW",
        found_report_title="Laptop with sticker",
        created_at=datetime.now(tz=timezone.utc),
    )
    with patch("services.admin_service.list_review_queue", return_value=[item]):
        res = client.get(
            "/api/v1/admin/reviews",
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["items"][0]["claim_attempt_id"] == str(claim_id)
    assert body["items"][0]["status"] == "review"


def test_admin_detail_includes_vault_and_public(client):
    claim_id = uuid4()
    detail = ReviewDetail(
        claim_attempt_id=claim_id,
        verification_session_id=uuid4(),
        match_id=uuid4(),
        claimant_id=uuid4(),
        claimant_email="owner@example.com",
        claimant_emergency_contact="+94770000000",
        status="review",
        risk_score=0.4,
        fraud_risk=0.45,
        overall_score=0.42,
        decision="REVIEW",
        questions=[{"question_id": "q1", "question": "Sticker text?", "expected_hint": "CS101"}],
        answers=["CS101"],
        semantic_scores=[0.9],
        vault_features={"sticker_text": "CS101"},
        public_image_url="https://example.com/public.jpg",
        vault_image_url="https://example.com/vault-signed.jpg",
        found_report_id=uuid4(),
        lost_report_id=uuid4(),
        found_report_title="Laptop",
        owner_email="finder@example.com",
        owner_emergency_contact="+94771111111",
        created_at=datetime.now(tz=timezone.utc),
        completed_at=None,
    )
    with patch("services.admin_service.get_review_detail", return_value=detail):
        res = client.get(
            f"/api/v1/admin/reviews/{claim_id}",
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["public_image_url"].endswith("public.jpg")
    assert body["vault_image_url"].endswith("vault-signed.jpg")
    assert body["vault_features"]["sticker_text"] == "CS101"


def test_admin_decide_pass(client):
    claim_id = uuid4()
    chat_id = uuid4()
    with patch(
        "services.admin_service.decide_review",
        return_value={
            "claim_attempt_id": str(claim_id),
            "decision": "PASS",
            "status": "passed",
            "chat_room_id": str(chat_id),
        },
    ), patch(
        "services.user_service.ensure_app_user",
        return_value=UUID("00000000-0000-0000-0000-000000000001"),
    ):
        res = client.post(
            f"/api/v1/admin/reviews/{claim_id}/decide",
            headers={"Authorization": "Bearer dev"},
            json={"decision": "PASS", "note": "Looks legit"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "PASS"
    assert body["chat_room_id"] == str(chat_id)


def test_admin_decide_block(client):
    claim_id = uuid4()
    with patch(
        "services.admin_service.decide_review",
        return_value={
            "claim_attempt_id": str(claim_id),
            "decision": "BLOCK",
            "status": "blocked",
            "chat_room_id": None,
        },
    ), patch(
        "services.user_service.ensure_app_user",
        return_value=UUID("00000000-0000-0000-0000-000000000001"),
    ):
        res = client.post(
            f"/api/v1/admin/reviews/{claim_id}/decide",
            headers={"Authorization": "Bearer dev"},
            json={"decision": "BLOCK"},
        )
    assert res.status_code == 200
    assert res.json()["decision"] == "BLOCK"


def test_claim_status_includes_chat_room_after_pass(client):
    attempt_id = uuid4()
    match_id = uuid4()
    room_id = uuid4()
    with patch(
        "services.claim_service.get_claim_status",
        return_value={
            "id": attempt_id,
            "match_id": match_id,
            "claimant_id": uuid4(),
            "status": "passed",
            "decision": "PASS",
            "risk_score": 0.2,
            "fraud_risk": 0.1,
            "chat_room_id": room_id,
            "created_at": datetime.now(tz=timezone.utc),
        },
    ), patch(
        "services.user_service.ensure_app_user",
        return_value=UUID("00000000-0000-0000-0000-000000000001"),
    ):
        res = client.get(
            f"/api/v1/claims/{attempt_id}/status",
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "passed"
    assert body["decision"] == "PASS"
    assert body["chat_room_id"] == str(room_id)


def test_chat_room_by_match(client):
    from services.chat_service import ChatRoomRecord

    match_id = uuid4()
    room_id = uuid4()
    owner = UUID("00000000-0000-0000-0000-000000000001")
    room = ChatRoomRecord(
        id=room_id,
        match_id=match_id,
        owner_id=owner,
        finder_id=uuid4(),
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
    )
    with patch("services.chat_service.get_room_by_match", return_value=room), patch(
        "services.user_service.ensure_app_user",
        return_value=owner,
    ):
        res = client.get(
            f"/api/v1/chat/rooms/by-match/{match_id}",
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    assert res.json()["room_id"] == str(room_id)


def test_assert_room_member_accepts_str_uuid():
    from services.chat_service import ChatRoomRecord, assert_room_member

    owner = uuid4()
    room = ChatRoomRecord(
        id=uuid4(),
        match_id=uuid4(),
        owner_id=str(owner),  # type: ignore[arg-type]
        finder_id=uuid4(),
        is_active=True,
        created_at=None,
    )
    assert_room_member(room, owner)


def test_admin_detail_404(client):
    with patch("services.admin_service.get_review_detail", return_value=None):
        res = client.get(
            f"/api/v1/admin/reviews/{uuid4()}",
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 404


def test_login_dev_bypass_returns_admin_role(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "admin"


def test_health_still_green(client):
    res = client.get("/health")
    assert res.status_code == 200


def test_observability_observe_noop_without_keys():
    from infrastructure.observability import flush, observe

    @observe(name="unit_test_span")
    def _fn(x: int) -> int:
        return x + 1

    assert _fn(1) == 2
    flush()  # must not raise


def test_signed_vault_url_none_on_empty():
    from infrastructure.storage.image_storage import signed_vault_url

    assert signed_vault_url(None) is None
    assert signed_vault_url("") is None
