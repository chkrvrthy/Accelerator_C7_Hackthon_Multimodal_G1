"""Visual Analysis agent against fake_deps."""
from __future__ import annotations

import pytest

from src.agents import visual_analysis
from src.schemas.outputs import GraphState, VisualAnalysis

pytestmark = pytest.mark.person_c


def test_visual_run_returns_visual_analysis(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image), instructions=None)
    out = visual_analysis.run(state, fake_deps)
    assert "visual" in out and isinstance(out["visual"], VisualAnalysis)


def test_visual_run_palette_non_empty(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = visual_analysis.run(state, fake_deps)
    assert out["visual"].palette  # at least one color
