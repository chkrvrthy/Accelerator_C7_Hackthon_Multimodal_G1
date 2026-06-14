"""Full graph runs end-to-end with fakes.

This test is the smoke check Person A relies on after every commit. If this
goes red, the demo is at risk.
"""

from __future__ import annotations

import pytest

from src.agents.graph import run_graph
from src.schemas.outputs import DesignReport

pytestmark = pytest.mark.person_a


def test_run_graph_returns_design_report(fake_deps, sample_image):
    rep = run_graph(sample_image, instructions="audience: Indian retail", deps=fake_deps)
    assert isinstance(rep, DesignReport)
    assert rep.visual is not None and rep.ux is not None and rep.brand is not None


def test_run_graph_persists_report_to_disk(fake_deps, sample_image, tmp_settings):
    rep = run_graph(sample_image, deps=fake_deps)
    files = list(tmp_settings.report_dir.glob("*.json"))
    assert files, f"synthesizer should write a report under {tmp_settings.report_dir}"
    assert isinstance(rep, DesignReport)


def test_run_graph_multi_frame_with_labels(fake_deps, sample_image):
    """Multi-frame run threads labels through and stamps them on the report.

    Three copies of the bundled sample stand in for three frames of one
    product. Labels are user-supplied; the orchestrator is expected to
    expose them on ``DesignReport.frame_labels`` exactly as passed, and
    every recommendation's ``affected_frames`` must contain ONLY labels
    from this set (the synthesizer scrubs hallucinations server-side).
    """
    labels = ["Hero", "Pricing", "Dashboard"]
    rep = run_graph(
        [sample_image, sample_image, sample_image],
        instructions="audience: enterprise IT; brand: technical",
        frame_labels=labels,
        deps=fake_deps,
    )
    assert isinstance(rep, DesignReport)
    assert rep.frame_labels == labels
    valid = set(labels)
    for r in rep.top_recommendations:
        for f in r.affected_frames:
            assert f in valid, f"recommendation cited unknown frame {f!r}"


def test_run_graph_single_frame_keeps_multi_frame_fields_empty(fake_deps, sample_image):
    """Single-frame runs keep frame_labels / per_frame_scores empty.

    The UI uses ``len(frame_labels) > 1`` to decide whether to render
    the per-frame strip and heatmap. Regression-protect that contract.
    """
    rep = run_graph(sample_image, deps=fake_deps)
    assert rep.frame_labels == []
    assert rep.per_frame_scores == {}
    for r in rep.top_recommendations:
        assert r.affected_frames == []
