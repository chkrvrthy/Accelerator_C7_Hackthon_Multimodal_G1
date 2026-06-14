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
from src.agents.tools import call_tool
from src.schemas.outputs import GraphState, VisualAnalysis
from src.utils.logger import get_logger
from src.utils.prompts import multi_image_note, visual_analysis_system, visual_analysis_user

if TYPE_CHECKING:  # pragma: no cover
    pass

log = get_logger(__name__)


def _is_shallow_visual(result: VisualAnalysis) -> bool:
    """Detect a 'palette-only' response from the LLM.

    Empirical bug: ``openai/gpt-4o-mini`` (the default vision model)
    rejects strict ``json_schema`` mode about 95% of the time on multi-
    image runs and falls through to plain ``json_object``. In that mode
    it often emits a minimal JSON like ``{"palette": [...]}`` and skips
    every string field — they all default to ``""`` so the schema
    accepts it. The user sees an empty Visual section, the report's
    quality gate flags it, and the run feels broken.

    We detect that pattern HERE (not in the schema) so the recovery
    path can re-prompt with a corrective directive. The four-string
    threshold is intentional: a strong model occasionally folds two
    fields into one (e.g. spacing into layout), and we don't want to
    burn a retry on near-complete responses.
    """
    empty_strings = sum(
        1
        for f in (
            result.layout,
            result.hierarchy,
            result.typography,
            result.spacing_notes,
        )
        if not (f or "").strip()
    )
    no_observations = len(result.observations) == 0
    # 4 empty strings + no observations = the model only filled palette
    # (and maybe density_score). 3 empty + no observations is also a
    # clear miss. Anything below that bar — accept it; the quality gate
    # will still flag thin content but we do not double-charge tokens.
    return empty_strings >= 3 and no_observations


def run(state: GraphState, deps: AgentDeps) -> dict[str, VisualAnalysis]:
    """Run the Visual Analysis agent.

    Args:
        state: Current graph state. Reads ``image_path`` and ``instructions``.
        deps: Injected dependency container.

    Returns:
        ``{"visual": VisualAnalysis}`` partial-state dict.
    """
    # PRE-TOOL: extract a deterministic palette from the PRIMARY frame
    # (first uploaded image). For multi-frame runs we still pre-measure
    # only the first one — the LLM is told via the multi-frame note that
    # palette findings are global and to call out drift it sees on the
    # other frames. This keeps the pre-tool cheap (it does not scale
    # with N) while still grounding the dominant palette.
    measured = call_tool("visual.extract_palette", image_path=state.image_path)
    user_text = visual_analysis_user(state)
    if measured and measured.get("palette"):
        user_text += (
            "\n\n<measured_facts>\n"
            f"palette (k-means in CIELab, ground truth, frame 1): "
            f"{', '.join(measured['palette'])}\n"
            "Use these as anchors for the palette field. Refine names "
            "and accents but do NOT change the hex codes — they were "
            "measured from the actual image. If the other frames show "
            "different dominant colors, call that out as drift.\n"
            "</measured_facts>"
        )
        log.info("agent.visual: pre-tool palette=%s", measured["palette"])

    # Multi-frame awareness: append the shared note when N>1 so every
    # vision agent treats the frames as ONE coherent product. No-op for
    # single-image runs (returns ""). Frame labels (filenames or user-
    # supplied) are passed so the agent cites findings by label.
    user_text += multi_image_note(len(state.image_paths), state.frame_labels)

    images = [Path(p) for p in state.image_paths]

    # Prompt construction lives in utils.prompts so iteration happens in one
    # file, not scattered across agents (the prompt registry is the seam).
    result = run_with_schema(
        agent_name="agent.visual",
        system=visual_analysis_system(),
        user=user_text,
        images=images,
        schema=VisualAnalysis,
        deps=deps,
    )
    assert isinstance(result, VisualAnalysis)

    # SELF-HEAL on shallow responses. gpt-4o-mini (the default vision
    # model) drops narrative fields ~95% of the time when strict
    # json_schema is rejected and fallback fires. One sharp corrective
    # retry recovers most of those without escalating to a pricier
    # model. We log the retry loudly so it shows up in app.log AND the
    # console — the user knows we're doing something, not silently
    # spending more tokens. Wrapped in try/except: a retry that itself
    # fails should not lose the partial first response.
    if _is_shallow_visual(result):
        log.warning(
            "agent.visual: shallow response (palette-only). "
            "Retrying once with a corrective directive."
        )
        critique = (
            "\n\n<critique>\n"
            "Your previous response had palette but EVERY narrative "
            "field (layout, hierarchy, typography, spacing_notes, "
            "observations) was empty or missing. That is unacceptable. "
            "RE-EMIT the same VisualAnalysis JSON with EVERY field "
            "populated with concrete observations from the screenshot:\n"
            "  - layout: 1-2 sentences naming zones and proportions.\n"
            "  - hierarchy: name strongest visual element first.\n"
            "  - typography: classify families (geometric sans, "
            "humanist serif, mono) and weights you can read.\n"
            "  - spacing_notes: 1 sentence with numbers (8 px grid, "
            "etc.) anchored on the screenshot.\n"
            "  - density_score: pick a SPECIFIC rubric anchor.\n"
            "  - observations: 5-10 short verifiable facts.\n"
            "Keep the palette unchanged; it was correct.\n"
            "</critique>"
        )
        try:
            retry = run_with_schema(
                agent_name="agent.visual.retry",
                system=visual_analysis_system(),
                user=user_text + critique,
                images=images,
                schema=VisualAnalysis,
                deps=deps,
            )
            assert isinstance(retry, VisualAnalysis)
            if not _is_shallow_visual(retry):
                log.info("agent.visual: retry recovered the narrative.")
                result = retry
            else:
                log.warning(
                    "agent.visual: retry STILL shallow. Keeping partial "
                    "result; the quality gate will flag it as 'visual."
                    "narrative' fail and the report will surface a "
                    "'not captured this run' note."
                )
        except Exception as e:
            log.warning(
                "agent.visual: retry failed (%s: %s). "
                "Keeping partial result.",
                type(e).__name__,
                e,
            )

    # POST-TOOL: if the LLM dropped or replaced the measured palette,
    # restore the measured one. The LLM is good at narrative; the tool
    # is good at hex codes. This split keeps both honest. Run AFTER the
    # retry merge so the corrected response also benefits.
    if measured and measured.get("palette") and not result.palette:
        result.palette = list(measured["palette"])
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
