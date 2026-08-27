"""Langfuse soft-disable wrapper — patterned on Examples observability.

Provides get_langfuse / get_tracer / observe / update helpers / flush.
When observability is off or keys missing, all helpers are no-ops.
"""

from __future__ import annotations

import os
from typing import Optional

from loguru import logger

_client = None
_ready = False
_lf_observe = None
_get_lf_client = None

try:
    from langfuse import observe as _lf_observe  # type: ignore
    from langfuse import get_client as _get_lf_client  # type: ignore
except ImportError:
    logger.debug("langfuse package not installed — @observe is a no-op")


def _is_enabled() -> bool:
    try:
        from infrastructure.config import OBSERVABILITY_ENABLED

        return bool(OBSERVABILITY_ENABLED)
    except Exception:
        return True


def get_langfuse():
    global _client, _ready
    if _ready:
        return _client
    _ready = True
    if not _is_enabled():
        logger.info("Langfuse disabled via config")
        return None
    sk, pk = os.getenv("LANGFUSE_SECRET_KEY"), os.getenv("LANGFUSE_PUBLIC_KEY")
    if not sk or not pk:
        logger.info("Langfuse disabled (no keys)")
        return None
    try:
        from langfuse import Langfuse

        host = (
            os.getenv("LANGFUSE_HOST")
            or os.getenv("LANGFUSE_BASE_URL")
            or "https://cloud.langfuse.com"
        )
        _client = Langfuse(secret_key=sk, public_key=pk, host=host)
        logger.info("Langfuse client initialised (host={})", host)
        return _client
    except Exception as exc:
        logger.warning("Langfuse init failed: {}", exc)
        return None


def get_tracer():
    """Return Langfuse client for tracing, or None when disabled/unavailable."""
    return get_langfuse()


def observe(
    *,
    name: Optional[str] = None,
    as_type: Optional[str] = None,
):
    """Decorator wrapping langfuse.observe — no-op when disabled or no keys."""

    def _noop(fn):
        return fn

    if not _is_enabled() or _lf_observe is None:
        return _noop
    # Avoid initializing a broken client when keys are absent
    if not (os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY")):
        return _noop

    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if as_type is not None:
        kwargs["as_type"] = as_type
    return _lf_observe(**kwargs)


def update_current_trace(
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list] = None,
) -> None:
    if _get_lf_client is None or not _is_enabled():
        return
    try:
        client = _get_lf_client()
        kwargs = {}
        if user_id is not None:
            kwargs["user_id"] = user_id
        if session_id is not None:
            kwargs["session_id"] = session_id
        if metadata is not None:
            kwargs["metadata"] = metadata
        if tags is not None:
            kwargs["tags"] = tags
        client.update_current_trace(**kwargs)
    except Exception as exc:
        logger.debug("update_current_trace failed: {}", exc)


def update_current_observation(
    *,
    input: Optional[str] = None,
    output: Optional[str] = None,
    metadata: Optional[dict] = None,
    usage: Optional[dict] = None,
    model: Optional[str] = None,
) -> None:
    if _get_lf_client is None or not _is_enabled():
        return
    try:
        client = _get_lf_client()
        if usage is not None or model is not None:
            gen_kwargs = {}
            if input is not None:
                gen_kwargs["input"] = input
            if output is not None:
                gen_kwargs["output"] = output
            if metadata is not None:
                gen_kwargs["metadata"] = metadata
            if model is not None:
                gen_kwargs["model"] = model
            if usage is not None:
                gen_kwargs["usage_details"] = usage
            try:
                client.update_current_generation(**gen_kwargs)
                return
            except Exception:
                pass
        span_kwargs = {}
        if input is not None:
            span_kwargs["input"] = input
        if output is not None:
            span_kwargs["output"] = output
        if metadata is not None:
            span_kwargs["metadata"] = metadata
        if span_kwargs:
            client.update_current_span(**span_kwargs)
    except Exception as exc:
        logger.debug("update_current_observation failed: {}", exc)


def flush() -> None:
    """Flush pending Langfuse events (call on shutdown)."""
    if not _is_enabled():
        return
    client = get_langfuse()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.debug("Langfuse flush failed: {}", exc)
