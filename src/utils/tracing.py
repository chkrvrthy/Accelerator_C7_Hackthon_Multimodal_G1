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
from collections.abc import Iterator
from typing import Any

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


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

    Usage:
        with traced("agent.visual", image=path):
            return await deps.vision.analyze(...)
    """
    log.debug("trace.start name=%s meta=%s", name, metadata)
    # HINT: explicit-run recipe for non-LangChain code (post-MVP):
    #
    #   from langsmith import Client
    #   client = Client()
    #   run = client.create_run(name=name, run_type="chain",
    #                           inputs={"metadata": metadata}, project_name=settings.langchain_project)
    #   try:
    #       yield
    #       client.update_run(run.id, outputs={"status": "ok"}, end_time=datetime.utcnow())
    #   except Exception as e:
    #       client.update_run(run.id, error=str(e), end_time=datetime.utcnow())
    #       raise
    #
    # NOTE: keep the no-key path fast — log.debug is right; do not log.info
    # because every agent call would emit a line.
    try:
        # TODO(person-a, post-MVP): when langsmith is installed and a key
        # is set, push an explicit run so non-LangChain spans (LanceRetriever,
        # TavilySearch) show up too. For v1 we rely on LangChain's automatic
        # tracing of LangGraph nodes, which kicks in once init_tracing()
        # has exported the env vars.
        yield
    finally:
        log.debug("trace.end   name=%s", name)
