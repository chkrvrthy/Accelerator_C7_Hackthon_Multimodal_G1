"""Protocol classes — the seams between people.

OWNER: Person A (frozen after Hour 1; any change needs a 2-line PR rationale)
SPRINT CONCEPTS: this file is a *Code Quality* artifact more than a sprint
    artifact. It is the architectural seam that makes "5 people in parallel"
    actually work.
CONSUMES: nothing — Protocols are the lightest possible imports.
PROVIDES: LLMClient, VisionLLM, Retriever, WebSearch.

LOGIC OUTLINE
-------------
1. Define a ``Protocol`` for every external dependency an agent has.
2. Mark each one ``@runtime_checkable`` so isinstance() works in tests.
3. The real classes live in ``src/llm/`` and ``src/rag/`` and ``src/tools/``.
4. The fake classes live in ``src/fakes/``. Both satisfy these protocols.
5. Agents type-hint against the Protocol; never against the concrete class.

TEACHING NOTES (mentor's voice)
-------------------------------
This is the most important file in the whole repo and almost no code lives in
it. That is the point.

A *Protocol* in Python is the structural-typing flavour of an interface — any
class with the right methods satisfies it, no inheritance required. We use
that property to draw a hard line:

    AGENTS  --(consume)-->  PROTOCOL  <--(implement)--  REAL or FAKE

Person C's visual_analysis agent never imports ``OpenRouterVision``; it imports
``VisionLLM`` from this file. At runtime, Person A swaps in the real class or
the fake class via the ``AgentDeps`` container. The agent does not change.

This is what unlocks two things judges score on:

  * **Code Quality (10)** — clear seams, no god objects, dependency injection.
  * **Difficulty (10)** — five people working at once on the same repo without
    stepping on each other's code.

HINTS
-----
- Do not import torch / openai / lancedb here. Protocols must stay cheap.
- If you add a new Protocol, write a fake on the SAME PR. Untestable seams
  rot fast.
- The ``model: str | None = None`` argument is the cost-tier hint — leave it
  alone in agent code; ``cost.select_model`` decides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from src.schemas.outputs import RetrievedRef, SearchResult


@runtime_checkable
class LLMClient(Protocol):
    """Text-only structured completion.

    Used by: market_research, synthesizer.
    Implemented by: ``OpenRouterClient`` (real), ``HFLocalClient`` (stub),
    ``FakeLLM`` (fake).
    """

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Run a chat completion that MUST validate against ``schema``.

        Implementations should:
            1. Hash the inputs through ``cost.prompt_hash`` and consult the
               response cache before calling out (see ``cost.cached``).
            2. Pass ``response_format={"type":"json_schema", "json_schema":
               {...}}`` derived from ``schema.model_json_schema()``.
            3. Validate the parsed JSON via ``schema.model_validate(...)``
               and raise ``ValueError`` on shape drift.
        """
        ...


@runtime_checkable
class VisionLLM(Protocol):
    """Multimodal structured completion (image + text → typed output).

    Used by: visual_analysis, ux_critique, accessibility, brand_consistency.
    Implemented by: ``OpenRouterVision`` (real), ``FakeVisionLLM`` (fake).
    """

    def analyze(
        self,
        *,
        system: str,
        user: str,
        images: list[Path | str],
        schema: type[BaseModel],
        model: str | None = None,
    ) -> BaseModel:
        """Run a vision completion that MUST validate against ``schema``.

        ``images`` may be local file paths or ``data:image/png;base64,...``
        URIs. Implementations resize down to a sane max-side before encoding
        to keep token cost predictable (see ``tools.image_utils``).
        """
        ...


@runtime_checkable
class Retriever(Protocol):
    """k-NN retrieval over the design corpus.

    Used by: brand_consistency agent, UI Tab 3 (browse refs), MCP server.
    Implemented by: ``LanceRetriever`` (real), ``FakeRetriever`` (fake).
    """

    def retrieve_by_image(
        self,
        image_path: Path | str,
        k: int = 5,
    ) -> list[RetrievedRef]:
        """Return the top-k references most similar to the candidate image."""
        ...

    def retrieve_by_text(
        self,
        text: str,
        k: int = 5,
    ) -> list[RetrievedRef]:
        """Return the top-k references most similar to the text query.

        We can do this because CLIP embeds text and images into the same
        vector space (Sprint 3 concept).
        """
        ...


@runtime_checkable
class WebSearch(Protocol):
    """Web search wrapper used by the Market Research agent.

    Implemented by: ``TavilySearch`` (real), ``DuckDuckGoSearch`` (free
    fallback), ``FakeSearch`` (fake).
    """

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Return the top-k web hits for ``query``."""
        ...


__all__ = ["LLMClient", "Retriever", "VisionLLM", "WebSearch"]
