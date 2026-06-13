"""WebSearch — fake works; real Tavily is gated by ``real_api``."""
from __future__ import annotations

import pytest

from src.contracts import WebSearch
from src.fakes import FakeSearch
from src.schemas.outputs import SearchResult

pytestmark = pytest.mark.person_e


def test_fake_search_protocol_compliance():
    s: WebSearch = FakeSearch()
    hits = s.search("anything", k=3)
    assert all(isinstance(h, SearchResult) for h in hits)


@pytest.mark.real_api
def test_tavily_search_returns_results():
    pytest.importorskip("tavily")
    from src.tools.web_search import TavilySearch

    s = TavilySearch()
    hits = s.search("fintech dashboard 2026", k=3)
    assert hits and all(h.url.startswith("http") for h in hits)
