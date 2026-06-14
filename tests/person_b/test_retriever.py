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


class _Embedder:
    dim = 2

    def embed_image(self, image_path):
        return [1.0, 0.0]

    def embed_text(self, text):
        return [0.0, 1.0]


def test_lance_retriever_filters_and_maps_rows(monkeypatch):
    from src.rag import vector_store
    from src.rag.retriever import LanceRetriever

    monkeypatch.setattr(vector_store, "open_db", lambda: object())
    monkeypatch.setattr(vector_store, "get_or_create_table", lambda db, dim: "table")
    monkeypatch.setattr(
        vector_store,
        "query_by_vector",
        lambda table, vec, k: [
            {
                "id": "close",
                "_distance": 0.1,
                "image_path": "reference/close.png",
                "source": "demo",
                "tags": ["fintech"],
                "description": "near match",
            },
            {
                "id": "far",
                "_distance": 0.9,
                "image_path": "reference/far.png",
                "source": "demo",
                "tags": [],
                "description": "",
            },
        ],
    )

    refs = LanceRetriever(embedder=_Embedder()).retrieve_by_text("dashboard", k=2)
    assert [r.id for r in refs] == ["close"]
    assert refs[0].score == pytest.approx(0.9)
    assert refs[0].metadata["tags"] == ["fintech"]
