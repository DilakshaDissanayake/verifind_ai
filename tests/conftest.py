"""Shared fixtures — unit tests must not require a live Supabase .env (CI has none)."""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

os.environ.setdefault("AUTH_DEV_BYPASS", "true")
os.environ.setdefault("AUTH_DEV_ROLE", "admin")
os.environ.setdefault("ARQ_WORKER_ENABLED", "false")

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _mock_db_bound_user_helpers():
    """
    Routers call ensure_app_user (and report create calls assert_user_can_post)
    before service mocks run. Patch both so pytest works without SUPABASE_DB_URL.
    """
    with ExitStack() as stack:
        stack.enter_context(
            patch("services.user_service.ensure_app_user", return_value=DEV_USER_ID)
        )
        # Top-level imports bind a local name — patch those modules too.
        stack.enter_context(
            patch("api.routers.admin.ensure_app_user", return_value=DEV_USER_ID)
        )
        stack.enter_context(
            patch("api.routers.claims.ensure_app_user", return_value=DEV_USER_ID)
        )
        stack.enter_context(
            patch("services.moderation_service.assert_user_can_post", return_value=None)
        )
        yield
