"""Unit tests — circuit breaker + multi-provider failover chain."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("AUTH_DEV_BYPASS", "true")
os.environ.setdefault("OPENAI_API_KEY", "test-openai")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter")


def test_circuit_opens_after_threshold():
    from infrastructure.llm.circuit_breaker import CircuitBreaker, CircuitState, reset_breakers

    reset_breakers()
    br = CircuitBreaker(name="t", failure_threshold=3, recovery_timeout_s=30)
    assert br.allow() is True
    br.record_failure()
    br.record_failure()
    assert br._state is CircuitState.CLOSED
    br.record_failure()
    assert br._state is CircuitState.OPEN
    assert br.allow() is False
    br.record_success()
    assert br._state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_failover_skips_open_circuit_uses_next_provider():
    from infrastructure.llm.circuit_breaker import get_breaker, reset_breakers
    from infrastructure.llm.llm_provider import chat_completions_with_failover

    reset_breakers()
    openai_br = get_breaker("vision:openai", failure_threshold=1, recovery_timeout_s=120)
    openai_br.record_failure()  # force OPEN

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"category":"bag","confidence":0.5}'}}]
    }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return mock_resp

    with patch("httpx.AsyncClient", return_value=_Client()):
        # Force chain openai → openrouter
        with patch(
            "infrastructure.llm.llm_provider.fallback_chain_for",
            return_value=["openai", "openrouter"],
        ):
            out = await chat_completions_with_failover(
                role="vision",
                messages=[{"role": "user", "content": "hi"}],
            )

    assert out["provider"] == "openrouter"
    assert out["degraded"] is True
    assert "category" in out["content"]
