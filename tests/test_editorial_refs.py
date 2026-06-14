"""Tests for the editorial fallback reference list."""

from __future__ import annotations

from src.rag.editorial_refs import render_as_html, search_editorial


def test_search_returns_starter_set_for_empty_query() -> None:
    refs = search_editorial("", limit=4)
    assert len(refs) == 4


def test_keyword_match_prioritizes_correct_refs() -> None:
    refs = search_editorial("wcag contrast for accessibility", limit=3)
    titles = [r.title for r in refs]
    assert any("WCAG" in t for t in titles), titles


def test_unknown_query_still_returns_something() -> None:
    refs = search_editorial("zzz_nothing_matches_zzz", limit=3)
    assert refs, "fallback must NEVER be empty"


def test_render_html_contains_links() -> None:
    refs = search_editorial("nielsen heuristic", limit=2)
    html = render_as_html(refs)
    assert "<a " in html and 'target="_blank"' in html
    assert all(f">{r.title}<" in html for r in refs)


def test_render_empty_returns_empty_string() -> None:
    assert render_as_html([]) == ""
