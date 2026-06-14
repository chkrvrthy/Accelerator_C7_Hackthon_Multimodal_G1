"""Premium HTML rendering for the DesignReport.

OWNER: Person E
USED BY: ui/app.py.

Single-page report layout (top to bottom):
  1. Hero — large score number + 1-paragraph score_rationale.
  2. Executive summary — 60-100 word memo.
  3. Per-axis breakdown — five horizontal bars.
  4. Specialist run-status grid (ok / partial / failed / skipped).
  5. Quick-wins callout (high-impact + low-effort only).
  6. Top strengths — 3 distinguishing items.
  7. Ranked recommendations — priority chip, effort/impact pills,
     metric_lift, source citation.
  8. Collapsible specialist sections for the curious.

Every helper here is pure — no IO, no LLM calls. Easy to unit test.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from typing import Any

from src.schemas.outputs import DesignReport


def _ul(items: list[str]) -> str:
    """Render an escaped HTML list (items may contain pre-escaped markup)."""
    rows = "".join(f"<li>{item}</li>" for item in items)
    return f"<ul>{rows}</ul>"


def _score_anchor(score: float) -> str:
    """Map an overall score to its rubric anchor label."""
    if score >= 95:
        return "World-class"
    if score >= 80:
        return "Production-ready"
    if score >= 65:
        return "Needs polish"
    if score >= 50:
        return "Significant rework"
    return "Foundational issues"


def _bar_class(value: float) -> str:
    """Color a breakdown bar by health: ok / warn / fail."""
    if value >= 75:
        return ""
    if value >= 55:
        return "warn"
    return "fail"


def _status_grid(status: Mapping[str, str]) -> str:
    """Five-cell grid showing per-agent run status."""
    if not status:
        return ""
    order = ["visual", "ux", "accessibility", "brand", "market"]
    cells: list[str] = []
    for axis in order:
        state = status.get(axis, "skipped")
        cls = state if state in {"ok", "partial", "failed", "skipped"} else "skipped"
        cells.append(
            f'<div class="status-cell {cls}">'
            f'<span class="dot"></span>'
            f'<span class="name">{html.escape(axis)}</span>'
            f'<span class="state">{html.escape(cls)}</span>'
            "</div>"
        )
    return f'<div class="status-grid">{"".join(cells)}</div>'


def _breakdown_bars(breakdown: dict[str, float], default: float = 50.0) -> str:
    """Five horizontal bars, one per axis."""
    order = ["visual", "ux", "accessibility", "brand", "market"]
    rows: list[str] = []
    for axis in order:
        value = float(breakdown.get(axis, default))
        cls = _bar_class(value)
        width = max(0.0, min(100.0, value))
        rows.append(
            f'<div class="breakdown-row {cls}">'
            f'<span class="axis">{html.escape(axis)}</span>'
            f'<span class="bar"><span class="bar-fill" style="width: {width:.1f}%"></span></span>'
            f'<span class="num">{value:.0f}</span>'
            "</div>"
        )
    return f'<div class="breakdown">{"".join(rows)}</div>'


def _quick_wins_block(report: DesignReport) -> str:
    """Highlight high-impact, low-effort recommendations (the wins to ship first)."""
    wins = [r for r in report.top_recommendations if r.impact == "L" and r.effort == "S"]
    if not wins:
        return ""
    lines = []
    for r in wins[:2]:
        lift = f" — {html.escape(r.metric_lift)}" if r.metric_lift else ""
        lines.append(f"<b>#{r.priority}.</b> {html.escape(r.title)}{lift}")
    body = "<br>".join(lines)
    return (
        '<div class="quick-wins">'
        '<span class="quick-wins-icon">!</span>'
        '<div class="quick-wins-body">'
        '<div class="quick-wins-title">Quick wins — ship first</div>'
        f"<p>{body}</p>"
        "</div></div>"
    )


def _recommendation_card(r: Any) -> str:
    """Render one premium recommendation card with priority chip + meta row.

    For multi-frame runs the card also surfaces ``affected_frames`` as
    badges next to the title so a reviewer can scan "which screens are
    affected" without reading the rationale.
    """
    e = html.escape
    affected = list(getattr(r, "affected_frames", None) or [])
    frame_badges = ""
    if affected:
        chips = "".join(
            f'<span class="report-tag tag-frame">{e(label)}</span>' for label in affected
        )
        frame_badges = f'<span class="frame-badges">{chips}</span>'
    parts = [
        '<div class="priority-row">',
        f'<span class="report-tag tag-priority">{r.priority}</span>',
        f"<b>{e(r.title)}</b>",
        frame_badges,
        "</div>",
        f'<p class="rationale-text">{e(r.rationale)}</p>',
        '<div class="meta-row">',
        f'<span class="report-tag tag-effort">Effort {e(str(r.effort))}</span>',
        f'<span class="report-tag tag-impact">Impact {e(str(r.impact))}</span>',
    ]
    if r.metric_lift:
        parts.append(f'<span class="report-tag tag-lift">{e(r.metric_lift)}</span>')
    parts.append("</div>")
    if r.proof:
        parts.append(f'<span class="proof">Source · {e(r.proof)}</span>')
    return "".join(parts)


def _frames_strip(frame_labels: list[str]) -> str:
    """Render the labelled frame strip at the top of a multi-frame report."""
    if not frame_labels or len(frame_labels) <= 1:
        return ""
    chips = "".join(
        f'<span class="frame-chip"><span class="frame-chip-num">{i + 1}</span>'
        f"<span class=\"frame-chip-label\">{html.escape(label)}</span></span>"
        for i, label in enumerate(frame_labels)
    )
    return (
        '<div class="frames-strip">'
        '<span class="frames-strip-label">Frames reviewed</span>'
        f'<div class="frames-strip-chips">{chips}</div>'
        "</div>"
    )


def _per_frame_heatmap(
    frame_labels: list[str],
    per_frame_scores: dict[str, dict[str, float]],
) -> str:
    """Render a small per-frame heatmap when the synthesizer populated it.

    Layout: one row per frame label (in the order they appear in
    ``frame_labels``, not dict insertion order), columns for each axis
    the synthesizer chose to score. Empty axes are simply absent — we
    do not pad with zeros because a missing axis is not the same as 0.
    """
    if not frame_labels or len(frame_labels) <= 1 or not per_frame_scores:
        return ""

    # Discover the union of axes present anywhere, but always lead with
    # 'overall' when present so the eye lands there first.
    axes_seen: list[str] = []
    for label in frame_labels:
        for axis in (per_frame_scores.get(label) or {}).keys():
            if axis not in axes_seen:
                axes_seen.append(axis)
    ordered_axes: list[str] = []
    if "overall" in axes_seen:
        ordered_axes.append("overall")
    for canonical in ("visual", "ux", "accessibility", "brand", "market"):
        if canonical in axes_seen and canonical not in ordered_axes:
            ordered_axes.append(canonical)
    for extra in axes_seen:
        if extra not in ordered_axes:
            ordered_axes.append(extra)

    if not ordered_axes:
        return ""

    head_cells = "".join(f"<th>{html.escape(a)}</th>" for a in ordered_axes)
    rows: list[str] = []
    for label in frame_labels:
        scores = per_frame_scores.get(label) or {}
        cells: list[str] = []
        for axis in ordered_axes:
            value = scores.get(axis)
            if value is None:
                cells.append('<td class="cell empty">—</td>')
                continue
            cls = _bar_class(float(value))
            cells.append(
                f'<td class="cell {cls}"><span class="cell-num">{float(value):.0f}</span></td>'
            )
        rows.append(
            f'<tr><th class="row-label">{html.escape(label)}</th>{"".join(cells)}</tr>'
        )

    return (
        '<div class="per-frame-heatmap">'
        '<table class="heatmap-table">'
        f"<thead><tr><th></th>{head_cells}</tr></thead>"
        f'<tbody>{"".join(rows)}</tbody>'
        "</table>"
        "</div>"
    )


def render_report(report: DesignReport | dict[str, Any] | None) -> str:
    """Format the latest report as a self-contained, premium HTML block.

    Layout (top to bottom):
      1. Hero: large score number + 1-paragraph score_rationale (the WHY).
      2. Breakdown: five horizontal bars (visual, ux, accessibility, brand, market).
      3. Per-agent run status grid (ok / partial / failed / skipped).
      4. Quick wins callout (high-impact + low-effort only).
      5. Top strengths (3 distinguishing items).
      6. Ranked recommendations (priority chip, effort/impact pills,
         metric_lift, source citation).
      7. Collapsible specialist sections for the curious.
    """
    if report is None:
        return """
<div class="result-card">
  <h3>No report yet</h3>
  <p>Run an analysis from the Analyze tab. The score, justification,
  per-axis breakdown, and prioritized recommendations will appear here.</p>
</div>
"""
    rep: DesignReport = DesignReport.model_validate(report) if isinstance(report, dict) else report
    report = rep

    e = html.escape
    score = report.overall_score or 0.0
    anchor = _score_anchor(score)

    # --- runtime metadata --------------------------------------------- #
    meta_parts: list[str] = []
    if report.run_id:
        meta_parts.append(f"run · {e(report.run_id)}")
    if report.analyzed_at:
        meta_parts.append(e(report.analyzed_at))
    meta_line = " &nbsp;·&nbsp; ".join(meta_parts) if meta_parts else ""

    rationale = e(
        report.score_rationale
        or (
            "No rationale was returned. The synthesizer must explain the "
            "score; re-run if this persists."
        )
    )
    hero = (
        '<div class="report-hero">'
        '<div class="score-block">'
        '<span class="label">Overall</span>'
        f'<span class="value">{score:.1f}</span>'
        f'<span class="anchor">{e(anchor)}</span>'
        "</div>"
        "<div>"
        '<div class="rationale-label">Why this score</div>'
        f'<p class="rationale">{rationale}</p>'
        f'<div class="score-meta">{meta_line}</div>'
        "</div></div>"
    )

    parts: list[str] = [
        '<div class="report-wrap">',
        "<h2>Design report</h2>",
        '<p class="report-subtitle">'
        "Synthesized from five specialist agents — visual, UX, accessibility, "
        "brand, market. Recommendations are ranked by impact-over-effort and "
        "cite the agent finding that produced them."
        "</p>",
    ]

    # Quality-gate banner: a yellow stripe when the report contains
    # placeholder-thin fields. Pure-Python check — no extra LLM calls.
    from src.agents.quality_gate import check_design_report

    issues = check_design_report(report)
    fails = [i for i in issues if i.severity == "fail"]
    warns = [i for i in issues if i.severity == "warn"]
    if fails or warns:
        bullets = "".join(
            f"<li><b>{e(i.field)}</b> — {e(i.reason)}</li>" for i in (fails + warns)[:5]
        )
        # Plain-language explainer collapsed by default. The user has to
        # *want* the detail; we never lecture them above the fold. The
        # earlier copy left judges asking "what does provisional mean?"
        # so we now spell it out: which numbers, why provisional, how to
        # fix. Single <details> keeps the banner compact.
        explainer = (
            '<details class="quality-banner-explain">'
            "<summary>What does this mean?</summary>"
            "<ul class=\"explainer\">"
            "<li><b>Review needed</b> — at least one specialist agent "
            "returned thin or placeholder content. The report still "
            "renders so you can read what *did* come back, but the score "
            "and recommendations should be treated as a draft, not a "
            "verdict.</li>"
            "<li><b>Provisional numbers</b> — the score breakdown and "
            "any <i>+X% lift</i> hints below are estimates from the "
            "agents that fired cleanly; the flagged agent's slice is "
            "either missing or below the quality bar, so the math is "
            "skewed.</li>"
            "<li><b>How to fix</b> — re-run the analysis "
            "(transient model errors are usually one-shot), try a "
            "higher-resolution screenshot, or switch the model in "
            ".env (DEFAULT_MODEL → openai/gpt-4o or anthropic/"
            "claude-3.5-sonnet for vision-heavy runs).</li>"
            "</ul>"
            "</details>"
        )
        parts.append(
            '<div class="quality-banner">'
            '<span class="quality-banner-icon">!</span>'
            "<div>"
            '<div class="quality-banner-title">Review needed</div>'
            f"<p>{len(fails)} blocking issue(s) and {len(warns)} warning(s) "
            "in this report. The flagged sections below are draft-quality "
            "until you re-run.</p>"
            f"<ul>{bullets}</ul>"
            f"{explainer}"
            "</div>"
            "</div>"
        )

    if report.executive_summary:
        parts.append(
            '<div class="exec-summary">'
            '<div class="exec-summary-label">Executive summary</div>'
            f"<p>{e(report.executive_summary)}</p>"
            "</div>"
        )

    parts.append(hero)

    # --- multi-frame: labelled strip + per-frame heatmap ------------ #
    parts.append(_frames_strip(report.frame_labels))

    # --- per-axis breakdown bars ------------------------------------- #
    if report.score_breakdown or any(
        getattr(report, k) is not None for k in ("visual", "ux", "accessibility", "brand", "market")
    ):
        parts.append("<h3>Per-axis breakdown</h3>")
        parts.append(_breakdown_bars(report.score_breakdown))

    # Per-frame heatmap lives directly under the global breakdown so the
    # eye's progression is global -> per-frame -> per-axis recommendations.
    heatmap_html = _per_frame_heatmap(report.frame_labels, report.per_frame_scores)
    if heatmap_html:
        parts.append("<h3>Per-frame breakdown</h3>")
        parts.append(heatmap_html)

    # --- agent run status -------------------------------------------- #
    if report.analysis_status:
        parts.append("<h3>Specialist status</h3>")
        parts.append(_status_grid(report.analysis_status))

    # --- quick wins -------------------------------------------------- #
    parts.append(_quick_wins_block(report))

    # --- strengths --------------------------------------------------- #
    parts.append("<h3>Top strengths</h3>")
    parts.append(_ul([e(s) for s in report.top_strengths] or ["No strengths returned yet."]))

    # --- prioritized recommendations -------------------------------- #
    parts.append("<h3>Prioritized recommendations</h3>")
    if report.top_recommendations:
        items = "".join(f"<li>{_recommendation_card(r)}</li>" for r in report.top_recommendations)
        parts.append(f'<ul class="rec-list">{items}</ul>')
    else:
        parts.append(_ul(["No recommendations returned yet."]))

    # --- collapsible specialist details ------------------------------ #
    if report.visual:
        # SHALLOW-RESPONSE LANDING. When the LLM rejects strict
        # json_schema and falls through to plain json_object, some
        # providers return a palette-only JSON. The schema accepts it
        # because every str field defaults to "" — but rendering "Not
        # returned" three times in a row reads as a UI bug, not a model
        # bug. We surface that case explicitly with a calm one-liner so
        # the user knows what happened and what to do.
        narrative_empty = not (
            (report.visual.layout or "").strip()
            or (report.visual.hierarchy or "").strip()
            or (report.visual.typography or "").strip()
            or (report.visual.spacing_notes or "").strip()
        )
        rows = [
            f"Layout: {e(report.visual.layout) if report.visual.layout else '<i>not captured</i>'}",
            f"Hierarchy: {e(report.visual.hierarchy) if report.visual.hierarchy else '<i>not captured</i>'}",
            f"Density score: {report.visual.density_score:.1f}/100",
        ]
        if narrative_empty:
            rows.append(
                "<i>Note: the vision model returned only a palette this run "
                "(no narrative). Re-run, or switch DEFAULT_MODEL in .env "
                "to a vision-strong model (openai/gpt-4o, anthropic/"
                "claude-3.5-sonnet) and try again.</i>"
            )
        body = _ul(rows)
        parts.append(
            f'<details class="specialist"><summary>Visual analysis</summary>'
            f'<div class="body">{body}</div></details>'
        )
    if report.ux:
        ux_items = [
            f"Cognitive load score: {report.ux.cognitive_load_score:.1f}/100",
            f"Heuristic violations: {len(report.ux.heuristic_violations)}",
            f"Friction points: {len(report.ux.friction_points)}",
        ]
        parts.append(
            '<details class="specialist"><summary>UX critique</summary>'
            f'<div class="body">{_ul(ux_items)}</div></details>'
        )
    if report.accessibility:
        ac = report.accessibility
        pass_text = (
            "pass"
            if ac.contrast_pass is True
            else "needs review" if ac.contrast_pass is False else "not measured"
        )
        ac_items = [
            f"Contrast: {pass_text}",
            f"WCAG findings: {len(ac.wcag_findings)}",
            (
                f"Estimated min touch target: {ac.est_min_touch_target_px}px"
                if ac.est_min_touch_target_px is not None
                else "Touch target: not measured"
            ),
        ]
        parts.append(
            '<details class="specialist"><summary>Accessibility</summary>'
            f'<div class="body">{_ul(ac_items)}</div></details>'
        )
    if report.brand:
        br = report.brand
        br_items = [
            f"Consistency score: {br.consistency_score:.1f}/100",
            f"Color drift: {e(br.color_drift or 'not measured')}",
            f"Type drift: {e(br.type_drift or 'not measured')}",
            f"Component drift: {e(br.component_drift or 'not measured')}",
        ]
        parts.append(
            '<details class="specialist"><summary>Brand consistency</summary>'
            f'<div class="body">{_ul(br_items)}</div></details>'
        )
    if report.market:
        mk = report.market
        mk_items = [f"Trend: {e(t)}" for t in (mk.trends or [])] or ["No trends returned."]
        if mk.competitors:
            mk_items.append("Competitors cited: " + ", ".join(e(c.name) for c in mk.competitors))
        parts.append(
            '<details class="specialist"><summary>Market signals</summary>'
            f'<div class="body">{_ul(mk_items)}</div></details>'
        )

    parts.append("</div>")
    return "\n".join(parts)
