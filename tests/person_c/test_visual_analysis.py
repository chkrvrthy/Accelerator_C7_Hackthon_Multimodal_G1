"""Visual Analysis agent against fake_deps."""

from __future__ import annotations

import re

import pytest

from src.agents import visual_analysis
from src.schemas.outputs import GraphState, VisualAnalysis
from src.utils.prompts import visual_analysis_user

pytestmark = pytest.mark.person_c

_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def test_visual_run_returns_visual_analysis(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image), instructions=None)
    out = visual_analysis.run(state, fake_deps)
    assert "visual" in out and isinstance(out["visual"], VisualAnalysis)


def test_visual_run_palette_non_empty(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = visual_analysis.run(state, fake_deps)
    assert out["visual"].palette  # at least one color


def test_visual_run_palette_all_hex(fake_deps, sample_image):
    """Every palette entry that survives the agent is a valid hex color."""
    state = GraphState(image_path=str(sample_image))
    out = visual_analysis.run(state, fake_deps)
    assert all(_HEX.match(c) for c in out["visual"].palette)


def test_visual_user_prompt_includes_instructions():
    """Free-form UI instructions are folded into the user message."""
    state = GraphState(image_path="x.png", instructions="Audience: retail banking, India")
    user = visual_analysis_user(state)
    assert "retail banking, India" in user


def test_visual_user_prompt_handles_no_instructions():
    state = GraphState(image_path="x.png", instructions=None)
    user = visual_analysis_user(state)
    assert "(none)" in user
