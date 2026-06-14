"""LangSmith setup helper — graceful no-op when no key is configured.

OWNER: Person A
SPRINT CONCEPTS:
    - Sprint 5: LangSmith tracing.
CONSUMES: ``langsmith`` (optional), ``settings``.
PROVIDES: ``init_tracing``, ``traced``.

WHY YOU CARE
------------
Tracing is a "second-class citizen" until something breaks — then it is
the only thing that matters. We want one line to enable it
(``init_tracing()``) and one decorator/context manager to wrap an
interesting span (``traced``). When no API key is set, both degrade to
plain-Python no-ops. That keeps the demo working on judges' laptops
without forcing an account.

DEFINITION OF DONE
------------------
[ ] ``init_tracing()`` is idempotent — call ten times, no surprises.
[ ] With ``LANGCHAIN_TRACING_V2=true`` and a valid ``LANGCHAIN_API_KEY``,
    LangGraph nodes show up as spans in the LangSmith UI under
    ``settings.langchain_project``.
[ ] Without a key, the function logs ONE info line and returns False.
    No crash, no noisy warnings.
[ ] ``with traced("agent.visual"):`` is safe to nest and to call from
    inside ``deps.vision.analyze``.

DO NOT
------
- Do not import ``langsmith`` at module top — keep imports lazy.
- Do not raise from ``traced``. The block runs whether or not the trace
  push succeeded.
- Do not log full prompts in the metadata dict. The trace UI shows
  metadata as columns; large blobs make traces unreadable.

POST-MVP
--------
- Push explicit runs via ``langsmith.client.Client().create_run(...)`` so
  non-LangChain code (e.g. the LanceRetriever search) shows up as its own
  span. Today we rely on LangChain's automatic instrumentation of
  LangGraph nodes once env vars are set.
- Add a "trace_id" column to ``data/reports/*.json`` so we can link a
  saved report back to its trace.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


def _tracing_enabled() -> bool:
    """Return True iff LangSmith env vars are present AND the SDK is installed."""
    if not settings.langchain_tracing_v2 or not settings.langchain_api_key:
        return False
    try:
        import langsmith  # noqa: F401  — presence check only
    except ImportError:
        return False
    return True


def init_tracing() -> bool:
    """Configure LangSmith tracing if a key is set.

    Returns:
        True if LangSmith env vars were exported; False if no-op.
    """
    # LOGIC: LangChain reads env vars at first Runnable construction.
    # Calling init_tracing() AFTER building the graph is too late — wire it
    # at the very top of the UI / CLI entry point.
    if not settings.langchain_tracing_v2 or not settings.langchain_api_key:
        log.info("tracing: LangSmith disabled (no key or flag off).")
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    log.info("tracing: LangSmith enabled — project=%s", settings.langchain_project)
    return True


@contextlib.contextmanager
def traced(name: str, **metadata: Any) -> Iterator[None]:
    """Wrap a block as a LangSmith run; log locally if no key.

    With ``LANGCHAIN_TRACING_V2=true`` and a valid key, this pushes an
    *explicit* run via ``langsmith.Client().create_run`` so non-LangChain
    code paths (LanceRetriever search, MCP tool calls, etc.) appear in the
    LangSmith UI alongside the auto-traced LangGraph nodes.

    With no key, this is a near-zero-cost ``log.debug`` no-op.

    Usage::

        with traced("agent.visual", image=path):
            return deps.vision.analyze(...)
    """
    log.debug("trace.start name=%s meta=%s", name, metadata)

    if not _tracing_enabled():
        # LOGIC: keep the no-key path cheap. log.debug — not info — so we
        # don't add a line per agent call to the operator's stderr.
        try:
            yield
        finally:
            log.debug("trace.end   name=%s", name)
        return

    # LOGIC: import here so the no-key path never pays the import cost.
    try:
        from langsmith import Client  # type: ignore[import-not-found]
    except ImportError:
        try:
            yield
        finally:
            log.debug("trace.end   name=%s", name)
        return

    run_id = uuid.uuid4()
    started = datetime.now(timezone.utc)
    client: Any | None = None
    try:
        client = Client()
        client.create_run(
            id=run_id,
            name=name,
            run_type="chain",
            inputs={"metadata": metadata} if metadata else {},
            project_name=settings.langchain_project,
            start_time=started,
        )
    except Exception as e:
        log.warning("trace.start failed for %s: %s", name, e)
        client = None

    try:
        yield
    except Exception as e:
        if client is not None:
            try:
                client.update_run(
                    run_id,
                    error=f"{type(e).__name__}: {e}",
                    end_time=datetime.now(timezone.utc),
                )
            except Exception as ue:
                log.warning("trace.update (error path) failed for %s: %s", name, ue)
        raise
    else:
        if client is not None:
            try:
                client.update_run(
                    run_id,
                    outputs={"status": "ok"},
                    end_time=datetime.now(timezone.utc),
                )
            except Exception as ue:
                log.warning("trace.update (ok path) failed for %s: %s", name, ue)
    finally:
        log.debug("trace.end   name=%s", name)
