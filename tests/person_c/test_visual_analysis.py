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
    # Representation-agnostic: any "none / no" sentinel for missing instructions
    # works. Locks the *behavior*, not the exact phrase.
    assert "none" in user.lower()


def test_is_shallow_visual_detector():
    """The shallow-response detector flags palette-only payloads
    while letting through legitimate-but-terse responses."""
    only_palette = VisualAnalysis(palette=["#0A2540", "#635BFF", "#FFFFFF"])
    rich = VisualAnalysis(
        layout="Two-column hero",
        hierarchy="Headline first",
        palette=["#0A2540"],
        typography="geometric sans 700/400",
        spacing_notes="8 px grid",
        density_score=35.0,
        observations=["a", "b", "c", "d", "e"],
    )
    assert visual_analysis._is_shallow_visual(only_palette) is True
    assert visual_analysis._is_shallow_visual(rich) is False


def test_visual_run_retries_on_shallow_response(sample_image):
    """When the LLM returns palette-only, the agent re-prompts once
    and the corrected response replaces the partial one. This is the
    self-heal loop for the gpt-4o-mini multi-image bug."""
    from src.agents.base import AgentDeps
    from src.fakes.fake_llm import FakeLLM
    from src.fakes.fake_retriever import FakeRetriever
    from src.fakes.fake_search import FakeSearch

    class _RecoveringVision:
        def __init__(self) -> None:
            self.calls = 0

        def analyze(self, *, system, user, images, schema, model=None):
            self.calls += 1
            if self.calls == 1:
                return VisualAnalysis(palette=["#0A2540", "#635BFF", "#FFFFFF"])
            return VisualAnalysis(
                layout="Two-column hero (60/40)",
                hierarchy="Headline leads, then CTA",
                palette=["#0A2540", "#635BFF", "#FFFFFF"],
                typography="geometric sans 700/400",
                spacing_notes="8 px grid; 24 px gutters",
                density_score=35.0,
                observations=["o1", "o2", "o3", "o4", "o5"],
            )

    vision = _RecoveringVision()
    deps = AgentDeps(
        llm=FakeLLM(), vision=vision, retriever=FakeRetriever(), search=FakeSearch()
    )
    state = GraphState(image_path=str(sample_image), image_paths=[str(sample_image)])
    out = visual_analysis.run(state, deps)
    v = out["visual"]
    assert vision.calls == 2, "the agent must retry exactly once on a shallow response"
    assert v.layout, "retry should have populated layout"
    assert len(v.observations) >= 5, "retry should have populated observations"


def test_visual_run_keeps_partial_when_retry_also_shallow(sample_image):
    """When the retry STILL returns a shallow response, we keep the
    first one. The quality gate then flags it; we do not loop forever
    or burn unbounded tokens."""
    from src.agents.base import AgentDeps
    from src.fakes.fake_llm import FakeLLM
    from src.fakes.fake_retriever import FakeRetriever
    from src.fakes.fake_search import FakeSearch

    class _StuckVision:
        def __init__(self) -> None:
            self.calls = 0

        def analyze(self, *, system, user, images, schema, model=None):
            self.calls += 1
            return VisualAnalysis(palette=["#0A2540", "#635BFF", "#FFFFFF"])

    vision = _StuckVision()
    deps = AgentDeps(
        llm=FakeLLM(), vision=vision, retriever=FakeRetriever(), search=FakeSearch()
    )
    state = GraphState(image_path=str(sample_image), image_paths=[str(sample_image)])
    out = visual_analysis.run(state, deps)
    assert vision.calls == 2, "exactly one retry, never more"
    assert not out["visual"].layout, "stuck-shallow keeps the empty narrative"
