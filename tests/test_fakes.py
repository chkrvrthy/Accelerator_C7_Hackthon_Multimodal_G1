"""Fakes round-trip every schema (cross-cutting, run by everyone).

This file proves the fakes are useful — they emit data that validates against
the real schemas. If you add a new agent, add a canned response to
``src.fakes.fake_llm._canned`` AND a test here.
"""

from __future__ import annotations

import pytest

from src.fakes import FakeLLM, FakeRetriever, FakeSearch, FakeVisionLLM, ensure_sample_design
from src.schemas.outputs import (
    AccessibilityReport,
    BrandConsistency,
    DesignReport,
    MarketResearch,
    UXCritique,
    VisualAnalysis,
)


@pytest.mark.parametrize(
    "schema",
    [
        VisualAnalysis,
        UXCritique,
        AccessibilityReport,
        MarketResearch,
        BrandConsistency,
        DesignReport,
    ],
)
def test_fake_llm_returns_schema_instance(schema):
    out = FakeLLM().complete(system="", user="", schema=schema)
    assert isinstance(out, schema)


def test_fake_vision_validates_image_exists():
    p = ensure_sample_design()
    out = FakeVisionLLM().analyze(system="", user="", images=[p], schema=VisualAnalysis)
    assert isinstance(out, VisualAnalysis) and out.palette


def test_fake_vision_raises_on_missing_image():
    with pytest.raises(FileNotFoundError):
        FakeVisionLLM().analyze(
            system="", user="", images=["/no/such/path.png"], schema=VisualAnalysis
        )


def test_fake_retriever_descending_scores():
    refs = FakeRetriever().retrieve_by_text("dashboard")
    scores = [r.score for r in refs]
    assert scores == sorted(scores, reverse=True)


def test_fake_retriever_image_query_requires_existing_path():
    with pytest.raises(FileNotFoundError):
        FakeRetriever().retrieve_by_image("/no/such/path.png")


def test_fake_search_returns_three_canned_hits():
    hits = FakeSearch().search("anything")
    assert len(hits) == 3
    assert all(h.url.startswith("https://") for h in hits)


def test_fake_search_rejects_empty_query():
    with pytest.raises(ValueError):
        FakeSearch().search("   ")


def test_unknown_schema_raises():
    """Adding a schema without a canned response should fail loudly."""
    from pydantic import BaseModel

    class _Surprise(BaseModel):
        x: int = 0

    with pytest.raises(ValueError):
        FakeLLM().complete(system="", user="", schema=_Surprise)
