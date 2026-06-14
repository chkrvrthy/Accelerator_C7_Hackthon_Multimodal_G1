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


def test_a11y_contrast_measurement_uses_wcag_relative_luminance(tmp_path):
    try:
        import cv2
        import numpy as np
    except ImportError:
        pytest.skip("opencv not installed")

    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[:, :10] = (20, 20, 20)
    image[:, 10:] = (120, 120, 120)
    path = tmp_path / "low_contrast.png"
    cv2.imwrite(str(path), image)

    assert accessibility._measure_contrast_pass(str(path)) is False


def test_a11y_contrast_measurement_passes_high_contrast_pair(tmp_path):
    try:
        import cv2
        import numpy as np
    except ImportError:
        pytest.skip("opencv not installed")

    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[:, 10:] = (255, 255, 255)
    path = tmp_path / "high_contrast.png"
    cv2.imwrite(str(path), image)

    assert accessibility._measure_contrast_pass(str(path)) is True
