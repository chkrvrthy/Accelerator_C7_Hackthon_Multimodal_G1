"""Market Research agent — uses FakeSearch + FakeLLM by default."""

from __future__ import annotations

import pytest

from src.agents import market_research
from src.schemas.outputs import GraphState, MarketResearch, VisualAnalysis

pytestmark = pytest.mark.person_e


def test_market_run_returns_market_research(fake_deps, sample_image):
    state = GraphState(
        image_path=str(sample_image),
        instructions="audience: Indian retail",
        visual=VisualAnalysis(layout="2-col dashboard", hierarchy="primary metrics first"),
    )
    out = market_research.run(state, fake_deps)
    assert "market" in out and isinstance(out["market"], MarketResearch)
    rep = out["market"]
    assert rep.competitors and len(rep.competitors) >= 1
    assert rep.trends


def test_market_run_falls_back_to_vision_when_no_visual(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))  # no .visual prefilled
    out = market_research.run(state, fake_deps)
    assert isinstance(out["market"], MarketResearch)
