"""Visual Analysis agent — emit a ``VisualAnalysis``.

OWNER: Person C
SPRINT CONCEPTS:
    - Sprint 1: multimodal prompt + JSON-schema output.
    - Sprint 6: one parallel branch of the multi-agent graph.
CONSUMES: ``VisionLLM`` (via ``AgentDeps``), prompt from ``utils.prompts``.
PROVIDES: ``run(state, deps) -> {"visual": VisualAnalysis}``.

WHY YOU CARE
------------
This is the simplest agent in the system on purpose — start here when you
join the project. If you can't get a clean VisualAnalysis out, none of the
heavier agents will work either. It is the canary.

LOGIC OUTLINE
-------------
1. Pull the system prompt from ``prompts.visual_analysis_system()``.
2. Build a user message that incorporates ``state.instructions`` if present.
3. Call ``deps.vision.analyze(... schema=VisualAnalysis)``.
4. Return a partial-state dict ``{"visual": <result>}``.

WHY PARTIAL-STATE
-----------------
LangGraph merges the partial dict into the running state. By only returning
*our* field (``visual``), this node cannot accidentally clobber the outputs
of agents running in parallel. That property is what makes the fan-out safe.

DEFINITION OF DONE
------------------
[ ] tests/person_c/test_visual_analysis.py is green against fake_deps.
[ ] ``make run-c-visual`` prints a valid VisualAnalysis JSON.
[ ] With ``USE_REAL=1``, the palette comes back as proper ``#RRGGBB`` strings
    on a real screenshot (verify by eye against the image).
[ ] ``density_score`` is a sensible 0..100 number — not always 50, not
    always 90. Iterate the prompt until it discriminates.

DO NOT
------
- Do not embed the prompt string here. It belongs in ``utils.prompts``.
- Do not loop over the LLM in this file. One call per agent.
- Do not write the output to disk. The synthesizer persists; specialists
  return state and stop.
- Do not catch exceptions silently. If validation fails, let it raise — the
  graph should retry the node, not pretend the agent succeeded.

PROMPT-ITERATION CHECKLIST (where most of your time goes)
---------------------------------------------------------
1. The LLM returns "navy" instead of "#0A2540" → tighten ``utils.prompts.
   visual_analysis_system`` with: "palette MUST be hex codes like ``#RRGGBB``".
2. The LLM lists 12 colors → ask for "no more than 6 palette entries".
3. The LLM returns spacing as a number (e.g. ``8``) → ask for descriptive
   strings ("8 px grid; 24 px gutters") since the schema has ``str``.
4. ``density_score`` always pegged at 80 → add anchor examples in the prompt
   ("blank page = 0, busy stock-trading dashboard = 90").
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from src.agents.base import AgentDeps, build_default_deps, run_with_schema
from src.schemas.outputs import GraphState, VisualAnalysis
from src.utils.logger import get_logger
from src.utils.prompts import visual_analysis_system, visual_analysis_user

if TYPE_CHECKING:  # pragma: no cover
    pass

log = get_logger(__name__)


def run(state: GraphState, deps: AgentDeps) -> dict[str, VisualAnalysis]:
    """Run the Visual Analysis agent.

    Args:
        state: Current graph state. Reads ``image_path`` and ``instructions``.
        deps: Injected dependency container.

    Returns:
        ``{"visual": VisualAnalysis}`` partial-state dict.
    """
    # Prompt construction lives in utils.prompts so iteration happens in one
    # file, not scattered across agents (the prompt registry is the seam).
    result = run_with_schema(
        agent_name="agent.visual",
        system=visual_analysis_system(),
        user=visual_analysis_user(state),
        images=[Path(state.image_path)],
        schema=VisualAnalysis,
        deps=deps,
    )
    assert isinstance(result, VisualAnalysis)
    return {"visual": result}


# --------------------------------------------------------------------------- #
# Per-slice CLI runner                                                        #
# --------------------------------------------------------------------------- #
def _cli() -> int:
    parser = argparse.ArgumentParser(description="Visual Analysis agent (Person C)")
    parser.add_argument("--image", required=True)
    parser.add_argument("--instructions", default=None)
    parser.add_argument("--use-real", action="store_true", default=None)
    args = parser.parse_args()

    deps = build_default_deps(use_real=args.use_real)
    state = GraphState(image_path=str(args.image), instructions=args.instructions)
    out = run(state, deps)
    print(json.dumps(out["visual"].model_dump(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
