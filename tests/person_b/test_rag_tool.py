"""LangChain Tool wrapper returns valid JSON list of RetrievedRef dicts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.tools.rag_tool import RAGSearchInput, RAGSearchTool

pytestmark = pytest.mark.person_b


def test_rag_tool_text_query_returns_json(fake_retriever):
    tool = RAGSearchTool(retriever=fake_retriever)
    result = tool._run(query="dashboard", k=2, by="text")
    parsed = json.loads(result)
    assert isinstance(parsed, list) and len(parsed) == 2
    assert all("id" in r and "score" in r for r in parsed)


def test_rag_tool_image_query_returns_json(fake_retriever, sample_image):
    tool = RAGSearchTool(retriever=fake_retriever)
    result = tool._run(query=str(sample_image), k=1, by="image")
    parsed = json.loads(result)
    assert len(parsed) == 1


def test_rag_tool_validates_by_argument(fake_retriever):
    tool = RAGSearchTool(retriever=fake_retriever)
    with pytest.raises(ValueError):
        tool._run(query="x", k=1, by="audio")


def test_rag_tool_input_schema_bounds():
    with pytest.raises(ValidationError):
        RAGSearchInput(query="q", k=999)  # k upper bound is 50


def test_rag_tool_to_langchain_when_installed(fake_retriever):
    pytest.importorskip("langchain_core")
    tool = RAGSearchTool(retriever=fake_retriever).to_langchain()
    assert tool.name == "rag_search_designs"
