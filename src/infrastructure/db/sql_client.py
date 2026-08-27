"""Postgres client."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

_SessionLocal: Optional[sessionmaker] = None


def _make_engine_url(raw: str) -> URL:
    """Build a SQLAlchemy URL that survives passwords with @ : # etc.

    A raw ``postgresql://user:p@ss@host:6543/db`` string is fine for Python's
    urlparse (last ``@``), but libpq/psycopg2 splits on the *first* ``@`` and
    then tries a bogus Unix socket — classic Windows + Supabase pooler failure.
    """
    parsed = urlparse(raw)
    if not parsed.hostname:
        raise RuntimeError(
            "Invalid SUPABASE_DB_URL (no host). "
            "Use pooler URI port 6543; URL-encode special chars in the password "
            "(e.g. @ → %40)."
        )
    password = unquote(parsed.password) if parsed.password else None
    database = (parsed.path or "/postgres").lstrip("/") or "postgres"
    driver = parsed.scheme or "postgresql"
    if "+" not in driver:
        driver = f"{driver}+psycopg2"
    return URL.create(
        drivername=driver,
        username=parsed.username,
        password=password,
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=database,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return create_engine(
        _make_engine_url(url),
        pool_size=8,
        max_overflow=12,
        pool_pre_ping=True,
        pool_recycle=300,
    )


def get_session() -> Session:
    """SQLAlchemy session (caller must close). Pattern from Examples/aee-capstone."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False
        )
    return _SessionLocal()


def ping_db() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def execute(sql: str, params: Optional[dict[str, Any]] = None) -> Any:
    """Run a statement in a short-lived session and commit."""
    session = get_session()
    try:
        result = session.execute(text(sql), params or {})
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
