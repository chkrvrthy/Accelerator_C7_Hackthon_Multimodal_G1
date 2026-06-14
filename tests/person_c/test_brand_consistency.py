"""Brand Consistency agent — happy path + zero-corpus fallback."""

from __future__ import annotations

import pytest

from src.agents import brand_consistency
from src.schemas.outputs import BrandConsistency, GraphState
from src.utils.prompts import brand_consistency_user

pytestmark = pytest.mark.person_c


def test_brand_run_returns_consistency(fake_deps, sample_image):
    state = GraphState(image_path=str(sample_image))
    out = brand_consistency.run(state, fake_deps)
    rep = out["brand"]
    assert isinstance(rep, BrandConsistency)
    assert rep.consistency_score >= 0
    assert len(rep.comparable_refs) >= 1


def test_brand_run_pins_ref_ids(fake_deps, sample_image):
    """comparable_refs must come from the retriever, not the LLM's imagination.

    The FakeLLM returns BrandConsistency with comparable_refs=[]; the agent
    must backfill it with the actual retrieved refs so ids can't be fabricated.
    """
    refs = fake_deps.retriever.retrieve_by_image(sample_image)
    state = GraphState(image_path=str(sample_image))
    out = brand_consistency.run(state, fake_deps)
    got_ids = {r.id for r in out["brand"].comparable_refs}
    assert got_ids == {r.id for r in refs}
    # and the retrieved refs are written back to state for the synthesizer
    assert [r.id for r in out["refs"]] == [r.id for r in refs]


def test_brand_run_no_refs_fallback(fake_deps, sample_image, monkeypatch):
    """When the retriever returns [], the agent must still produce a valid output."""
    monkeypatch.setattr(fake_deps.retriever, "retrieve_by_image", lambda *a, **k: [])
    state = GraphState(image_path=str(sample_image))
    out = brand_consistency.run(state, fake_deps)
    rep = out["brand"]
    assert isinstance(rep, BrandConsistency)
    assert rep.comparable_refs == []


def test_brand_user_prompt_lists_ref_ids_and_scores(fake_deps, sample_image):
    """The user message surfaces each ref's id + similarity score to the LLM."""
    refs = fake_deps.retriever.retrieve_by_image(sample_image)
    user = brand_consistency_user(refs)
    for r in refs:
        assert r.id in user
        assert f"{r.score:.2f}" in user


def test_brand_user_prompt_empty_refs():
    user = brand_consistency_user([])
    assert "none available" in user
