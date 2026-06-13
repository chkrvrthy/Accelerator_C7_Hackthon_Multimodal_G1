"""Web search — Tavily preferred, DuckDuckGo free fallback.

OWNER: Person E
SPRINT CONCEPTS:
    - Sprint 5: tool augmentation (Market Research agent's tool).
CONSUMES: ``tavily-python``, ``duckduckgo-search``.
PROVIDES: ``TavilySearch``, ``DuckDuckGoSearch``, ``get_default_search``.

WHY YOU CARE
------------
The Market Research agent (Person E's, also yours) is the only consumer.
But this file also lights up the "tool-augmented agent" Sprint-5 concept
slot — without it, you don't have a real tool, you have a single LLM call.

LOGIC OUTLINE
-------------
1. ``TavilySearch`` calls Tavily's ``search`` API; returns clean snippets.
2. ``DuckDuckGoSearch`` is the free path; results are rawer and need more
   defensive prompting downstream.
3. ``get_default_search`` returns Tavily if a key is set, else DuckDuckGo.

DEFINITION OF DONE
------------------
[ ] tests/person_e/test_web_search.py passes (FakeSearch path).
[ ] With ``TAVILY_API_KEY`` set, the ``real_api`` test returns ≥ 3 hits with
    valid http(s) URLs.
[ ] DuckDuckGo path returns SearchResult objects (not raw dicts) and never
    raises on empty results — returns ``[]``.
[ ] Cache layer: a second identical query within 24 h reads from disk.

DO NOT
------
- Do not blast Tavily on every keystroke. Cache for 24 h to
  ``data/cache/search/<sha256(query)>.json``.
- Do not return the raw URL with tracking params. Strip ``utm_*``,
  ``fbclid``, ``gclid`` — judges notice tracker noise.
- Do not let DuckDuckGo's empty-list response raise. Return ``[]``.
- Do not write your own retry loop on top of Tavily's rate limit. Catch
  the SDK's RateLimitError and fall back to DuckDuckGoSearch instead.
"""
from __future__ import annotations

from typing import Any

from src.config import settings
from src.contracts import WebSearch  # noqa: F401  — declared for clarity
from src.schemas.outputs import SearchResult
from src.utils.logger import get_logger

log = get_logger(__name__)


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
        # HINT: lazy import keeps non-Person-E slices from needing this dep.
        # TODO(person-e): two lines:
        #   from tavily import TavilyClient
        #   self._client = TavilyClient(api_key=self.api_key)
        #   return self._client
        raise NotImplementedError("Person E: implement TavilySearch._ensure_client")

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Return top-k web hits from Tavily."""
        # HINT: the recipe is short:
        #   client = self._ensure_client()
        #   resp = client.search(query=query, max_results=k, include_answer=False)
        #   return [
        #       SearchResult(title=h["title"], url=_strip_trackers(h["url"]), snippet=h["content"])
        #       for h in resp["results"]
        #   ]
        #
        # HINT: cache wrapper (~10 lines, optional but worth it):
        #   key = hashlib.sha256(f"tavily::{query}::{k}".encode()).hexdigest()
        #   p = settings.cache_dir / "search" / f"{key}.json"
        #   if p.exists() and (time.time() - p.stat().st_mtime) < 86400:
        #       return [SearchResult.model_validate(r) for r in json.loads(p.read_text())]
        #   ... call API ...
        #   p.parent.mkdir(parents=True, exist_ok=True)
        #   p.write_text(json.dumps([r.model_dump() for r in results]))
        #   return results
        # TODO(person-e): implement search + (optional) caching.
        raise NotImplementedError("Person E: implement TavilySearch.search")


class DuckDuckGoSearch:
    """Free ``WebSearch`` fallback via duckduckgo_search.

    No key required. Snippets are rawer than Tavily's; the market agent's
    prompt has to be defensive about quality.
    """

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Return top-k web hits from DuckDuckGo."""
        # HINT: the recipe (~6 lines):
        #   from duckduckgo_search import DDGS
        #   with DDGS() as ddgs:
        #       hits = list(ddgs.text(query, max_results=k))
        #   return [
        #       SearchResult(title=h["title"], url=h["href"], snippet=h["body"])
        #       for h in hits
        #   ]
        #
        # NOTE: empty results return [] — don't raise. The market agent will
        # still produce a (less informed) MarketResearch.
        # TODO(person-e): implement.
        raise NotImplementedError("Person E: implement DuckDuckGoSearch.search")


def get_default_search() -> WebSearch:
    """Tavily if a key is set, else DuckDuckGo.

    Used by ``AgentDeps`` when ``USE_REAL=1``.
    """
    if settings.tavily_api_key:
        return TavilySearch()
    return DuckDuckGoSearch()


# Optional helper: strip tracker query params before returning URLs.
# TODO(person-e, optional):
#   from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
#   _TRACKERS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
#                "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid"}
#   def _strip_trackers(url: str) -> str:
#       u = urlparse(url)
#       q = [(k, v) for k, v in parse_qsl(u.query) if k.lower() not in _TRACKERS]
#       return urlunparse(u._replace(query=urlencode(q)))
