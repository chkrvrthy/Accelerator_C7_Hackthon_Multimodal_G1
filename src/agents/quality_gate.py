"""Quality gate — content-level validation for agent outputs.

OWNER: Person A
SPRINT CONCEPTS: Sprint 5 (eval / quality), Sprint 6 (resilience).

WHY THIS FILE EXISTS
--------------------
Pydantic validates *types*. It cannot validate that a string is *useful*.
An LLM is happy to return:

    BrandConsistency(
        consistency_score=0.0,
        color_drift="not measured",
        type_drift="not measured",
        ...
    )

That payload PASSES every type check and produces a useless report. The
quality gate is a tiny set of pure-function checks that flag this kind
of placeholder-thin content so the UI can:

  1. Show a "review needed" banner above the report.
  2. (Optionally, in the agent retry loop) tell the LLM exactly what was
     thin and ask for one corrective pass — a focused single retry,
     not a blanket re-roll.

Cost discipline:
- Every check is pure Python; ZERO LLM calls.
- Used by ``run_with_schema`` only as a hint for the corrective-retry
  decision; the report renders even when the gate flags issues. We
  never block the UI on quality.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.schemas.outputs import (
    AccessibilityReport,
    BrandConsistency,
    DesignReport,
    MarketResearch,
    UXCritique,
    VisualAnalysis,
)


@dataclass(frozen=True)
class QualityIssue:
    """One placeholder-thin field flagged by the gate.

    Fields:
        field: dotted path inside the schema, e.g. "executive_summary".
        reason: short, user-facing explanation.
        severity: "info" / "warn" / "fail". Renderer color-codes.
    """

    field: str
    reason: str
    severity: str = "warn"


# Word-count thresholds. Tuned to be slightly under the prompt's stated
# minimums so an off-by-a-few-words drift does not flag a perfectly fine
# report. Numbers chosen by reading 10+ sample outputs from real LLM runs.
_MIN_EXEC_SUMMARY_WORDS = 50
_MIN_SCORE_RATIONALE_WORDS = 32
_MIN_RECS = 3


def check_design_report(report: DesignReport) -> list[QualityIssue]:
    """Return all placeholder-thin issues in a DesignReport.

    Empty list = passes. Non-empty list = the UI shows a banner; if the
    agent retry loop is enabled, this is also the corrective feedback
    fed back into the synthesizer.
    """
    issues: list[QualityIssue] = []

    # Executive summary
    if _word_count(report.executive_summary) < _MIN_EXEC_SUMMARY_WORDS:
        issues.append(
            QualityIssue(
                field="executive_summary",
                reason=(
                    f"executive_summary is too short "
                    f"({_word_count(report.executive_summary)} words; "
                    f"min {_MIN_EXEC_SUMMARY_WORDS}). "
                    "Re-prompt to require a 60-100 word narrative paragraph."
                ),
                severity="fail",
            )
        )

    # Score rationale
    if _word_count(report.score_rationale) < _MIN_SCORE_RATIONALE_WORDS:
        issues.append(
            QualityIssue(
                field="score_rationale",
                reason=(
                    f"score_rationale is too short "
                    f"({_word_count(report.score_rationale)} words; "
                    f"min {_MIN_SCORE_RATIONALE_WORDS}). "
                    "Re-prompt to require 40-80 words with the breakdown values."
                ),
                severity="fail",
            )
        )

    # Score breakdown coverage
    expected_axes = {"visual", "ux", "accessibility", "brand", "market"}
    missing_axes = sorted(expected_axes - set(report.score_breakdown.keys()))
    if missing_axes:
        issues.append(
            QualityIssue(
                field="score_breakdown",
                reason=(f"score_breakdown is missing axes: {', '.join(missing_axes)}."),
                severity="warn",
            )
        )

    # Recommendation count
    if len(report.top_recommendations) < _MIN_RECS:
        issues.append(
            QualityIssue(
                field="top_recommendations",
                reason=(
                    f"Only {len(report.top_recommendations)} recommendation(s); "
                    f"the report needs at least {_MIN_RECS}."
                ),
                severity="fail",
            )
        )

    # Per-recommendation completeness
    for r in report.top_recommendations:
        if not r.proof:
            issues.append(
                QualityIssue(
                    field=f"top_recommendations[{r.priority}].proof",
                    reason=(
                        f"Recommendation #{r.priority} ({r.title!r}) has no "
                        "proof citation. Without it the rationale is unauditable."
                    ),
                    severity="warn",
                )
            )
        if r.impact == "L" and not r.metric_lift:
            issues.append(
                QualityIssue(
                    field=f"top_recommendations[{r.priority}].metric_lift",
                    reason=(
                        f"High-impact recommendation #{r.priority} has no "
                        "metric_lift; specify the expected business outcome."
                    ),
                    severity="info",
                )
            )

    # Strengths
    if len(report.top_strengths) < 3:
        issues.append(
            QualityIssue(
                field="top_strengths",
                reason=(
                    f"Only {len(report.top_strengths)} strengths returned; "
                    "the report should always name 3 distinguishing strengths."
                ),
                severity="warn",
            )
        )

    return issues


# --------------------------------------------------------------------------- #
# Specialist-level gates                                                      #
# --------------------------------------------------------------------------- #
# Each specialist gate is small and pure. They are used by the agent retry
# loop and by the synthesizer's degraded-report logic to decide whether a
# given specialist's output is reliable enough to feed in.


def check_visual(v: VisualAnalysis) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if len(v.palette) < 3:
        issues.append(
            QualityIssue(
                "visual.palette",
                f"palette has only {len(v.palette)} colors; want 3-6 hex codes.",
            )
        )
    if v.density_score in {0.0, 50.0}:
        issues.append(
            QualityIssue(
                "visual.density_score",
                "density_score looks defaulted (0 or 50); pick from the rubric.",
            )
        )
    if len(v.observations) < 3:
        issues.append(
            QualityIssue(
                "visual.observations",
                f"only {len(v.observations)} observations; want 5-10 specific facts.",
            )
        )
    return issues


def check_ux(u: UXCritique) -> list[QualityIssue]:
    if not u.heuristic_violations and not u.friction_points:
        return [
            QualityIssue(
                "ux",
                "no heuristic violations and no friction points returned — "
                "either re-prompt or accept that the screen is exemplary.",
                severity="info",
            )
        ]
    return []


def check_accessibility(a: AccessibilityReport) -> list[QualityIssue]:
    if not a.wcag_findings and a.contrast_pass is None:
        return [
            QualityIssue(
                "accessibility",
                "no WCAG findings AND no measured contrast — output is empty. "
                "Re-prompt with the WCAG 2.2 SC list.",
                severity="fail",
            )
        ]
    return []


def check_brand(b: BrandConsistency) -> list[QualityIssue]:
    placeholder = "not measured"
    drifts = (b.color_drift or "", b.type_drift or "", b.component_drift or "")
    if all(placeholder in d.lower() or d.startswith("(no") for d in drifts):
        return [
            QualityIssue(
                "brand",
                "all three drift fields are placeholders. Either ingest brand "
                "references or re-prompt with the side-by-side composite.",
                severity="warn",
            )
        ]
    return []


def check_market(m: MarketResearch) -> list[QualityIssue]:
    if not m.competitors and not m.trends:
        return [
            QualityIssue(
                "market",
                "neither competitors nor trends returned — search hits were "
                "probably empty. Either ingest more search context or skip.",
                severity="warn",
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _word_count(s: str) -> int:
    """Whitespace-split word count; safe on None / empty."""
    return len((s or "").split())


def format_issues_for_prompt(issues: list[QualityIssue]) -> str:
    """Render quality issues as a corrective-feedback block for re-prompting.

    Used by the agent retry loop. Format is intentionally terse — every
    extra token here costs money and adds noise for the model.
    """
    if not issues:
        return ""
    lines = ["The previous response failed these quality checks; fix them:"]
    for i in issues:
        lines.append(f"- {i.field}: {i.reason}")
    return "\n".join(lines)
