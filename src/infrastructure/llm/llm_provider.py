"""LLM factory — OpenAI primary."""
from __future__ import annotations

from typing import Any, Optional

from langchain_openai import ChatOpenAI

from infrastructure.config import (
    GROQ_BASE_URL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    OPENROUTER_BASE_URL,
    ROUTER_MODEL,
    ROUTER_PROVIDER,
    VERIFY_MODEL,
    VERIFY_PROVIDER,
    VISION_MODEL,
    VISION_PROVIDER,
    get_api_key,
)


def _build(model: str, provider: str, **kwargs: Any) -> ChatOpenAI:
    opts: dict[str, Any] = {
        "model": model,
        "temperature": kwargs.pop("temperature", LLM_TEMPERATURE),
        "max_tokens": kwargs.pop("max_tokens", LLM_MAX_TOKENS),
        **kwargs,
    }
    if provider == "openrouter":
        opts["openai_api_base"] = OPENROUTER_BASE_URL
        opts["openai_api_key"] = get_api_key("openrouter")
    elif provider == "groq":
        opts["openai_api_base"] = GROQ_BASE_URL
        opts["openai_api_key"] = get_api_key("groq")
    else:
        opts["openai_api_key"] = get_api_key("openai")
    return ChatOpenAI(**opts)


def get_router_llm(**kwargs: Any) -> ChatOpenAI:
    return _build(ROUTER_MODEL, ROUTER_PROVIDER, **kwargs)


def get_vision_llm(**kwargs: Any) -> ChatOpenAI:
    return _build(VISION_MODEL, VISION_PROVIDER, **kwargs)


def get_verify_llm(**kwargs: Any) -> ChatOpenAI:
    return _build(VERIFY_MODEL, VERIFY_PROVIDER, **kwargs)
