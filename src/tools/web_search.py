"""Web search: Tavily preferred, DuckDuckGo free fallback.

OWNER: Person E
SPRINT CONCEPTS:
    - Sprint 5: tool augmentation (Market Research agent's tool).
CONSUMES: ``tavily-python``, ``duckduckgo-search``.
PROVIDES: ``TavilySearch``, ``DuckDuckGoSearch``, ``get_default_search``.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.config import settings
from src.contracts import WebSearch
from src.schemas.outputs import SearchResult
from src.utils.logger import get_logger

log = get_logger(__name__)

_TRACKERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}
_CACHE_TTL_SECONDS = 24 * 60 * 60


def _strip_trackers(url: str) -> str:
    """Remove common tracking params while preserving useful query params."""
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _TRACKERS]
    return urlunparse(parsed._replace(query=urlencode(query)))


def _cache_path(provider: str, query: str, k: int) -> Path:
    key = hashlib.sha256(f"{provider}::{query.strip()}::{k}".encode()).hexdigest()
    return settings.cache_dir / "search" / f"{key}.json"


def _read_cache(provider: str, query: str, k: int) -> list[SearchResult] | None:
    if settings.cache_disabled:
        return None
    path = _cache_path(provider, query, k)
    if not path.exists() or time.time() - path.stat().st_mtime > _CACHE_TTL_SECONDS:
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return [SearchResult.model_validate(r) for r in rows]
    except Exception as e:
        log.warning("web_search: ignoring bad cache file %s: %s", path, e)
        return None


def _write_cache(provider: str, query: str, k: int, results: list[SearchResult]) -> None:
    if settings.cache_disabled:
        return
    path = _cache_path(provider, query, k)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.model_dump() for r in results], indent=2),
        encoding="utf-8",
    )


def _clean_result(title: Any, url: Any, snippet: Any) -> SearchResult | None:
    clean_url = _strip_trackers(str(url or "").strip())
    clean_title = str(title or "").strip()
    clean_snippet = str(snippet or "").strip()
    if not clean_url.startswith(("http://", "https://")):
        return None
    if not clean_title and not clean_snippet:
        return None
    return SearchResult(title=clean_title or clean_url, url=clean_url, snippet=clean_snippet)


class TavilySearch:
    """Real ``WebSearch`` via Tavily."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.tavily_api_key
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError(
                "TAVILY_API_KEY is not set. Either export it, set it in .env, "
                "or use DuckDuckGoSearch via get_default_search()."
            )
        try:
            from tavily import TavilyClient  # type: ignore[import-not-found]
        except ImportError as e:
            raise RuntimeError(
                "tavily-python is not installed. Run: pip install -r "
                "requirements/person-e-ui.txt"
            ) from e
        self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Return top-k web hits from Tavily."""
        query = query.strip()
        if not query or k <= 0:
            return []
        k = min(k, 20)

        cached = _read_cache("tavily", query, k)
        if cached is not None:
            return cached

        try:
            client = self._ensure_client()
            resp = client.search(query=query, max_results=k, include_answer=False)
            rows = resp.get("results", []) if isinstance(resp, dict) else []
            results = [
                r
                for h in rows
                if (
                    r := _clean_result(
                        h.get("title"),
                        h.get("url"),
                        h.get("content") or h.get("snippet"),
                    )
                )
            ][:k]
        except Exception as e:
            log.warning("tavily search failed, falling back to DuckDuckGo: %s", e)
            return DuckDuckGoSearch().search(query, k=k)

        _write_cache("tavily", query, k, results)
        return results


class DuckDuckGoSearch:
    """Free ``WebSearch`` fallback via duckduckgo_search."""

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Return top-k web hits from DuckDuckGo."""
        query = query.strip()
        if not query or k <= 0:
            return []
        k = min(k, 20)

        cached = _read_cache("duckduckgo", query, k)
        if cached is not None:
            return cached

        try:
            try:
                from duckduckgo_search import DDGS  # type: ignore[import-not-found]
            except ImportError:
                from ddgs import DDGS  # type: ignore[import-not-found]

            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=k) or [])
        except Exception as e:
            log.warning("duckduckgo search failed: %s", e)
            return []

        results = [
            r
            for h in hits
            if (
                r := _clean_result(
                    h.get("title"),
                    h.get("href") or h.get("url"),
                    h.get("body") or h.get("content") or h.get("snippet"),
                )
            )
        ][:k]
        _write_cache("duckduckgo", query, k, results)
        return results


def get_default_search() -> WebSearch:
    """Tavily if a key is set, else DuckDuckGo."""
    if settings.tavily_api_key:
        return TavilySearch()
    return DuckDuckGoSearch()
