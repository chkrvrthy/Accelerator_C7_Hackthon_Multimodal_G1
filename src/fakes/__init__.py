"""Fakes — deterministic stand-ins for every Protocol in ``src/contracts.py``.

OWNER: Person A (used by everyone)

Why this package exists
-----------------------
A "container per person" only works if Person C can run their visual_analysis
agent before Person A's OpenRouter client is wired and before Person B's
LanceDB is populated. The fakes here close that gap. Each one:

  * Implements one Protocol from ``src/contracts.py`` exactly.
  * Returns canned, schema-valid data on every call.
  * Has zero third-party imports beyond pydantic — no network, no GPU.
  * Is deterministic so tests can assert specific values.

Use them via ``AgentDeps`` (see ``src/agents/base.build_default_deps``):

    >>> deps = build_default_deps(use_real=False)   # fakes wired in
    >>> result = await visual_analysis.run(state, deps)

You almost never construct a fake by hand — pytest fixtures in
``tests/conftest.py`` do that for you.
"""

from .fake_llm import FakeLLM, FakeVisionLLM
from .fake_retriever import FakeRetriever
from .fake_search import FakeSearch
from .fixtures import SAMPLE_DESIGN, ensure_sample_design

__all__ = [
    "SAMPLE_DESIGN",
    "FakeLLM",
    "FakeRetriever",
    "FakeSearch",
    "FakeVisionLLM",
    "ensure_sample_design",
]
