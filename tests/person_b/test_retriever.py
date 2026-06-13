"""Retriever protocol contract — uses FakeRetriever until LanceRetriever lands.

Person B replaces the body of LanceRetriever; these tests then run unchanged
against the real implementation.
"""
from __future__ import annotations

import pytest

from src.contracts import Retriever
from src.schemas.outputs import RetrievedRef

pytestmark = pytest.mark.person_b


def test_retriever_returns_descending_scores(fake_retriever, sample_image):
    refs = fake_retriever.retrieve_by_image(sample_image, k=3)
    assert all(isinstance(r, RetrievedRef) for r in refs)
    assert refs == sorted(refs, key=lambda r: r.score, reverse=True)


def test_retriever_text_query(fake_retriever):
    refs = fake_retriever.retrieve_by_text("modern fintech dashboard", k=2)
    assert len(refs) == 2 and refs[0].score >= refs[1].score


def test_retriever_protocol_runtime(fake_retriever):
    assert isinstance(fake_retriever, Retriever)
