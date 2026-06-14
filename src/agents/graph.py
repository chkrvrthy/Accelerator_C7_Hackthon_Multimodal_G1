"""LangGraph wiring — parallel fan-out + synthesizer.

OWNER: Person A
SPRINT CONCEPTS: Sprint 5 (LangGraph multi-agent), Sprint 6 (parallel fan-out
    + structured aggregated output).
CONSUMES: every agent's ``run(state, deps)``.
PROVIDES: ``build_graph(deps)``, ``run_graph(image_path, ...)``.

LOGIC OUTLINE
-------------
1. ``build_graph`` constructs a ``StateGraph(GraphState)`` with five
   specialist nodes (visual, ux, accessibility, brand, market) all wired
   from START in parallel, then all converging on synthesizer → END.
2. ``run_graph`` is the convenience wrapper used by the UI and the MCP
   server. It builds default deps if none provided, invokes the graph,
   and returns the final ``DesignReport``.

WHY THE PARALLEL DAG MATTERS
----------------------------
End-to-end latency = ``max(agent_latency) + synthesizer_latency``, NOT the
sum. With OpenRouter rate limits as the only constraint, that means a 5-LLM
fan-out finishes in roughly the time of one slow agent. Judges who watch
the LangSmith trace will see five simultaneous spans starting at the same
x-coordinate — the visual proof that "agentic" is also fast.

WHY THE FALLBACK
----------------
Person A's tests run in CI before LangGraph is installed in some environments.
The graph file therefore defines a FALLBACK orchestrator that walks the same
DAG sequentially using plain Python. The FALLBACK preserves the public surface
(``run_graph``) so every other test can rely on it. When ``langgraph`` IS
installed, ``build_graph`` returns a real compiled StateGraph.

DEFINITION OF DONE
------------------
[ ] tests/person_a/test_graph.py is green: end-to-end against fakes
    yields a valid DesignReport AND persists it to disk.
[ ] With ``USE_REAL=1`` and a key, ``make demo`` finishes in < 30 s.
[ ] LangSmith trace shows five specialist spans starting near the same
    timestamp (visual proof of parallelism).
[ ] The fallback orchestrator (no langgraph) produces the SAME report
    shape — only the trace UI differs.

DO NOT
------
- Do not pass ``state`` by reference between nodes. LangGraph already
  merges partial-state dicts; mutating state inside a node is undefined.
- Do not import LangChain / LangGraph at module top. They are heavy and
  Person B/C/D test runs that don't need the graph should not pay for it.
- Do not embed the agent functions inline. Each agent must own its run().

HINTS
-----
- Stream node updates via ``compiled.stream(state)`` so the UI can show
  per-node progress badges.
- Wire LangSmith via ``RunnableConfig(callbacks=[...])`` once tracing.py
  lands; the ``init_tracing()`` function only sets env vars.
- Async parallelism: when an agent's run() becomes ``async def``, switch
  to ``compiled.ainvoke(state)`` and use ``asyncio.gather`` in the
  fallback orchestrator. Today everything is sync — fine for v1.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.agents import (
    accessibility,
    brand_consistency,
    market_research,
    synthesizer,
    ux_critique,
    visual_analysis,
)
from src.agents.base import AgentDeps, build_default_deps
from src.schemas.outputs import DesignReport, GraphState
from src.utils.logger import get_logger

log = get_logger(__name__)


# Spec of all parallel specialist branches: (node_name, run_callable).
SPECIALIST_BRANCHES: list[tuple[str, Any]] = [
    ("visual", visual_analysis.run),
    ("ux", ux_critique.run),
    ("accessibility", accessibility.run),
    ("brand", brand_consistency.run),
    ("market", market_research.run),
]


def _fallback_run(state: GraphState, deps: AgentDeps) -> DesignReport:
    """Plain-Python orchestrator used when ``langgraph`` is not installed.

    Walks the same DAG sequentially. Same final output shape.
    """
    log.info("graph: running fallback orchestrator (langgraph not installed).")
    for name, fn in SPECIALIST_BRANCHES:
        log.info("graph: %s ...", name)
        partial = fn(state, deps)
        # LOGIC: copy the partial-state dict back into the GraphState.
        state = state.model_copy(update=partial)
    log.info("graph: synthesizer ...")
    state = state.model_copy(update=synthesizer.run(state, deps))
    assert state.report is not None, "synthesizer must populate report"
    return state.report


def build_graph(deps: AgentDeps) -> Any:
    """Return a compiled ``StateGraph`` if langgraph is installed, else None.

    HINT: callers should prefer ``run_graph`` which handles both cases.
    """
    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore[import-not-found]
    except ImportError:
        log.warning("graph: langgraph not installed — falling back to plain Python.")
        return None

    g = StateGraph(GraphState)
    # TODO(person-a): wrap each fn so it captures `deps` via closure and
    # returns a partial-state dict (LangGraph's expected node signature).
    for name, fn in SPECIALIST_BRANCHES:
        g.add_node(name, lambda s, _fn=fn, _d=deps: _fn(s, _d))
        g.add_edge(START, name)
    g.add_node("synthesizer", lambda s, _d=deps: synthesizer.run(s, _d))
    for name, _ in SPECIALIST_BRANCHES:
        g.add_edge(name, "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile()


def run_graph(
    image_path: Path | str,
    *,
    instructions: str | None = None,
    deps: AgentDeps | None = None,
) -> DesignReport:
    """Run the analysis end-to-end and return the synthesized report."""
    deps = deps or build_default_deps()
    state = GraphState(image_path=str(image_path), instructions=instructions)

    compiled = build_graph(deps)
    if compiled is None:
        return _fallback_run(state, deps)

    # TODO(person-a): use compiled.invoke or compiled.ainvoke for true
    # parallel scheduling. For now we call invoke which langgraph runs sync.
    final_state = compiled.invoke(state)
    report = final_state.get("report") if isinstance(final_state, dict) else final_state.report
    assert isinstance(report, DesignReport), "graph must return a DesignReport"
    return report


# --------------------------------------------------------------------------- #
# CLI runner: `python -m src.agents.graph --image <path>`                    #
# --------------------------------------------------------------------------- #
def _cli() -> int:
    parser = argparse.ArgumentParser(description="Full graph end-to-end (Person A)")
    parser.add_argument("--image", required=True)
    parser.add_argument("--instructions", default=None)
    parser.add_argument("--use-real", action="store_true", default=None)
    args = parser.parse_args()

    deps = build_default_deps(use_real=args.use_real)
    report = run_graph(args.image, instructions=args.instructions, deps=deps)
    print(json.dumps(report.model_dump(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
