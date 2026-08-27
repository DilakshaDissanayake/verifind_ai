"""Stateful circuit breaker — Closed → Open → Half-Open (graceful degradation)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Per-provider breaker used by the multi-provider LLM failover chain."""

    name: str
    failure_threshold: int = 3
    recovery_timeout_s: float = 60.0
    _state: CircuitState = CircuitState.CLOSED
    _failures: int = 0
    _opened_at: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def allow(self) -> bool:
        with self._lock:
            if self._state is CircuitState.CLOSED:
                return True
            if self._state is CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.recovery_timeout_s:
                    self._state = CircuitState.HALF_OPEN
                    return True
                return False
            # HALF_OPEN — allow one probe
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state is CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()

    def status(self) -> dict[str, Any]:
        with self._lock:
            remaining = 0.0
            if self._state is CircuitState.OPEN:
                remaining = max(
                    0.0,
                    self.recovery_timeout_s - (time.monotonic() - self._opened_at),
                )
            return {
                "name": self.name,
                "state": self._state.value,
                "failures": self._failures,
                "recovery_remaining_s": round(remaining, 1),
            }


_REGISTRY: dict[str, CircuitBreaker] = {}
_REG_LOCK = threading.Lock()


def get_breaker(
    name: str,
    *,
    failure_threshold: int = 3,
    recovery_timeout_s: float = 60.0,
) -> CircuitBreaker:
    with _REG_LOCK:
        br = _REGISTRY.get(name)
        if br is None:
            br = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout_s=recovery_timeout_s,
            )
            _REGISTRY[name] = br
        return br


def all_breaker_status() -> dict[str, Any]:
    with _REG_LOCK:
        return {k: v.status() for k, v in _REGISTRY.items()}


def reset_breakers() -> None:
    """Test helper — clear registry."""
    with _REG_LOCK:
        _REGISTRY.clear()
