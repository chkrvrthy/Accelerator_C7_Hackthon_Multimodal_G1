"""Accessibility agent against fake_deps."""
from __future__ import annotations

import pytest

from src.agents import accessibility
from src.schemas.outputs import AccessibilityReport, GraphState

pytestmark = pytest.mark.person_d


def test_a11y_run_returns_report(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = accessibility.run(state, fake_deps)
    rep = out["accessibility"]
    assert isinstance(rep, AccessibilityReport)


def test_a11y_findings_carry_severity(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = accessibility.run(state, fake_deps)
    rep = out["accessibility"]
    for f in rep.wcag_findings:
        assert f.severity is not None
