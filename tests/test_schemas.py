"""Schema validation contracts (cross-cutting, run by everyone).

These tests guard the SHAPE of the data flowing between modules. If anyone
adds a required field to a Pydantic model without updating fakes, these
tests catch it before the demo.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.outputs import (
    AccessibilityReport,
    BrandConsistency,
    DesignReport,
    Finding,
    GraphState,
    MarketResearch,
    Recommendation,
    RetrievedRef,
    SearchResult,
    Severity,
    UXCritique,
    VisualAnalysis,
    WCAGFinding,
)


def test_severity_enum_values():
    assert {s.value for s in Severity} == {"low", "medium", "high", "critical"}


def test_finding_minimal_construction():
    f = Finding(
        title="t",
        description="d",
        severity=Severity.LOW,
        evidence="e",
        recommendation="r",
    )
    assert f.severity is Severity.LOW


def test_visual_analysis_drops_empty_palette_strings():
    v = VisualAnalysis(palette=["#000", "", "#FFF"])
    assert v.palette == ["#000", "#FFF"]


def test_score_bounds_enforced():
    with pytest.raises(ValidationError):
        VisualAnalysis(density_score=150.0)


def test_design_report_with_specialists_round_trips():
    rep = DesignReport(
        overall_score=72.5,
        top_strengths=["x", "y", "z"],
        top_recommendations=[
            Recommendation(priority=1, title="t", rationale="r", effort="S", impact="L"),
        ],
        visual=VisualAnalysis(palette=["#fff"]),
        ux=UXCritique(cognitive_load_score=50.0),
        accessibility=AccessibilityReport(contrast_pass=True),
        market=MarketResearch(),
        brand=BrandConsistency(consistency_score=80.0),
    )
    parsed = DesignReport.model_validate(rep.model_dump())
    assert parsed.overall_score == 72.5
    assert parsed.visual is not None
    assert parsed.brand is not None and parsed.brand.consistency_score == 80.0


def test_graph_state_partial_validates():
    s = GraphState(image_path="x.png", instructions=None)
    assert s.visual is None and s.report is None


def test_wcag_finding_requires_numeric_criterion():
    f = WCAGFinding(
        title="t",
        description="d",
        severity=Severity.HIGH,
        evidence="e",
        recommendation="r",
        criterion="1.4.3",
    )
    assert f.criterion == "1.4.3"


def test_wcag_finding_drops_bad_criterion():
    # Resilience contract: a malformed criterion is silently coerced to
    # "" so a single LLM quirk never crashes the run. Prompt remains the
    # enforcement mechanism for citation quality.
    f = WCAGFinding(
        title="t",
        description="d",
        severity=Severity.HIGH,
        evidence="e",
        recommendation="r",
        criterion="contrast",
    )
    assert f.criterion == ""


def test_finding_backfills_missing_text_fields():
    # Resilience contract: when the LLM omits description/evidence/
    # recommendation we cross-fill from siblings so the UI always has copy.
    f = Finding(title="Primary CTA buried", severity=Severity.HIGH)
    assert f.description  # cross-filled, not blank
    assert f.evidence
    assert f.recommendation
    # Title is the last-resort fallback; everything points at it here.
    assert f.recommendation == "Primary CTA buried"


def test_finding_severity_defaults_to_medium():
    # Resilience contract: omitted severity is treated as MEDIUM rather
    # than crashing validation.
    f = Finding(title="t")
    assert f.severity is Severity.MEDIUM


def test_recommendation_minimal_construction():
    # Resilience contract: only `title` is required; everything else has
    # a sensible default so a thin LLM emission still produces a renderable
    # recommendation.
    r = Recommendation(title="Raise CTA contrast")
    assert r.priority >= 1  # default 999, will be renumbered by report validator
    assert r.effort == "M"
    assert r.impact == "M"
    assert r.rationale == "Raise CTA contrast"  # backfilled from title


def test_design_report_renumbers_default_priorities_densely():
    # When the LLM omits all priorities they collapse to 999. The report
    # validator must renumber 1..N stably (preserving emit order) instead
    # of deduping on priority and silently dropping all but one.
    rep = DesignReport(
        top_recommendations=[
            Recommendation(title="A"),
            Recommendation(title="B"),
            Recommendation(title="C"),
        ],
    )
    assert [r.priority for r in rep.top_recommendations] == [1, 2, 3]
    assert [r.title for r in rep.top_recommendations] == ["A", "B", "C"]


def test_retrieved_ref_score_is_float():
    r = RetrievedRef(id="a", score=0.42, image_path="x.png", metadata={})
    assert isinstance(r.score, float)


def test_search_result_required_fields():
    r = SearchResult(title="t", url="https://x", snippet="s")
    assert r.title == "t"
