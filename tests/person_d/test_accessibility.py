"""Accessibility agent against fake_deps."""
from __future__ import annotations

import re

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


def test_a11y_findings_have_evidence_and_recommendation(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = accessibility.run(state, fake_deps)
    rep = out["accessibility"]
    for f in rep.wcag_findings:
        assert f.evidence and f.recommendation


def test_a11y_findings_cite_wcag_criterion(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = accessibility.run(state, fake_deps)
    rep = out["accessibility"]
    for f in rep.wcag_findings:
        assert re.match(r"^\d+\.\d+\.\d+$", f.criterion)


def test_a11y_contrast_pass_measured_when_opencv_present(fake_deps, sample_image):
    try:
        import cv2  # noqa: F401
    except ImportError:
        pytest.skip("opencv not installed")

    state = GraphState(image_path=str(sample_image))
    out = accessibility.run(state, fake_deps)
    rep = out["accessibility"]
    assert rep.contrast_pass is not None
    assert isinstance(rep.contrast_pass, bool)
