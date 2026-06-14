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


def test_graph_state_image_path_populates_image_paths():
    # Back-compat: legacy callers pass image_path="x.png"; the model
    # validator should mirror that into image_paths so vision agents
    # always have a list to iterate.
    s = GraphState(image_path="x.png")
    assert s.image_paths == ["x.png"]
    assert s.image_path == "x.png"


def test_graph_state_image_paths_populates_image_path():
    # New comparison-mode callers pass image_paths=[...]; image_path
    # becomes the primary (first) frame so single-image pre-tools work.
    s = GraphState(image_paths=["a.png", "b.png", "c.png"])
    assert s.image_paths == ["a.png", "b.png", "c.png"]
    assert s.image_path == "a.png"


def test_graph_state_requires_at_least_one_image():
    with pytest.raises(ValidationError):
        GraphState()


def test_graph_state_frame_labels_default_to_filename_stem():
    # When the caller omits frame_labels every entry falls back to the
    # filename stem so downstream agents always have a name to cite.
    s = GraphState(image_paths=["data/uploads/Hero.png", "data/uploads/Pricing.jpg"])
    assert s.frame_labels == ["Hero", "Pricing"]


def test_graph_state_frame_labels_partial_input_padded():
    # When the caller supplies some labels but not all, the missing
    # ones fill from filenames so the output is always parallel to
    # image_paths.
    s = GraphState(
        image_paths=["a.png", "b.png", "c.png"],
        frame_labels=["Hero", ""],
    )
    assert s.frame_labels == ["Hero", "b", "c"]


def test_recommendation_affected_frames_defaults_empty():
    r = Recommendation(title="Raise contrast")
    assert r.affected_frames == []


def test_design_report_per_frame_scores_are_clamped():
    # The clamp validator must coerce out-of-range values to [0, 100]
    # so a stray 150 from the LLM never paints a broken bar.
    rep = DesignReport(
        per_frame_scores={
            "Hero": {"overall": 78.0, "visual": 82.0},
            "Pricing": {"overall": 150.0, "ux": -10.0},
        }
    )
    assert rep.per_frame_scores["Hero"]["overall"] == 78.0
    assert rep.per_frame_scores["Pricing"]["overall"] == 100.0
    assert rep.per_frame_scores["Pricing"]["ux"] == 0.0


def test_design_report_carries_frame_labels_field():
    rep = DesignReport(
        frame_labels=["Hero", "Pricing", "Dashboard"],
        top_recommendations=[
            Recommendation(
                title="Raise CTA contrast",
                effort="S",
                impact="L",
                affected_frames=["Pricing", "Dashboard"],
            ),
        ],
    )
    # Per-recommendation affected_frames are preserved verbatim.
    assert rep.top_recommendations[0].affected_frames == ["Pricing", "Dashboard"]
    assert rep.frame_labels == ["Hero", "Pricing", "Dashboard"]


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
