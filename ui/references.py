"""References-tab handlers: from-report payload + ad-hoc search.

OWNER: Person E
USED BY: ui/app.py.

Public surface:
  - ``_references_for_report(report)``: build the gallery + summary HTML
    from the LATEST analysis (brand-agent retrievals + market-agent URLs).
  - ``_reference_query_from_ui(query)``: search local image RAG (LanceDB)
    + live web (Tavily / DuckDuckGo) + curated editorial fallback.
  - ``_gallery_query(deps, query, k)``: low-level retriever wrapper used
    by the search handler above.

Graceful errors: every external call is wrapped — a failed retriever
or a flaky web-search provider degrades to "fewer results" rather than
a Gradio error popup.
"""

from __future__ import annotations

import html
from typing import Any

from src.agents.base import AgentDeps, build_default_deps
from src.schemas.outputs import DesignReport
from src.utils.logger import get_logger
from ui.state import (
    _format_web_references,
    _fresh_settings,
    _local_reference_file_count,
    _resolve_reference_path,
    _vector_row_count,
)

log = get_logger(__name__)


def _gallery_query(deps: AgentDeps, query: str, k: int = 12) -> list[tuple[str, str]]:
    """Return Gradio gallery tuples from the configured retriever."""
    refs = deps.retriever.retrieve_by_text(query, k=k)
    return [(_resolve_reference_path(r.image_path), f"{r.id} - {r.score:.2f}") for r in refs]


def _references_for_report(
    report: DesignReport | dict[str, Any] | None,
) -> tuple[list[tuple[str, str]], str]:
    """Build the References-tab payload from the LATEST analysis.

    Replaces the old "search-only" References tab with a contextual one:
    when the user runs an analysis, this surfaces exactly the references
    the agents looked at — local image RAG hits the brand agent retrieved
    plus the URLs the market agent cited. Search is still available below
    as a supplementary tool.
    """
    if report is None:
        return (
            [],
            """
<div class="reference-card">
  <h3>References used in this run</h3>
  <p>Run an analysis from the <b>Analyze</b> tab. The references the
  brand and market agents consulted will appear here automatically.</p>
</div>
""",
        )

    rep: DesignReport = DesignReport.model_validate(report) if isinstance(report, dict) else report
    report = rep

    gallery_items: list[tuple[str, str]] = []
    if report.brand and report.brand.comparable_refs:
        for ref in report.brand.comparable_refs:
            try:
                resolved = _resolve_reference_path(ref.image_path)
            except Exception:
                resolved = ref.image_path
            label = f"{ref.id} · {ref.score:.2f}"
            gallery_items.append((resolved, label))

    market_lines: list[str] = []
    if report.market and report.market.competitors:
        for c in report.market.competitors:
            market_lines.append(
                f"<li><b>{html.escape(c.name)}</b> "
                f'— <a href="{html.escape(c.url)}" target="_blank" rel="noopener">{html.escape(c.url)}</a> '
                f'<br><span class="muted">{html.escape(c.why_relevant)}</span></li>'
            )
    if report.market and report.market.citations:
        for url in report.market.citations[:5]:
            market_lines.append(
                f'<li><a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(url)}</a></li>'
            )

    market_block = ""
    if market_lines:
        market_block = (
            '<div class="reference-card" style="margin-top:14px">'
            "<h3>Market references cited in this run</h3>"
            f'<ul>{"".join(market_lines)}</ul>'
            "</div>"
        )

    gallery_msg = (
        f"{len(gallery_items)} brand reference(s) retrieved by the brand agent."
        if gallery_items
        else "Brand agent retrieved no comparable references for this screen "
        "(empty index or off-domain). Search below to add context."
    )
    summary_html = (
        '<div class="reference-card">'
        "<h3>References used in this run</h3>"
        f"<p>{html.escape(gallery_msg)}</p>"
        "</div>"
        f"{market_block}"
    )
    return gallery_items, summary_html


def _reference_query_from_ui(query: str) -> tuple[list[tuple[str, str]], str]:
    """Search local image refs (LanceDB) and live web refs (Tavily/DuckDuckGo).

    GRACEFUL ERRORS: every external call below is wrapped — a failed
    retriever or a flaky web-search provider degrades to "fewer results"
    rather than a Gradio error popup. The user sees what we can show and
    a calm "some sources unavailable" hint when relevant.
    """
    _fresh_settings()
    if not query.strip():
        return (
            [],
            """
<div class="reference-card">
  <h3>Similar references</h3>
  <p>Type a pattern or product category.</p>
</div>
""",
        )

    gallery_items: list[tuple[str, str]] = []
    local_files = _local_reference_file_count()
    vector_rows = _vector_row_count()
    retriever_failed = False

    if vector_rows > 0:
        try:
            deps = build_default_deps(use_real=True)
            gallery_items = _gallery_query(deps, query, k=12)
        except Exception as e:
            retriever_failed = True
            log.warning("references: retriever failed: %s", e)

    if retriever_failed:
        status = (
            "Image-similarity search hit a snag, so we are showing the other "
            "sources only. Server logs have details."
        )
    elif gallery_items:
        status = f"{vector_rows} indexed references from {local_files} local files."
    else:
        status = (
            "No indexed matches yet. Add images to the reference dir and run "
            "make ingest."
        )

    try:
        web_refs = _format_web_references(query, use_real=True)
    except Exception as e:
        log.warning("references: web search failed: %s", e)
        web_refs = (
            '<div class="reference-card" style="margin-top:12px">'
            "<h3>Web references</h3>"
            "<p>Web search is unavailable right now. Showing curated "
            "fallbacks below.</p></div>"
        )

    # FALLBACK: editorial references (hand-curated, no network, no LLM).
    # Shown ONLY when both gallery_items and web_refs are empty so we
    # never overwhelm a fully-functional run with the static list.
    editorial_block = ""
    has_web_results = "<li>" in web_refs and "(none yet" not in web_refs.lower()
    if not gallery_items and not has_web_results:
        from src.rag.editorial_refs import render_as_html, search_editorial

        editorial_block = render_as_html(search_editorial(query, limit=6))

    return (
        gallery_items,
        f"""
<div class="reference-card">
  <h3>Similar references</h3>
  <p>{html.escape(status)}</p>
</div>
{web_refs}
{editorial_block}
""",
    )
