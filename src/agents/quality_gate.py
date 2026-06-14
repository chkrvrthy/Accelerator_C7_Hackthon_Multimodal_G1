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

    # MULTI-FRAME RUNS: the synthesizer is required to emit
    # per_frame_scores for runs that cover 2+ frames. An empty dict here
    # means the user lost the per-frame heatmap — the primary visual
    # the multi-frame story sells. We flag it as 'warn' (not 'fail') so
    # the report still renders; the retry loop picks it up if enabled.
    n_frames = len(report.frame_labels)
    if n_frames > 1:
        if not report.per_frame_scores:
            issues.append(
                QualityIssue(
                    field="per_frame_scores",
                    reason=(
                        f"Multi-frame run ({n_frames} frames) emitted no "
                        "per_frame_scores; the per-frame heatmap will be "
                        "blank. Re-prompt the synthesizer with the "
                        "per_frame_scores contract."
                    ),
                    severity="warn",
                )
            )
        else:
            missing = sorted(set(report.frame_labels) - set(report.per_frame_scores.keys()))
            if missing:
                issues.append(
                    QualityIssue(
                        field="per_frame_scores",
                        reason=(
                            "per_frame_scores is missing entries for "
                            f"{', '.join(missing)}. Every uploaded frame "
                            "must have at least an 'overall' score."
                        ),
                        severity="warn",
                    )
                )
        # affected_frames on every recommendation should ideally cite
        # at least one frame label; warn (not fail) when none do.
        no_attribution = sum(1 for r in report.top_recommendations if not r.affected_frames)
        if (
            report.top_recommendations
            and no_attribution == len(report.top_recommendations)
        ):
            issues.append(
                QualityIssue(
                    field="top_recommendations[*].affected_frames",
                    reason=(
                        "Multi-frame run produced recommendations but none "
                        "cite which frame they affect. Re-prompt to "
                        "populate affected_frames for each recommendation."
                    ),
                    severity="warn",
                )
            )

    # SPECIALIST FAN-IN: every per-agent gate is folded into the report-
    # level gate so the renderer's "Review needed" banner can name the
    # offending agent (visual / ux / accessibility / brand / market).
    # Without this fan-in the per-agent checks were dead code — they
    # existed but nothing called them, so a thin visual narrative or an
    # empty market block silently slipped through. Each specialist's
    # field path stays scoped (e.g. "visual.narrative") so the user
    # immediately knows which slice to retry.
    if report.visual:
        issues.extend(check_visual(report.visual))
    if report.ux:
        issues.extend(check_ux(report.ux))
    if report.accessibility:
        issues.extend(check_accessibility(report.accessibility))
    if report.brand:
        issues.extend(check_brand(report.brand))
    if report.market:
        issues.extend(check_market(report.market))

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
    # SHALLOW-RESPONSE GUARD. When the LLM rejects strict json_schema and
    # falls through to plain json_object, some providers emit a minimal
    # JSON ({"palette": [...]}) and skip every str field. The schema
    # accepts it because every narrative field defaults to "". We catch
    # that "palette but no narrative" pattern explicitly so the user sees
    # a clear "visual narrative missing" banner instead of silently empty
    # accordions in the report.
    narrative_empty = (
        not (v.layout or "").strip()
        and not (v.hierarchy or "").strip()
        and not (v.typography or "").strip()
        and not (v.spacing_notes or "").strip()
    )
    if narrative_empty:
        issues.append(
            QualityIssue(
                field="visual.narrative",
                reason=(
                    "layout, hierarchy, typography and spacing all came back "
                    "empty — the model returned a minimal palette-only JSON. "
                    "Re-run, or try a higher-resolution screenshot so the "
                    "vision model has more to anchor on."
                ),
                severity="fail",
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
