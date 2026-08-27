"""LLM factory with Context-Aware Graceful Degradation (circuit breaker + multi-provider failover).

Chain (configurable): OpenAI → OpenRouter (Gemini/Claude models) → Groq → Ollama local.
When a provider fails (timeout / 429 / 5xx), its circuit opens and the next provider is tried.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from loguru import logger

from infrastructure.config import (
    GROQ_BASE_URL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    MODELS,
    OPENROUTER_BASE_URL,
    PARAMS,
    ROUTER_MODEL,
    ROUTER_PROVIDER,
    VERIFY_MODEL,
    VERIFY_PROVIDER,
    VISION_MODEL,
    VISION_PROVIDER,
    get_api_key,
    _nested,
)
from infrastructure.llm.circuit_breaker import all_breaker_status, get_breaker


def _resilience() -> dict[str, Any]:
    return PARAMS.get("resilience") or {}


def _failure_threshold() -> int:
    return int(_resilience().get("failure_threshold", 3))


def _recovery_timeout_s() -> float:
    return float(_resilience().get("recovery_timeout_s", 60))


def _call_timeout_s() -> float:
    return float(_resilience().get("call_timeout_s", 20))


def fallback_chain_for(role: str) -> list[str]:
    """Ordered provider names for a role (vision | verify | router | embed)."""
    chain = _nested(_resilience(), "fallback_chain", role, default=None)
    if isinstance(chain, list) and chain:
        return [str(p) for p in chain]
    # Defaults aligned with WRIT1 / models.yaml
    defaults = {
        "vision": ["openai", "openrouter", "ollama"],
        "verify": ["openai", "openrouter", "ollama"],
        "router": ["openai", "openrouter", "groq"],
        "embed": ["openai", "openrouter"],
    }
    return defaults.get(role, ["openai", "openrouter"])


def _ollama_base() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")


def _model_for(provider: str, role: str) -> str:
    """Resolve model id for provider + role from models.yaml (+ ollama env)."""
    section = {
        "router": "chat",
        "vision": "vision",
        "verify": "verify",
        "embed": "embedding",
    }.get(role, "chat")
    tier = "strong" if role == "verify" else "general"
    if role == "embed":
        tier = "small"

    if provider == "ollama":
        env_key = {
            "vision": "OLLAMA_VISION_MODEL",
            "verify": "OLLAMA_VERIFY_MODEL",
            "router": "OLLAMA_CHAT_MODEL",
            "embed": "OLLAMA_EMBED_MODEL",
        }.get(role, "OLLAMA_CHAT_MODEL")
        return os.getenv(env_key, "llava" if role == "vision" else "llama3.2")

    if provider == "openrouter":
        # Prefer OpenRouter catalog entries that map to Gemini / Claude / OpenAI
        model = _nested(MODELS, "openrouter", section, tier)
        if not model and section == "vision":
            model = _nested(MODELS, "openrouter", "chat", "general")
        if not model and section == "verify":
            model = _nested(MODELS, "openrouter", "chat", "strong")
        return model or "openai/gpt-4o-mini"

    if provider in ("google", "gemini"):
        model = _nested(MODELS, "google", section if section != "verify" else "chat", tier)
        return model or "gemini-2.5-flash"

    if provider == "anthropic":
        model = _nested(MODELS, "anthropic", "chat" if section != "verify" else "verify", tier)
        return model or "claude-3-5-sonnet-20241022"

    if provider == "groq":
        return os.getenv("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")

    # openai native
    model = _nested(MODELS, "openai", section, tier)
    if not model and section == "vision":
        model = _nested(MODELS, "openai", "chat", "general")
    if not model and section == "verify":
        model = _nested(MODELS, "openai", "verify", "strong")
    return model or ("gpt-4o" if role == "verify" else "gpt-4o-mini")


def _endpoint_for(provider: str) -> tuple[Optional[str], Optional[str]]:
    """Return (base_url, api_key) for an OpenAI-compatible chat client."""
    if provider == "openai":
        return None, get_api_key("openai")
    if provider == "openrouter":
        return OPENROUTER_BASE_URL, get_api_key("openrouter")
    if provider == "groq":
        return GROQ_BASE_URL, get_api_key("groq")
    if provider == "ollama":
        # Ollama OpenAI-compatible API — key ignored but required by client
        return _ollama_base(), os.getenv("OLLAMA_API_KEY", "ollama")
    if provider in ("google", "gemini"):
        # Prefer OpenRouter if no native Google OpenAI base configured
        base = os.getenv("GOOGLE_OPENAI_BASE_URL")
        key = get_api_key("google")
        if base and key:
            return base, key
        return OPENROUTER_BASE_URL, get_api_key("openrouter")
    if provider == "anthropic":
        base = os.getenv("ANTHROPIC_OPENAI_BASE_URL")
        key = get_api_key("anthropic")
        if base and key:
            return base, key
        return OPENROUTER_BASE_URL, get_api_key("openrouter")
    return None, get_api_key(provider)


def _build(model: str, provider: str, **kwargs: Any) -> ChatOpenAI:
    opts: dict[str, Any] = {
        "model": model,
        "temperature": kwargs.pop("temperature", LLM_TEMPERATURE),
        "max_tokens": kwargs.pop("max_tokens", LLM_MAX_TOKENS),
        **kwargs,
    }
    base, key = _endpoint_for(provider)
    if base:
        opts["openai_api_base"] = base
    opts["openai_api_key"] = key or "missing-key"
    return ChatOpenAI(**opts)


def get_router_llm(**kwargs: Any) -> ChatOpenAI:
    return _build(ROUTER_MODEL, ROUTER_PROVIDER, **kwargs)


def get_vision_llm(**kwargs: Any) -> ChatOpenAI:
    return _build(VISION_MODEL, VISION_PROVIDER, **kwargs)


def get_verify_llm(**kwargs: Any) -> ChatOpenAI:
    return _build(VERIFY_MODEL, VERIFY_PROVIDER, **kwargs)


def resilience_status() -> dict[str, Any]:
    """Snapshot for /health — circuit states + configured chains."""
    return {
        "fallback_chains": {
            "vision": fallback_chain_for("vision"),
            "verify": fallback_chain_for("verify"),
            "router": fallback_chain_for("router"),
        },
        "breakers": all_breaker_status(),
        "call_timeout_s": _call_timeout_s(),
        "failure_threshold": _failure_threshold(),
        "recovery_timeout_s": _recovery_timeout_s(),
    }


async def chat_completions_with_failover(
    *,
    role: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 800,
    temperature: float = 0.0,
    timeout_s: Optional[float] = None,
) -> dict[str, Any]:
    """Try providers in the role fallback chain; skip open circuits.

    Returns:
        { content, provider, model, degraded: bool }
    Raises RuntimeError if every provider fails (caller may use local heuristic).
    """
    import httpx

    timeout = timeout_s if timeout_s is not None else _call_timeout_s()
    errors: list[str] = []

    for provider in fallback_chain_for(role):
        breaker = get_breaker(
            f"{role}:{provider}",
            failure_threshold=_failure_threshold(),
            recovery_timeout_s=_recovery_timeout_s(),
        )
        if not breaker.allow():
            logger.info("circuit OPEN — skip {}:{}", role, provider)
            errors.append(f"{provider}:circuit_open")
            continue

        base, api_key = _endpoint_for(provider)
        if not api_key or api_key == "missing-key":
            # Ollama still usable with placeholder key
            if provider != "ollama":
                errors.append(f"{provider}:no_api_key")
                continue

        model = _model_for(provider, role)
        # When google/anthropic fall through to OpenRouter, remap model ids
        if provider in ("google", "gemini") and base == OPENROUTER_BASE_URL:
            model = _nested(MODELS, "openrouter", "vision" if role == "vision" else "chat", "general") or "google/gemini-2.5-flash"
        if provider == "anthropic" and base == OPENROUTER_BASE_URL:
            model = _nested(MODELS, "openrouter", "chat", "strong") or "anthropic/claude-3.5-sonnet"

        url = f"{(base or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter" or (
            provider in ("google", "gemini", "anthropic") and base == OPENROUTER_BASE_URL
        ):
            headers["HTTP-Referer"] = os.getenv("OPENROUTER_REFERER", "https://verifind.local")
            headers["X-Title"] = "VERIFIND AI"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in (429, 500, 502, 503, 504):
                    breaker.record_failure()
                    errors.append(f"{provider}:http_{resp.status_code}")
                    logger.warning(
                        "LLM failover: {}:{} HTTP {} — circuit failures={}",
                        role,
                        provider,
                        resp.status_code,
                        breaker.status()["failures"],
                    )
                    continue
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                breaker.record_success()
                primary = fallback_chain_for(role)[0]
                degraded = provider != primary
                if degraded:
                    logger.warning(
                        "graceful degradation: role={} using provider={} model={}",
                        role,
                        provider,
                        model,
                    )
                return {
                    "content": content,
                    "provider": provider,
                    "model": model,
                    "degraded": degraded,
                }
        except Exception as exc:
            breaker.record_failure()
            errors.append(f"{provider}:{type(exc).__name__}")
            logger.warning("LLM failover: {}:{} failed: {}", role, provider, exc)
            continue

    raise RuntimeError(
        f"All LLM providers failed for role={role}: {'; '.join(errors) or 'none'}"
    )


__all__ = [
    "get_router_llm",
    "get_vision_llm",
    "get_verify_llm",
    "chat_completions_with_failover",
    "fallback_chain_for",
    "resilience_status",
]
