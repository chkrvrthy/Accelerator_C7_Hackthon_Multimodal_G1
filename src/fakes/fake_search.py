"""Deterministic WebSearch double.

OWNER: Person A
Used by: Person E's market_research agent in tests and per-slice runs.
"""

from __future__ import annotations

from typing import ClassVar

from src.schemas.outputs import SearchResult


class FakeSearch:
    """Three canned web hits, deterministic across runs."""

    _hits: ClassVar[list[SearchResult]] = [
        SearchResult(
            title="Top fintech UI trends 2026",
            url="https://example.com/fintech-trends-2026",
            snippet="Card stacking, dark-mode-by-default and progressive disclosure.",
        ),
        SearchResult(
            title="Designing for Indian retail banking customers",
            url="https://example.com/india-banking-ux",
            snippet="Vernacular language toggles, low-bandwidth thumbnails, UPI-first flows.",
        ),
        SearchResult(
            title="Jupiter and Fi Money product teardown",
            url="https://example.com/jupiter-fi-teardown",
            snippet="Comparative analysis of two Indian neobank dashboards.",
        ),
    ]

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("FakeSearch: empty query.")
        return self._hits[:k]
