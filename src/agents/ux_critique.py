"""UX Critique agent — emit a ``UXCritique``.

OWNER: Person D
SPRINT CONCEPTS:
    - Sprint 1: XML-tagged prompt blocks for context/task.
    - Sprint 6: one parallel branch of the multi-agent graph.
CONSUMES: ``VisionLLM``, ``utils.prompts.ux_critique_system``.
PROVIDES: ``run(state, deps) -> {"ux": UXCritique}``.

WHY YOU CARE
------------
UX critiques are where LLMs go off the rails fastest. Without discipline
they mark every soft-edged button "critical" and every off-white background
a "violation". Your prompt — not your code — is what saves this agent.

LOGIC OUTLINE
-------------
1. Compose a user message with XML tags around context and task — Sprint 1
   recommended pattern for keeping the model on rails.
2. Vision call with ``schema=UXCritique``.
3. Return ``{"ux": ...}``.

WHY XML TAGS
------------
``<context>...</context>`` and ``<task>...</task>`` partition the prompt so
the model treats them as separate signals. We avoid markdown for this
because the model sometimes copies markdown into its output, breaking JSON
mode. XML inside JSON output never collides.

DEFINITION OF DONE
------------------
[ ] tests/person_d/test_ux_critique.py green against fake_deps.
[ ] ``make run-d-ux`` prints a valid UXCritique JSON.
[ ] Every Finding has non-empty ``evidence`` AND ``recommendation``.
[ ] Severity distribution on a real screenshot: at most 1 ``critical``,
    at most 2 ``high``. If everything is critical, the prompt is broken.
[ ] ``cognitive_load_score`` differentiates between a busy and a calm
    layout (run on two screenshots, compare).

DO NOT
------
- Do not chain heuristics in code. The model picks heuristics from the prompt.
- Do not fabricate evidence in the schema. ``evidence: ""`` is preferable
  to evidence: "the button looks weird".
- Do not duplicate Findings in ``heuristic_violations`` and
  ``friction_points``. Pick one.

PROMPT-ITERATION CHECKLIST
--------------------------
1. Severity inflation → add the rubric in ``utils.prompts.ux_critique_system``:
       "high = blocks task completion; medium = adds friction;
        low = polish; critical = data-loss or unsafe action."
2. Generic recommendations ("improve contrast") → require concrete deltas:
       "every recommendation must specify what to change and to what value."
3. Hallucinated UI elements → "if you cannot see it in the screenshot, do
   not mention it. Quote what you see verbatim."
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.agents.base import AgentDeps, build_default_deps, run_with_schema
from src.schemas.outputs import GraphState, UXCritique
from src.utils.logger import get_logger
from src.utils.prompts import ux_critique_system, ux_critique_user

log = get_logger(__name__)


def run(state: GraphState, deps: AgentDeps) -> dict[str, UXCritique]:
    """Run the UX Critique agent."""
    result = run_with_schema(
        agent_name="agent.ux",
        system=ux_critique_system(),
        user=ux_critique_user(state),
        images=[Path(state.image_path)],
        schema=UXCritique,
        deps=deps,
    )
    assert isinstance(result, UXCritique)
    return {"ux": result}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="UX Critique agent (Person D)")
    parser.add_argument("--image", required=True)
    parser.add_argument("--instructions", default=None)
    parser.add_argument("--use-real", action="store_true", default=None)
    args = parser.parse_args()

    deps = build_default_deps(use_real=args.use_real)
    state = GraphState(image_path=str(args.image), instructions=args.instructions)
    out = run(state, deps)
    print(json.dumps(out["ux"].model_dump(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
