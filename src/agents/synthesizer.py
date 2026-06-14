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
from src.agents.quality_gate import (
    check_design_report,
    format_issues_for_prompt,
)
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
        status_block = (
            "\n<analysis_status>"
            f"{json.dumps(state.analysis_status, separators=(',', ':'))}"
            "</analysis_status>"
        )
    if failed:
        log.warning(
            "synthesizer: %d/%d specialists missing (%s) — emitting degraded report.",
            len(failed),
            len(parts),
            ", ".join(failed),
        )
    # COST DISCIPLINE: compact JSON (no whitespace) for the <inputs> block.
    # The synthesizer is text-only and the 5 specialist outputs total ~2 kB
    # of structured data; pretty-printing wastes ~30 % of those tokens on
    # whitespace the model does not need. Compact form is identical
    # information at lower cost. Saves ~500 tokens per synthesizer call.
    user_text = (
        "Synthesize a DesignReport from these specialist outputs.\n"
        f"<inputs>{json.dumps(parts, separators=(',', ':'))}</inputs>"
        f"{status_block}\n"
        "<task>\n"
        " 1. executive_summary (60-100 word narrative paragraph): headline"
        " finding, single biggest opportunity, action to ship first.\n"
        " 2. Score 0-100 with score_rationale (40-80 words, ends with the"
        " 'fixing rec #1 raises overall by ~X' sentence).\n"
        " 3. score_breakdown for each of the 5 axes.\n"
        " 4. 3 distinguishing strengths (specific elements only).\n"
        " 5. 3-5 ranked top_recommendations with priority 1..N, effort,"
        " impact, metric_lift, and proof citation.\n"
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

    # AGENT RETRY LOOP (max 1 corrective re-prompt).
    # If the first synthesizer output is placeholder-thin (executive_summary
    # too short, no recommendations, missing breakdown), we re-prompt ONCE
    # with the specific failures appended to the user message. This is a
    # bounded budget by design: at most 2x the synthesizer cost, never more.
    # Skipped automatically when the cost-conscious mode flag is set.
    fail_issues = [i for i in check_design_report(report) if i.severity == "fail"]
    if fail_issues and not _cfg.settings.cache_disabled:
        # LOGIC: only retry on `fail` severity — `warn` / `info` are not
        # worth a second LLM call. We also skip when CACHE_DISABLED is on
        # because that mode is the dev/CI path where we want repeatable
        # token-free runs, not aggressive quality gating.
        feedback = format_issues_for_prompt(fail_issues)
        log.info(
            "synthesizer: corrective re-prompt (%d fail-level issues): %s",
            len(fail_issues),
            ", ".join(i.field for i in fail_issues),
        )
        retry_user = (
            user_text
            + "\n\n<corrective_feedback>"
            + feedback
            + "\nReturn the COMPLETE DesignReport JSON again with the fixes."
            + "</corrective_feedback>"
        )
        retry_report = run_with_schema(
            agent_name="agent.synthesizer.retry",
            system=synthesizer_system(),
            user=retry_user,
            images=[],
            schema=DesignReport,
            deps=deps,
        )
        assert isinstance(retry_report, DesignReport)
        # LOGIC: keep whichever attempt has fewer fail issues. If the
        # retry made things WORSE (rare but possible), we keep the
        # original — otherwise we'd silently regress quality.
        if len([i for i in check_design_report(retry_report) if i.severity == "fail"]) < len(
            fail_issues
        ):
            report = retry_report
        else:
            log.warning("synthesizer: retry did not reduce fail-issues; keeping first attempt")

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

    # LOGIC: run the cheap (zero-LLM) quality gate. We log the issues
    # but do NOT block. The UI surfaces them as a banner so reviewers
    # know the report needs an extra eye. The agent retry loop (next
    # patch) uses the same issues to drive a single corrective re-prompt.
    issues = check_design_report(report)
    if issues:
        log.warning(
            "synthesizer: quality gate flagged %d issue(s) on %s: %s",
            len(issues),
            out_path.name,
            "; ".join(f"{i.field}({i.severity})" for i in issues),
        )

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
