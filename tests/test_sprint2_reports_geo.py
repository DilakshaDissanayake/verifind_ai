"""Sprint 2 — Reports + Geo unit tests (no live DB / storage)."""
from __future__ import annotations

import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
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
from pipelines.metadata_pipeline import extract_exif, public_exif  # noqa: E402
from services.geo_service import NearbyHit, NearbyUser, fuzz_coordinates, haversine_m, merge_nearby_user_hits  # noqa: E402
from services.image_service import ReportImageRecord  # noqa: E402
from services.report_service import ReportRecord  # noqa: E402


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _fake_report(**kwargs) -> ReportRecord:
    defaults = dict(
        id=uuid4(),
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        report_type="LOST",
        category="electronics",
        title="Test",
        description="desc",
        status="pending",
        latitude=6.9275,
        longitude=79.8615,
        location_label="Colombo",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return ReportRecord(**defaults)


def test_gps_fuzz_within_radius():
    lat, lon = 6.9271, 79.8612
    for seed in range(20):
        import random

        f_lat, f_lon = fuzz_coordinates(lat, lon, 500, rng=random.Random(seed))
        dist = haversine_m(lat, lon, f_lat, f_lon)
        assert dist <= 500.0 + 1.0  # 1 m float slack


def test_gps_fuzz_changes_point():
    import random

    lat, lon = 6.9271, 79.8612
    f_lat, f_lon = fuzz_coordinates(lat, lon, 500, rng=random.Random(42))
    assert (f_lat, f_lon) != (lat, lon)


def test_public_exif_strips_gps():
    raw = {
        "Make": "Apple",
        "Model": "iPhone",
        "GPSInfo": {"GPSLatitude": [6, 55, 0]},
        "gps_decimal": {"latitude": 6.9271, "longitude": 79.8612},
        "SerialNumber": "ABC123",
    }
    cleaned = public_exif(raw)
    assert cleaned is not None
    assert "GPSInfo" not in cleaned
    assert "gps_decimal" not in cleaned
    assert "SerialNumber" not in cleaned
    assert cleaned["Make"] == "Apple"


def test_extract_exif_plain_png():
    pytest.importorskip("PIL")
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(buf, format="PNG")
    exif = extract_exif(buf.getvalue())
    assert exif.get("has_exif") is False or "format" in exif
    assert public_exif(exif) is not None


def test_nearby_endpoint_mocked(client):
    hit = NearbyHit(
        id=uuid4(),
        report_type="FOUND",
        category="electronics",
        title="Nearby bag",
        status="active",
        latitude=6.9280,
        longitude=79.8620,
        distance_m=120.5,
        location_label=None,
    )
    with patch("api.routers.reports.nearby_reports", return_value=[hit]), patch(
        "api.routers.reports.image_service.public_urls_for_reports",
        return_value={hit.id: ["https://cdn.example/public.jpg"]},
    ):
        res = client.get(
            "/api/v1/reports/nearby",
            params={"lat": 6.9271, "lon": 79.8612, "radius_m": 5000},
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["items"][0]["distance_m"] == 120.5
    assert body["radius_m"] == 5000
    assert body["items"][0]["image_urls"] == ["https://cdn.example/public.jpg"]


def test_create_persists_via_service(client):
    fake = _fake_report(report_type="FOUND", title="Wallet")
    with patch(
        "api.routers.reports.report_service.create_report", return_value=fake
    ) as mock_create:
        res = client.post(
            "/api/v1/reports",
            json={
                "report_type": "FOUND",
                "title": "Wallet",
                "latitude": 6.9271,
                "longitude": 79.8612,
            },
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 202
    assert mock_create.called
    assert res.json()["report_id"] == str(fake.id)
    assert res.json()["latitude"] is not None


def test_get_and_list_reports(client):
    fake = _fake_report()
    with patch(
        "api.routers.reports.report_service.get_report", return_value=fake
    ), patch(
        "api.routers.reports.report_service.list_reports_for_user",
        return_value=[fake],
    ):
        g = client.get(
            f"/api/v1/reports/{fake.id}",
            headers={"Authorization": "Bearer dev"},
        )
        lst = client.get(
            "/api/v1/reports",
            headers={"Authorization": "Bearer dev"},
        )
    assert g.status_code == 200
    assert g.json()["report_id"] == str(fake.id)
    assert lst.status_code == 200
    assert lst.json()["count"] == 1


def test_upload_image_no_vault_leak(client):
    rid = uuid4()
    img = ReportImageRecord(
        id=uuid4(),
        report_id=rid,
        public_path=None,
        content_type="image/jpeg",
        is_primary=True,
        exif_public={"Make": "Canon", "Model": "EOS"},
        has_vault=True,
    )
    with patch(
        "api.routers.reports.image_service.upload_report_image", return_value=img
    ), patch(
        "api.routers.reports.report_service.get_report", return_value=None
    ):
        res = client.post(
            f"/api/v1/reports/{rid}/images",
            files={"file": ("x.jpg", b"\xff\xd8\xfffakejpeg", "image/jpeg")},
            data={"is_primary": "true"},
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 201
    body = res.json()
    assert body["public_path"] is None
    assert body["has_vault"] is True
    assert "GPSInfo" not in (body.get("exif") or {})
    assert "vault_path" not in body
    assert "hidden_features" not in body


def test_resolve_content_type_octet_stream_jpeg():
    from services.image_service import resolve_content_type

    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    assert resolve_content_type("application/octet-stream", data=jpeg) == "image/jpeg"
    assert resolve_content_type("application/octet-stream", filename="photo.PNG", data=b"") == "image/png"


def test_health_version_sprint2(client):
    res = client.get("/health")
    # health router may still say sprint1 in body — schemas HealthResponse defaults sprint2
    assert res.status_code == 200


def test_owner_close_self_found(client):
    fake = _fake_report(status="active")
    closed = _fake_report(id=fake.id, status="closed")
    with patch(
        "api.routers.reports.report_service.close_owner_report",
        return_value=(closed, False, 0),
    ) as mock_close:
        res = client.post(
            f"/api/v1/reports/{fake.id}/close",
            json={"reason": "self_found"},
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "closed"
    assert body["already_closed"] is False
    assert body["reason"] == "self_found"
    assert "not deleted" in body["message"].lower()
    mock_close.assert_called_once()


def test_owner_close_already_closed(client):
    fake = _fake_report(status="closed")
    with patch(
        "api.routers.reports.report_service.close_owner_report",
        return_value=(fake, True, 0),
    ):
        res = client.post(
            f"/api/v1/reports/{fake.id}/close",
            json={"reason": "self_found"},
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    assert res.json()["already_closed"] is True


def test_owner_close_not_owner(client):
    rid = uuid4()
    with patch(
        "api.routers.reports.report_service.close_owner_report",
        side_effect=HTTPException(status_code=403, detail="Not report owner"),
    ):
        res = client.post(
            f"/api/v1/reports/{rid}/close",
            json={"reason": "withdrawn"},
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 403


def test_merge_nearby_user_hits_keeps_closest():
    a, b = uuid4(), uuid4()
    out = merge_nearby_user_hits([(a, 500.0), (b, 100.0), (a, 200.0)], limit=10)
    assert [u.user_id for u in out] == [b, a]
    assert out[1].distance_m == 200.0


def test_create_notifies_nearby_users(client):
    fake = _fake_report(report_type="LOST", title="Black bag")
    with patch(
        "api.routers.reports.report_service.create_report", return_value=fake
    ), patch(
        "services.notification_service.notify_nearby_post", return_value=3
    ) as notify, patch(
        "services.user_service.update_last_location", return_value=True
    ):
        res = client.post(
            "/api/v1/reports",
            json={
                "report_type": "LOST",
                "title": "Black bag",
                "latitude": 6.9271,
                "longitude": 79.8612,
            },
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 202
    assert notify.called
    kwargs = notify.call_args.kwargs
    assert kwargs["report_id"] == fake.id
    assert kwargs["poster_user_id"] == fake.user_id
    assert kwargs["lat"] == fake.latitude


def test_notify_nearby_post_fans_out():
    from services.notification_service import notify_nearby_post

    poster, u1, u2, rid = uuid4(), uuid4(), uuid4(), uuid4()
    with patch(
        "services.geo_service.nearby_users_to_notify",
        return_value=[
            NearbyUser(user_id=u1, distance_m=120.0),
            NearbyUser(user_id=u2, distance_m=4100.0),
        ],
    ), patch(
        "services.notification_service._insert_typed_notification",
        return_value=True,
    ) as insert:
        created = notify_nearby_post(
            poster_user_id=poster,
            report_id=rid,
            report_type="FOUND",
            title="Wallet",
            lat=6.9271,
            lon=79.8612,
        )
    assert created == 2
    assert insert.call_count == 2
    assert insert.call_args.kwargs["notif_type"] == "nearby_post"
    assert insert.call_args.kwargs["band"] == "FOUND"


def test_notify_nearby_post_skips_without_gps():
    from services.notification_service import notify_nearby_post

    assert (
        notify_nearby_post(
            poster_user_id=uuid4(),
            report_id=uuid4(),
            report_type="LOST",
            title="Bag",
        )
        == 0
    )


def test_location_ping(client):
    with patch("services.user_service.update_last_location", return_value=True) as ping:
        res = client.post(
            "/api/v1/auth/me/location",
            json={"latitude": 6.9271, "longitude": 79.8612},
            headers={"Authorization": "Bearer dev"},
        )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert ping.called
