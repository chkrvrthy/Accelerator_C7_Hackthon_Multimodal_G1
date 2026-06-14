"""Project-wide logger.

Use:
    from src.utils import get_logger
    log = get_logger(__name__)
    log.info("agent.%s starting (images=%d)", agent_name, n_images)

We prefer loguru for its nice formatting + structured fields, but fall back
to stdlib ``logging`` cleanly when loguru is not installed (e.g. in a slice
that does not pull the full ``base.txt`` requirements). This means tests
and per-slice runners work even before ``pip install`` is fully done.

STDLIB-COMPAT INTERPOLATION
---------------------------
The codebase uses ``logging``-style positional args (``log.info("got %s",
x)``). Stdlib ``logging`` interpolates those automatically; loguru does
NOT. The `_StdlibCompatLogger` wrapper below pre-interpolates ``%s`` /
``%d`` args before delegating to loguru so call-sites stay portable —
without this we'd see literal "got %s" in the console (the bug Person E
hit on Windows).

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


class _StdlibCompatLogger:
    """Thin shim that lets loguru accept ``logging``-style positional args.

    Why this exists
    ---------------
    Stdlib ``logging`` does this for you:

        log.info("got %s items", n)   # -> "got 12 items"

    Loguru does NOT auto-interpolate ``%s`` / ``%d``; it uses ``{}``-style
    formatting via ``log.info("got {} items", n)``. Migrating every call
    site would be invasive, so this wrapper pre-formats positional args
    with ``msg % args`` (the same rule stdlib uses), then delegates the
    already-formatted string to loguru.

    Failure mode: if interpolation raises (mismatched specifiers), we
    fall back to printing the raw template + args so we never lose the
    log line. Better a slightly ugly log than a missing one.
    """

    __slots__ = ("_base",)

    def __init__(self, base: Any) -> None:
        self._base = base

    @staticmethod
    def _fmt(msg: Any, args: tuple[Any, ...]) -> str:
        if not args:
            return str(msg)
        try:
            return str(msg) % args
        except (TypeError, ValueError):
            # Mismatched specifier — keep the raw template + args visible
            # so the dev can spot the bug without losing context.
            return f"{msg} | args={args!r}"

    def _log(self, level: str, msg: Any, args: tuple[Any, ...], kw: dict[str, Any]) -> None:
        # depth=2 skips this _log frame plus the wrapper method (info/warning/...)
        # so loguru reports the original caller in {function} / {file}:{line}.
        try:
            target = self._base.opt(depth=2)
        except AttributeError:
            target = self._base
        getattr(target, level)(self._fmt(msg, args), **kw)

    def debug(self, msg: Any, *args: Any, **kw: Any) -> None:
        self._log("debug", msg, args, kw)

    def info(self, msg: Any, *args: Any, **kw: Any) -> None:
        self._log("info", msg, args, kw)

    def warning(self, msg: Any, *args: Any, **kw: Any) -> None:
        self._log("warning", msg, args, kw)

    def error(self, msg: Any, *args: Any, **kw: Any) -> None:
        self._log("error", msg, args, kw)

    def exception(self, msg: Any, *args: Any, **kw: Any) -> None:
        # Loguru's `.exception()` auto-attaches the active exception.
        self._log("exception", msg, args, kw)

    def critical(self, msg: Any, *args: Any, **kw: Any) -> None:
        self._log("critical", msg, args, kw)

    # Pass-through for anything we didn't wrap (e.g. ``log.bind(...)``,
    # ``log.opt(...)``). Forwarding keeps loguru's full API available.
    def __getattr__(self, item: str) -> Any:
        return getattr(self._base, item)


def get_logger(name: str | None = None) -> Any:
    """Return a logger bound to ``name``.

    With loguru → returns a ``_StdlibCompatLogger`` wrapping
    ``logger.bind(name=...)``. Stdlib-style ``%s`` / ``%d`` positional
    args are interpolated before the message reaches loguru.

    Without loguru → returns ``logging.getLogger(name)`` directly (it
    already does the interpolation natively).
    """
    _configure()
    if _HAS_LOGURU:
        return _StdlibCompatLogger(_loguru_logger.bind(name=name or "app"))
    return logging.getLogger(name or "app")
