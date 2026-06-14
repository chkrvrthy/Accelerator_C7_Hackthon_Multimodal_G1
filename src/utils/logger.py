"""Project-wide logger.

Use:
    from src.utils import get_logger
    log = get_logger(__name__)
    log.info("hello")

We prefer loguru for its nice formatting + structured fields, but fall back
to stdlib ``logging`` cleanly when loguru is not installed (e.g. in a slice
that does not pull the full ``base.txt`` requirements). This means tests
and per-slice runners work even before ``pip install`` is fully done.

OWNER: Person A (already on disk; do not modify casually)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from src.config import settings

_CONFIGURED = False

try:
    from loguru import logger as _loguru_logger  # type: ignore[import-not-found]

    _HAS_LOGURU = True
except ImportError:  # graceful degrade
    _loguru_logger = None  # type: ignore[assignment]
    _HAS_LOGURU = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    if _HAS_LOGURU:
        _loguru_logger.remove()
        _loguru_logger.add(
            sys.stderr,
            level=settings.log_level,
            backtrace=False,
            diagnose=False,
            format=(
                "<green>{time:HH:mm:ss}</green> "
                "<level>{level: <8}</level> "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
                "<level>{message}</level>"
            ),
        )
    else:
        logging.basicConfig(
            stream=sys.stderr,
            level=getattr(logging, settings.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
            datefmt="%H:%M:%S",
        )
    _CONFIGURED = True


def get_logger(name: str | None = None) -> Any:
    """Return a logger bound to ``name``.

    With loguru → returns ``logger.bind(name=...)``.
    Without loguru → returns ``logging.getLogger(name)``.

    Both expose ``.info()``, ``.warning()``, ``.error()``, etc.
    """
    _configure()
    if _HAS_LOGURU:
        return _loguru_logger.bind(name=name or "app")
    return logging.getLogger(name or "app")
