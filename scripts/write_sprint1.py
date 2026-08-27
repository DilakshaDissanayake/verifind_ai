# -*- coding: utf-8 -*-
"""Write a consistent Sprint-1 tree. Run from repo root: python scripts/write_sprint1.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def w(rel: str, text: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.lstrip("\n"), encoding="utf-8")
    print("wrote", rel)


# --- config ---
w(
    "src/infrastructure/config.py",
    r'''
"""Application configuration — YAML params + env secrets."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def _load_yaml(name: str) -> Dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _nested(d: Any, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return default if cur is None else cur


PARAMS = _load_yaml("param.yaml")
MODELS = _load_yaml("models.yaml")

PROVIDER = _nested(PARAMS, "provider", "default", default="openai")
MODEL_TIER = _nested(PARAMS, "provider", "tier", default="general")
OPENROUTER_BASE_URL = _nested(
    PARAMS, "provider", "openrouter_base_url", default="https://openrouter.ai/api/v1"
)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
EMBEDDING_DIM = int(_nested(PARAMS, "embedding", "dim", default=1536))


def get_role_model(role: str) -> tuple[str, str]:
    cfg = _nested(MODELS, "roles", role, default={}) or {}
    provider = cfg.get("provider") or PROVIDER
    tier = cfg.get("tier") or MODEL_TIER
    section = {"router": "chat", "vision": "vision", "verify": "verify", "embed": "embedding"}.get(role, "chat")
    model = _nested(MODELS, provider, section, tier)
    if not model and section == "vision":
        model = _nested(MODELS, provider, "chat", tier)
    if not model and section == "verify":
        model = _nested(MODELS, provider, "chat", "strong")
    if not model:
        model = "gpt-4o-mini" if role != "embed" else "text-embedding-3-small"
    return provider, model


ROUTER_PROVIDER, ROUTER_MODEL = get_role_model("router")
VISION_PROVIDER, VISION_MODEL = get_role_model("vision")
VERIFY_PROVIDER, VERIFY_MODEL = get_role_model("verify")
EMBED_PROVIDER, EMBEDDING_MODEL = get_role_model("embed")

LLM_TEMPERATURE = float(_nested(PARAMS, "llm", "temperature", default=0.0))
LLM_MAX_TOKENS = int(_nested(PARAMS, "llm", "max_tokens", default=2000))

FUSION_WEIGHTS = {
    "vision": float(_nested(PARAMS, "fusion", "vision", default=0.30)),
    "text": float(_nested(PARAMS, "fusion", "text", default=0.30)),
    "geo": float(_nested(PARAMS, "fusion", "geo", default=0.25)),
    "category": float(_nested(PARAMS, "fusion", "category", default=0.15)),
}
MATCH_HIGH = float(_nested(PARAMS, "match", "high_threshold", default=0.80))
MATCH_MEDIUM = float(_nested(PARAMS, "match", "medium_threshold", default=0.50))
GEO_RADIUS_M = int(_nested(PARAMS, "match", "geo_radius_m", default=5000))
FRAUD = {
    "claim_velocity_max": int(_nested(PARAMS, "fraud", "claim_velocity_max", default=3)),
    "claim_velocity_window_h": int(_nested(PARAMS, "fraud", "claim_velocity_window_h", default=24)),
    "fail_lockout_count": int(_nested(PARAMS, "fraud", "fail_lockout_count", default=3)),
    "fail_lockout_h": int(_nested(PARAMS, "fraud", "fail_lockout_h", default=24)),
    "risk_pass": float(_nested(PARAMS, "fraud", "risk_pass", default=0.3)),
    "risk_review": float(_nested(PARAMS, "fraud", "risk_review", default=0.7)),
}
GPS_FUZZ_METERS = int(_nested(PARAMS, "gps", "fuzz_meters", default=500))
BLUR_SIGMA = float(_nested(PARAMS, "sanitization", "blur_sigma", default=15))

LOGS_DIR = PROJECT_ROOT / _nested(PARAMS, "paths", "logs_dir", default="logs")
LOGGING_ENABLED = bool(_nested(PARAMS, "logging", "enabled", default=True))
LOG_LEVEL = _nested(PARAMS, "logging", "level", default="INFO")
OBSERVABILITY_ENABLED = bool(_nested(PARAMS, "observability", "enabled", default=True))
STORAGE_PUBLIC_BUCKET = os.getenv(
    "STORAGE_PUBLIC_BUCKET", _nested(PARAMS, "paths", "public_bucket", default="public-sanitized")
)
STORAGE_VAULT_BUCKET = os.getenv(
    "STORAGE_VAULT_BUCKET", _nested(PARAMS, "paths", "vault_bucket", default="private-vault")
)


def get_log_level() -> str:
    return (os.getenv("LOG_LEVEL") or LOG_LEVEL).upper()


def get_api_key(provider: Optional[str] = None) -> Optional[str]:
    provider = provider or PROVIDER
    mapping = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    return os.getenv(mapping.get(provider, f"{provider.upper()}_API_KEY"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_db_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    arq_worker_enabled: bool = False
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    auth_dev_bypass: bool = True
    auth_dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    auth_dev_email: str = "dev@verifind.local"

    @property
    def cors_origin_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    def b(name: str, default: str = "false") -> bool:
        return os.getenv(name, default).lower() in ("1", "true", "yes")

    return Settings(
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        api_reload=b("API_RELOAD", "true"),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", ""),
        supabase_db_url=os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        arq_worker_enabled=b("ARQ_WORKER_ENABLED", "false"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        auth_dev_bypass=b("AUTH_DEV_BYPASS", "true"),
        auth_dev_user_id=os.getenv("AUTH_DEV_USER_ID", "00000000-0000-0000-0000-000000000001"),
        auth_dev_email=os.getenv("AUTH_DEV_EMAIL", "dev@verifind.local"),
    )
''',
)

w(
    "src/infrastructure/log.py",
    r'''
"""Loguru setup."""
from __future__ import annotations

import logging
import sys

from loguru import logger

from infrastructure.config import LOGGING_ENABLED, LOGS_DIR, get_log_level

_CONFIGURED = False


def _patch(record: dict) -> None:
    record["extra"].setdefault("name", record["name"])


class _Intercept(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.bind(name=record.name).opt(exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED or not LOGGING_ENABLED:
        _CONFIGURED = True
        return
    level = get_log_level()
    logger.remove()
    logger.configure(patcher=_patch)
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{extra[name]}</cyan> | <level>{message}</level>",
        colorize=True,
    )
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(LOGS_DIR / "app_{time:YYYY-MM-DD}.log", level="DEBUG", rotation="00:00", retention="14 days")
    logging.basicConfig(handlers=[_Intercept()], level=0, force=True)
    _CONFIGURED = True
''',
)

w(
    "src/infrastructure/llm/llm_provider.py",
    r'''
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
''',
)

w(
    "src/infrastructure/llm/embeddings.py",
    r'''
"""Embeddings — text-embedding-3-small."""
from __future__ import annotations

from typing import Any, List

from langchain_openai import OpenAIEmbeddings

from infrastructure.config import EMBEDDING_MODEL, EMBED_PROVIDER, OPENROUTER_BASE_URL, get_api_key


def get_embeddings(**kwargs: Any) -> OpenAIEmbeddings:
    opts: dict[str, Any] = {"model": EMBEDDING_MODEL, **kwargs}
    if EMBED_PROVIDER == "openrouter":
        opts["openai_api_base"] = OPENROUTER_BASE_URL
        opts["openai_api_key"] = get_api_key("openrouter")
    else:
        opts["openai_api_key"] = get_api_key("openai")
    return OpenAIEmbeddings(**opts)


def embed_texts(texts: List[str]) -> List[List[float]]:
    return get_embeddings().embed_documents(texts)
''',
)

w("src/infrastructure/llm/__init__.py", "from infrastructure.llm.llm_provider import get_router_llm, get_vision_llm, get_verify_llm\n")
w("src/infrastructure/__init__.py", "")
w("src/infrastructure/db/__init__.py", "from infrastructure.db.sql_client import ping_db\n")
w(
    "src/infrastructure/db/sql_client.py",
    r'''
"""Postgres client."""
from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return create_engine(url, pool_pre_ping=True)


def ping_db() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
''',
)

w(
    "src/infrastructure/db/supabase_client.py",
    r'''
"""Supabase helpers."""
from __future__ import annotations

import os
from functools import lru_cache

from loguru import logger

from infrastructure.config import STORAGE_PUBLIC_BUCKET, STORAGE_VAULT_BUCKET


@lru_cache(maxsize=1)
def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Supabase env missing")
    from supabase import create_client
    return create_client(url, key)


def ensure_buckets() -> dict:
    try:
        client = get_supabase()
        existing = {b.name for b in client.storage.list_buckets()}
        created = []
        for name, public in ((STORAGE_PUBLIC_BUCKET, True), (STORAGE_VAULT_BUCKET, False)):
            if name not in existing:
                client.storage.create_bucket(name, options={"public": public})
                created.append(name)
        return {"ok": True, "created": created}
    except Exception as exc:
        logger.warning("ensure_buckets skipped: {}", exc)
        return {"ok": False, "error": str(exc)}
''',
)

w(
    "src/infrastructure/observability.py",
    r'''
"""Langfuse soft-disable wrapper."""
from __future__ import annotations

import os
from loguru import logger

_client = None
_ready = False


def get_langfuse():
    global _client, _ready
    if _ready:
        return _client
    _ready = True
    from infrastructure.config import OBSERVABILITY_ENABLED
    if not OBSERVABILITY_ENABLED:
        return None
    sk, pk = os.getenv("LANGFUSE_SECRET_KEY"), os.getenv("LANGFUSE_PUBLIC_KEY")
    if not sk or not pk:
        logger.info("Langfuse disabled (no keys)")
        return None
    try:
        from langfuse import Langfuse
        _client = Langfuse(secret_key=sk, public_key=pk, host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
        return _client
    except Exception as exc:
        logger.warning("Langfuse init failed: {}", exc)
        return None
''',
)

print("infra ok")
