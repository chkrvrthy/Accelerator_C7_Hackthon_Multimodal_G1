"""Agent dependency container + shared helpers.

OWNER: Person A
SPRINT CONCEPTS: dependency injection (Code-Quality concept), Sprint 5 tools.
CONSUMES: ``contracts``, ``fakes`` (for the default factory).
PROVIDES: ``AgentDeps`` dataclass, ``build_default_deps``, ``run_with_schema``.

WHY THIS FILE EXISTS
--------------------
Every agent needs the same four things: an LLM, a vision LLM, a retriever,
and (sometimes) a web search. We pack those four into one ``AgentDeps``
container so:

  * Tests construct a fake-only ``AgentDeps`` once and pass it to every
    agent.
  * The graph wires real implementations once and threads the same container
    through every node.
  * Adding a sixth dependency in three months is a one-line change in this
    file — not a tour of the codebase.

This is plain dependency injection. Nothing fancy. The discipline is that
*nothing else* in the agent files reads global state.

DEFINITION OF DONE
------------------
[ ] ``build_default_deps()`` returns fakes on a fresh checkout (no env vars).
[ ] ``build_default_deps(use_real=True)`` returns the real wiring once
    Person A and Person B finish their slices — and FAILS LOUDLY if their
    deps aren't installed (do not silently fall back).
[ ] Every agent's ``run(state, deps)`` accepts EITHER fake or real deps —
    no isinstance checks anywhere.
[ ] ``run_with_schema`` wraps every call with ``traced(...)`` so judges
    see five spans on a single timeline in LangSmith.

DO NOT
------
- Do not add a 6th dependency until you have the 5 working. ``AgentDeps``
  growing reflects scope creep — push back.
- Do not allow an agent to construct its own LLM. The container is the
  contract; bypassing it breaks the swap.
- Do not leak ``Settings`` into agent code. Read ``deps.cfg`` instead so
  test monkeypatches work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from src.config import Settings, settings
from src.contracts import LLMClient, Retriever, VisionLLM, WebSearch
from src.utils.logger import get_logger
from src.utils.tracing import traced

log = get_logger(__name__)


@dataclass
class AgentDeps:
    """Container threaded through every agent's ``run(state, deps)``."""

    llm: LLMClient
    vision: VisionLLM
    retriever: Retriever
    search: WebSearch
    cfg: Settings = field(default_factory=lambda: settings)


def build_default_deps(use_real: bool | None = None) -> AgentDeps:
    """Construct an ``AgentDeps`` with fakes by default.

    Args:
        use_real: When ``True``, wire ``OpenRouterClient``, ``OpenRouterVision``,
            ``LanceRetriever``, ``TavilySearch`` (or ``DuckDuckGoSearch`` if no
            Tavily key). When ``None`` (default), read ``settings.use_real``.

    Returns:
        A ready-to-use ``AgentDeps``. Calling agents on the result is safe in
        offline mode (fakes) and online mode (real impls) with the SAME code.
    """
    real = settings.use_real if use_real is None else use_real

    if not real:
        # Offline path — every fake is import-cheap.
        from src.fakes import FakeLLM, FakeRetriever, FakeSearch, FakeVisionLLM

        return AgentDeps(
            llm=FakeLLM(),
            vision=FakeVisionLLM(),
            retriever=FakeRetriever(),
            search=FakeSearch(),
        )

    # Online path — heavier imports kept lazy on purpose.
    from src.llm.multimodal import OpenRouterVision
    from src.llm.openrouter_client import OpenRouterClient
    from src.rag.retriever import LanceRetriever
    from src.tools.web_search import get_default_search

    return AgentDeps(
        llm=OpenRouterClient(),
        vision=OpenRouterVision(),
        retriever=LanceRetriever(),
        search=get_default_search(),
    )


def run_with_schema(
    *,
    agent_name: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    deps: AgentDeps,
    images: list[Path] | None = None,
) -> BaseModel:
    """Generic helper used by every agent.

    Picks ``deps.vision.analyze`` if ``images`` is non-empty, else
    ``deps.llm.complete``. Wraps the call in a LangSmith span (no-op if no key)
    and logs entry/exit/error so the operator can debug a stuck agent without
    enabling DEBUG.

    Returns:
        A validated instance of ``schema``.

    Raises:
        Anything the underlying LLM client raises, after logging it. Callers
        (graph + UI) decide whether to fail the whole run or skip this slice.
    """
    # NOTE: visible-error pattern. Every agent goes through this seam, so a
    # single try/except here gives Person A/B/C/D/E uniform debug output:
    #     "agent.visual: starting (schema=VisualAnalysis, images=1)"
    #     "agent.visual: failed: openai.RateLimitError ..."
    # No silent excepts anywhere downstream. If you want to swallow an error,
    # do it at the GRAPH level (after this function), not inside it.
    n_images = len(images) if images else 0
    log.info("%s: starting (schema=%s, images=%d)", agent_name, schema.__name__, n_images)
    # LOGIC: every agent call is wrapped in a LangSmith span. With no key,
    # ``traced`` is a near-zero-cost log.debug no-op (see src/utils/tracing.py).
    with traced(agent_name, schema=schema.__name__, images=n_images):
        try:
            if images:
                result = deps.vision.analyze(
                    system=system, user=user, images=list(images), schema=schema
                )
            else:
                result = deps.llm.complete(system=system, user=user, schema=schema)
        except Exception as e:
            # LOGIC: log the exception at ERROR (always visible), then re-raise.
            # The graph layer (or fallback orchestrator) decides retry / skip.
            log.error("%s: failed: %s: %s", agent_name, type(e).__name__, e)
            raise
    log.info("%s: ok (%s)", agent_name, schema.__name__)
    return result
