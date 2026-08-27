"""One-shot Sprint 1 scaffold writer. Run: python scripts/_write_sprint1.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def w(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8")
    print("wrote", rel)


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

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"


def _load_yaml(filename: str) -> Dict[str, Any]:
    filepath = _CONFIG_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_nested(d: Any, *keys, default=None):
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d if d is not None else default


_PARAMS = _load_yaml("param.yaml")
_MODELS = _load_yaml("models.yaml")

PROVIDER = _get_nested(_PARAMS, "provider", "default", default="openai")
MODEL_TIER = _get_nested(_PARAMS, "provider", "tier", default="general")
OPENROUTER_BASE_URL = _get_nested(
    _PARAMS, "provider", "openrouter_base_url", default="https://openrouter.ai/api/v1"
)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

EMBEDDING_TIER = _get_nested(_PARAMS, "embedding", "tier", default="small")
EMBEDDING_DIM = int(_get_nested(_PARAMS, "embedding", "dim", default=1536))


def get_role_model(role: str) -> tuple[str, str]:
    role_cfg = _get_nested(_MODELS, "roles", role, default={}) or {}
    provider = role_cfg.get("provider") or PROVIDER
    tier = role_cfg.get("tier") or MODEL_TIER
    section = {
        "router": "chat",
        "vision": "vision",
        "verify": "verify",
        "embed": "embedding",
    }.get(role, "chat")
    model = _get_nested(_MODELS, provider, section, tier)
    if not model and section == "vision":
        model = _get_nested(_MODELS, provider, "chat", tier)
    if not model and section == "verify":
        model = _get_nested(_MODELS, provider, "chat", "strong")
    if not model:
        model = "gpt-4o-mini" if role != "embed" else "text-embedding-3-small"
    return provider, model


ROUTER_PROVIDER, ROUTER_MODEL = get_role_model("router")
VISION_PROVIDER, VISION_MODEL = get_role_model("vision")
VERIFY_PROVIDER, VERIFY_MODEL = get_role_model("verify")
EMBED_PROVIDER, EMBEDDING_MODEL = get_role_model("embed")

LLM_TEMPERATURE = float(_get_nested(_PARAMS, "llm", "temperature", default=0.0))
LLM_MAX_TOKENS = int(_get_nested(_PARAMS, "llm", "max_tokens", default=2000))

FUSION_WEIGHTS = {
    "vision": float(_get_nested(_PARAMS, "fusion", "vision", default=0.30)),
    "text": float(_get_nested(_PARAMS, "fusion", "text", default=0.30)),
    "geo": float(_get_nested(_PARAMS, "fusion", "geo", default=0.25)),
    "category": float(_get_nested(_PARAMS, "fusion", "category", default=0.15)),
}

MATCH_HIGH = float(_get_nested(_PARAMS, "match", "high_threshold", default=0.80))
MATCH_MEDIUM = float(_get_nested(_PARAMS, "match", "medium_threshold", default=0.50))
GEO_RADIUS_M = int(_get_nested(_PARAMS, "match", "geo_radius_m", default=5000))

FRAUD = {
    "claim_velocity_max": int(_get_nested(_PARAMS, "fraud", "claim_velocity_max", default=3)),
    "claim_velocity_window_h": int(
        _get_nested(_PARAMS, "fraud", "claim_velocity_window_h", default=24)
    ),
    "fail_lockout_count": int(_get_nested(_PARAMS, "fraud", "fail_lockout_count", default=3)),
    "fail_lockout_h": int(_get_nested(_PARAMS, "fraud", "fail_lockout_h", default=24)),
    "risk_pass": float(_get_nested(_PARAMS, "fraud", "risk_pass", default=0.3)),
    "risk_review": float(_get_nested(_PARAMS, "fraud", "risk_review", default=0.7)),
}

GPS_FUZZ_METERS = int(_get_nested(_PARAMS, "gps", "fuzz_meters", default=500))
BLUR_SIGMA = float(_get_nested(_PARAMS, "sanitization", "blur_sigma", default=15))

LOGS_DIR = _PROJECT_ROOT / _get_nested(_PARAMS, "paths", "logs_dir", default="logs")
LOGGING_ENABLED = bool(_get_nested(_PARAMS, "logging", "enabled", default=True))
LOG_LEVEL = _get_nested(_PARAMS, "logging", "level", default="INFO")
OBSERVABILITY_ENABLED = bool(_get_nested(_PARAMS, "observability", "enabled", default=True))

STORAGE_PUBLIC_BUCKET = os.getenv(
    "STORAGE_PUBLIC_BUCKET",
    _get_nested(_PARAMS, "paths", "public_bucket", default="public-sanitized"),
)
STORAGE_VAULT_BUCKET = os.getenv(
    "STORAGE_VAULT_BUCKET",
    _get_nested(_PARAMS, "paths", "vault_bucket", default="private-vault"),
)


def get_log_level() -> str:
    return (os.getenv("LOG_LEVEL") or LOG_LEVEL).upper()


def get_api_key(provider: Optional[str] = None) -> Optional[str]:
    provider = provider or PROVIDER
    key_map = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    return os.getenv(key_map.get(provider, f"{provider.upper()}_API_KEY"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = ""

    redis_url: str = "redis://localhost:6379/0"
    arq_worker_enabled: bool = False

    openai_api_key: str = ""
    openrouter_api_key: str = ""

    auth_dev_bypass: bool = True
    auth_dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    auth_dev_email: str = "dev@verifind.local"

    # Accept both naming styles from .env
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_alias_generator=None,
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Map common .env aliases into Settings fields
    alias_map = {
        "SUPABASE_URL": "supabase_url",
        "SUPABASE_ANON_KEY": "supabase_anon_key",
        "SUPABASE_SERVICE_KEY": "supabase_service_key",
        "SUPABASE_JWT_SECRET": "supabase_jwt_secret",
        "SUPABASE_DB_URL": "database_url",
        "DATABASE_URL": "database_url",
        "REDIS_URL": "redis_url",
        "ARQ_WORKER_ENABLED": "arq_worker_enabled",
        "OPENAI_API_KEY": "openai_api_key",
        "OPENROUTER_API_KEY": "openrouter_api_key",
        "AUTH_DEV_BYPASS": "auth_dev_bypass",
        "AUTH_DEV_USER_ID": "auth_dev_user_id",
        "AUTH_DEV_EMAIL": "auth_dev_email",
        "API_HOST": "api_host",
        "API_PORT": "api_port",
        "API_RELOAD": "api_reload",
        "CORS_ORIGINS": "cors_origins",
    }
    data: Dict[str, Any] = {}
    for env_key, field in alias_map.items():
        val = os.getenv(env_key)
        if val is not None and val != "":
            data[field] = val
    return Settings(**data)
''',
)

print("partial ok — continuing in next script parts")
