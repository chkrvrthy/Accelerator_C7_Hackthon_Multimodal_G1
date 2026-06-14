"""Protocol runtime checks — every fake satisfies its Protocol.

These tests are the wall between "Protocol drift" and "agent crashes in
demo". If someone adds a method to ``Retriever`` without updating the
fake, this file fails immediately.
"""

from __future__ import annotations

from src.contracts import LLMClient, Retriever, VisionLLM, WebSearch
from src.fakes import FakeLLM, FakeRetriever, FakeSearch, FakeVisionLLM


def test_fake_llm_satisfies_llm_client():
    assert isinstance(FakeLLM(), LLMClient)


def test_fake_vision_satisfies_vision_llm():
    assert isinstance(FakeVisionLLM(), VisionLLM)


def test_fake_retriever_satisfies_retriever():
    assert isinstance(FakeRetriever(), Retriever)


def test_fake_search_satisfies_websearch():
    assert isinstance(FakeSearch(), WebSearch)


def test_protocols_have_runtime_checkable():
    """Sanity: removing @runtime_checkable would break per-slice tests silently."""
    for proto in (LLMClient, VisionLLM, Retriever, WebSearch):
        assert getattr(
            proto, "_is_runtime_protocol", False
        ), f"{proto.__name__} must be runtime_checkable."
