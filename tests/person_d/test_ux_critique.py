"""UX Critique agent against fake_deps."""

from __future__ import annotations

import pytest

from src.agents import ux_critique
from src.schemas.outputs import GraphState, UXCritique

pytestmark = pytest.mark.person_d


def test_ux_run_returns_ux_critique(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image), instructions="be terse")
    out = ux_critique.run(state, fake_deps)
    assert "ux" in out and isinstance(out["ux"], UXCritique)


def test_ux_findings_have_evidence(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = ux_critique.run(state, fake_deps)
    crit = out["ux"]
    for f in crit.heuristic_violations:
        assert f.evidence and f.recommendation


def test_ux_friction_points_have_evidence_when_present(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = ux_critique.run(state, fake_deps)
    crit = out["ux"]
    for f in crit.friction_points:
        assert f.evidence and f.recommendation
