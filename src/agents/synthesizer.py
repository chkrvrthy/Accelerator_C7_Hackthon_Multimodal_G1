"""Synthesizer — fan-in node. Combines all specialist outputs into ``DesignReport``.

OWNER: Person A
SPRINT CONCEPTS:
    - Sprint 6: fan-in / aggregation in a multi-agent graph.
    - Cross-sprint: structured output, JSON-schema enforcement.
CONSUMES: ``LLMClient`` (text-only).
PROVIDES: ``run(state, deps) -> {"report": DesignReport}``, persists to disk.

WHY YOU CARE
------------
The five specialists each see a slice. The synthesizer is the only place
where someone (LLM or human) reasons across slices. That is what makes the
recommendations "specific" instead of "generic" — they reference cross-
agent evidence ("the visual agent flagged low contrast AND the UX agent
flagged the same input field as low-affordance — therefore the input is the
single highest-leverage fix").

LOGIC OUTLINE
-------------
1. Concatenate the five specialist outputs into a structured XML block.
2. Ask a text LLM to produce the DesignReport.
3. Persist to ``settings.report_dir/design_report_<id>.json``.
4. Return ``{"report": ...}``.

DEFINITION OF DONE
------------------
[ ] tests/person_a/test_synthesizer.py green against fake_deps.
[ ] tests/person_a/test_graph.py shows the report file lands in tmp dir.
[ ] ``overall_score`` is a sensible weighted blend (visual + UX +
    accessibility + brand) — not always 75.
[ ] ``top_recommendations`` is exactly 3 items, sorted by impact desc.
[ ] ``top_strengths`` is 3 items, present even when scores are low.

DO NOT
------
- Do not skip the schema validation. The whole point of this node is to
  produce a report another tool can read.
- Do not embed the prompt in this file — it lives in ``utils.prompts``.
- Do not write the report path back into the GraphState. The CLI / UI
  picks the path up from settings; coupling state to disk is leaky.

PROMPT-ITERATION CHECKLIST
--------------------------
1. Recommendations all "improve contrast" → require diversity:
       "exactly 3 recommendations, each from a DIFFERENT agent."
2. Score == sum / 4 every time → require a rubric:
       "overall_score = 0.30*visual + 0.30*ux + 0.25*accessibility + 0.15*brand."
3. Strengths empty → "always list 3 strengths, even if the design is rough."
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.agents.base import AgentDeps, build_default_deps, run_with_schema
from src.schemas.outputs import DesignReport, GraphState
from src.utils.logger import get_logger
from src.utils.prompts import synthesizer_system

if TYPE_CHECKING:  # pragma: no cover
    pass

log = get_logger(__name__)


def run(state: GraphState, deps: AgentDeps) -> dict[str, DesignReport]:
    """Combine specialist outputs into a DesignReport, persist it, return it.

    Resilience contract:
    1. Any of the five specialist fields may be ``None`` (an agent failed).
       The prompt instructs the LLM to renormalize weights and downgrade
       the affected axis — we still produce a usable report.
    2. We always populate ``run_id`` and ``analyzed_at`` on the returned
       report so the UI can surface "this report was generated at ...".
    3. The pydantic validator on ``top_recommendations`` re-numbers
       priorities densely 1..N, so the UI can render in order without
       trusting the LLM's emit sequence.
    """
    from src import config as _cfg

    parts: dict[str, dict | None] = {
        "visual": state.visual.model_dump() if state.visual else None,
        "ux": state.ux.model_dump() if state.ux else None,
        "accessibility": state.accessibility.model_dump() if state.accessibility else None,
        "brand": state.brand.model_dump() if state.brand else None,
        "market": state.market.model_dump() if state.market else None,
    }
    failed = [k for k, v in parts.items() if v is None]
    status_block = ""
    if state.analysis_status:
        status_block = f"\n<analysis_status>{json.dumps(state.analysis_status)}</analysis_status>"
    if failed:
        log.warning(
            "synthesizer: %d/%d specialists missing (%s) — emitting degraded report.",
            len(failed),
            len(parts),
            ", ".join(failed),
        )
    user_text = (
        "Synthesize a DesignReport from these specialist outputs.\n"
        f"<inputs>{json.dumps(parts, indent=2)}</inputs>"
        f"{status_block}\n"
        "<task>\n"
        "  1. Score 0-100 with score_rationale (40-80 words explaining WHY).\n"
        "  2. score_breakdown for each of the 5 axes.\n"
        "  3. 3 distinguishing strengths (specific elements only).\n"
        "  4. 3-5 ranked top_recommendations with priority 1..N, effort,\n"
        "     impact, metric_lift, and proof citation.\n"
        "</task>"
    )

    report = run_with_schema(
        agent_name="agent.synthesizer",
        system=synthesizer_system(),
        user=user_text,
        images=[],
        schema=DesignReport,
        deps=deps,
    )
    assert isinstance(report, DesignReport)

    # LOGIC: stamp runtime metadata on the LLM output. We own these fields,
    # not the model — they are facts about the run, not about the design.
    # The orchestrator's `state.analysis_status` is the source of truth for
    # which agents actually ran; an LLM hallucinating "ok" everywhere is
    # explicitly overridden here so the UI status grid never lies.
    report.run_id = uuid.uuid4().hex[:8]
    report.analyzed_at = datetime.now(UTC).isoformat(timespec="seconds")
    truth_status = state.analysis_status or _infer_status(state)
    if truth_status:
        report.analysis_status = truth_status

    # LOGIC: thread the specialist outputs through into the final report so
    # the UI / MCP consumer has them all in one place. The LLM produces the
    # *summary* fields; we own the structured ones.
    report.visual = state.visual
    report.ux = state.ux
    report.accessibility = state.accessibility
    report.brand = state.brand
    report.market = state.market

    # LOGIC: defense in depth — the validator renumbers priorities densely
    # but if the LLM emitted no priority at all, fix it now.
    for i, rec in enumerate(report.top_recommendations, start=1):
        if rec.priority < 1:
            rec.priority = i

    out_path = _cfg.settings.report_dir / f"design_report_{report.run_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.model_dump_json(indent=2))
    log.info(
        "synthesizer: wrote %s (score=%.1f, recs=%d, status=%s)",
        out_path.name,
        report.overall_score,
        len(report.top_recommendations),
        report.analysis_status,
    )

    return {"report": report}


def _infer_status(state: GraphState) -> dict[str, str]:
    """If the orchestrator did not populate analysis_status, infer it.

    Lets us produce a usable status grid even when the synthesizer is
    called by tests / CLI directly (where the orchestrator was bypassed).
    """
    return {
        name: ("ok" if getattr(state, name) is not None else "failed")
        for name in ("visual", "ux", "accessibility", "brand", "market")
    }


def _cli() -> int:
    """Smoke test on a fake state."""
    from src.fakes.fixtures import ensure_sample_design

    deps = build_default_deps()
    state = GraphState(image_path=str(ensure_sample_design()))
    state.visual = deps.vision.analyze(  # type: ignore[arg-type]
        system="",
        user="",
        images=[state.image_path],
        schema=__import__("src.schemas.outputs", fromlist=["VisualAnalysis"]).VisualAnalysis,
    )
    out = run(state, deps)
    print(json.dumps(out["report"].model_dump(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
