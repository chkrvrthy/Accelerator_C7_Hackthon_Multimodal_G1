"""Synthesizer aggregates fake outputs into a valid DesignReport."""

from __future__ import annotations

import pytest

from src.agents import (
    accessibility,
    brand_consistency,
    market_research,
    synthesizer,
    ux_critique,
    visual_analysis,
)
from src.schemas.outputs import DesignReport, GraphState

pytestmark = pytest.mark.person_a


def test_synthesizer_aggregates_all_specialists(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    state = state.model_copy(update=visual_analysis.run(state, fake_deps))
    state = state.model_copy(update=ux_critique.run(state, fake_deps))
    state = state.model_copy(update=accessibility.run(state, fake_deps))
    state = state.model_copy(update=brand_consistency.run(state, fake_deps))
    state = state.model_copy(update=market_research.run(state, fake_deps))

    out = synthesizer.run(state, fake_deps)
    rep: DesignReport = out["report"]

    assert isinstance(rep, DesignReport)
    assert 0 <= rep.overall_score <= 100
    assert rep.top_strengths and len(rep.top_strengths) >= 1
    assert rep.top_recommendations and len(rep.top_recommendations) >= 1
    # All specialist fields threaded into the report:
    assert rep.visual is not None
    assert rep.ux is not None
    assert rep.accessibility is not None
    assert rep.brand is not None
    assert rep.market is not None
