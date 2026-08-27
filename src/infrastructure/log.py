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
