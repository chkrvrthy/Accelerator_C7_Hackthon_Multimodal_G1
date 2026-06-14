"""WebSearch — fake works; real Tavily is gated by ``real_api``."""

from __future__ import annotations

import sys
import types

import pytest

from src.contracts import WebSearch
from src.fakes import FakeSearch
from src.schemas.outputs import SearchResult

pytestmark = pytest.mark.person_e


def test_fake_search_protocol_compliance():
    s: WebSearch = FakeSearch()
    hits = s.search("anything", k=3)
    assert all(isinstance(h, SearchResult) for h in hits)


def test_strip_trackers_keeps_useful_query_params():
    from src.tools.web_search import _strip_trackers

    url = "https://example.com/path?q=dashboard&utm_source=x&gclid=abc"
    assert _strip_trackers(url) == "https://example.com/path?q=dashboard"


def test_duckduckgo_search_normalizes_results(monkeypatch, tmp_settings):
    from src.tools import web_search
    from src.tools.web_search import DuckDuckGoSearch

    monkeypatch.setattr(web_search, "settings", tmp_settings)

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def text(self, query, max_results):
            return [
                {
                    "title": "A result",
                    "href": "https://example.com/a?utm_campaign=x&ref=keep",
                    "body": f"snippet for {query}",
                },
                {"title": "bad", "href": "javascript:void(0)", "body": "skip"},
            ]

    monkeypatch.setitem(sys.modules, "duckduckgo_search", types.SimpleNamespace(DDGS=FakeDDGS))

    hits = DuckDuckGoSearch().search("fintech dashboard", k=5)
    assert hits == [
        SearchResult(
            title="A result",
            url="https://example.com/a?ref=keep",
            snippet="snippet for fintech dashboard",
        )
    ]


@pytest.mark.real_api
def test_tavily_search_returns_results():
    pytest.importorskip("tavily")
    from src.tools.web_search import TavilySearch

    s = TavilySearch()
    hits = s.search("fintech dashboard 2026", k=3)
    assert hits and all(h.url.startswith("http") for h in hits)
