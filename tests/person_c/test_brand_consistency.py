"""Brand Consistency agent — happy path + zero-corpus fallback."""
from __future__ import annotations

import pytest

from src.agents import brand_consistency
from src.schemas.outputs import BrandConsistency, GraphState

pytestmark = pytest.mark.person_c


def test_brand_run_returns_consistency(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = brand_consistency.run(state, fake_deps)
    rep = out["brand"]
    assert isinstance(rep, BrandConsistency)
    assert rep.consistency_score >= 0
    assert len(rep.comparable_refs) >= 1


def test_brand_run_no_refs_fallback(fake_deps, sample_image, monkeypatch):
    """When the retriever returns [], the agent must still produce a valid output."""
    monkeypatch.setattr(fake_deps.retriever, "retrieve_by_image", lambda *a, **k: [])
    state = GraphState(image_path=str(sample_image))
    out = brand_consistency.run(state, fake_deps)
    rep = out["brand"]
    assert isinstance(rep, BrandConsistency)
    assert rep.comparable_refs == []
