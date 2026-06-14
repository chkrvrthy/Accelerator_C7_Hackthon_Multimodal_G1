"""LangChain BaseTool wrapper around the Retriever protocol.

OWNER: Person B (thin pass-through ~25 lines)
SPRINT CONCEPTS:
    - Sprint 5: LangChain tools (concept claim).
CONSUMES: ``langchain-core``, ``Retriever``.
PROVIDES: ``RAGSearchInput``, ``RAGSearchTool``.

WHY THIN
--------
The brand agent calls the retriever directly (faster, simpler). This file
exists so the project visibly demonstrates "we know how to define a
LangChain tool". If we later expose retrieval to an LLM-as-router, this
file is what gets passed to ``bind_tools(...)``.

DEFINITION OF DONE
------------------
[ ] tests/person_b/test_rag_tool.py passes (text + image queries).
[ ] ``_run`` returns a JSON STRING (not a list of dicts) — LangChain tools
    must return strings to the model.
[ ] ``args_schema`` validates ``k`` is between 1 and 50.
[ ] ``to_langchain()`` returns a real ``StructuredTool`` once
    ``langchain-core`` is installed.

DO NOT
------
- Do not expand this file beyond ~30 lines. The plan calls it a "thin
  pass-through" for a reason — judges check that LangChain tools exist,
  not that you wrote a fancy one.
- Do not couple to a specific Retriever class — accept the Protocol so the
  fake works in tests.
- Do not catch exceptions silently. If the retriever raises, the LLM should
  see the error string.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.contracts import Retriever


class RAGSearchInput(BaseModel):
    """Input schema for ``RAGSearchTool``."""

    query: str = Field(..., description="Image path or text query.")
    k: int = Field(default=5, ge=1, le=50)
    by: Literal["text", "image"] = "text"


class RAGSearchTool:
    """Minimal BaseTool-shaped wrapper around the ``Retriever`` protocol.

    HINT: we type as ``Any`` and don't actually inherit from
    ``langchain_core.tools.BaseTool`` until langchain-core is installed —
    keeps the rest of the repo importable for slices that don't pull it.
    """

    name: str = "rag_search_designs"
    description: str = (
        "Find similar reference designs in the corpus. Pass `by='image'` with "
        "a local image path or `by='text'` with a natural-language query."
    )
    args_schema: type[BaseModel] = RAGSearchInput

    def __init__(self, retriever: Retriever) -> None:
        # NOTE: any object satisfying the Retriever Protocol works — including
        # FakeRetriever in tests, LanceRetriever in production.
        self.retriever = retriever

    def _run(self, query: str, k: int = 5, by: str = "text") -> str:
        """Return a JSON-serialized list of ``RetrievedRef`` dicts.

        LangChain tools must return *strings* (so the LLM can read them),
        which is why we json.dumps here even though we have typed objects.
        """
        if by not in {"text", "image"}:
            raise ValueError(f"by must be 'text' or 'image', got {by!r}")
        # LOGIC: dispatch on ``by`` so the same tool covers both query modes.
        # That's enough for the LLM to choose; no need for two tools.
        refs = (
            self.retriever.retrieve_by_text(query, k)
            if by == "text"
            else self.retriever.retrieve_by_image(query, k)
        )
        return json.dumps([r.model_dump() for r in refs])

    def to_langchain(self) -> Any:  # pragma: no cover
        """Wrap as a real ``langchain_core.tools.StructuredTool`` if installed."""
        # HINT: three lines:
        #   from langchain_core.tools import StructuredTool
        #   return StructuredTool.from_function(
        #       self._run, name=self.name, description=self.description,
        #       args_schema=self.args_schema,
        #   )
        # TODO(person-b, optional): wire StructuredTool when needed.
        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            self._run,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
        )
