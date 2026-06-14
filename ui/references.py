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
            # MULTI-FRAME ATTRIBUTION: when the run uploaded multiple
            # frames, label the gallery item with which screens
            # surfaced it so the team can see "Stripe pricing matched
            # our Pricing AND Checkout — drift is broader than one
            # page". For single-frame runs the field is empty and the
            # label stays compact.
            base_label = f"{ref.id} · {ref.score:.2f}"
            if ref.matched_frames:
                base_label += f" · matched {', '.join(ref.matched_frames)}"
            gallery_items.append((resolved, base_label))

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

    # When the gallery is empty we want a *helpful* explanation rather
    # than a generic "no references". Most users hit this because they
    # haven't run ``make ingest`` yet — surface that one-liner instead
    # of a vague hint. We probe the corpus state lazily so the import
    # cost only lands on the empty path.
    if gallery_items:
        gallery_msg = (
            f"{len(gallery_items)} brand reference(s) the agent looked at this run. "
            "Click any thumbnail to open it; the small label shows the similarity "
            "score and (in multi-frame runs) which screen surfaced the match."
        )
    else:
        try:
            vector_rows = _vector_row_count()
            local_files = _local_reference_file_count()
        except Exception:
            vector_rows, local_files = 0, 0
        if vector_rows == 0:
            gallery_msg = (
                "Empty brand-RAG corpus. Drop a few reference images into "
                "data/reference/ and run `make ingest` (Linux/macOS) or "
                "`python -m scripts.ingest_references --source ./data/reference` "
                "(Windows). Until then the brand agent has nothing to compare "
                "against and the gallery above stays empty. Use the search "
                "below for ad-hoc lookups against the local index + the live web."
            )
        elif local_files == 0:
            gallery_msg = (
                f"Vector index has {vector_rows} row(s) but the on-disk "
                "data/reference/ folder is empty — the index points at images "
                "that have moved. Re-run `make ingest` after restoring the files."
            )
        else:
            gallery_msg = (
                f"Brand agent looked at the corpus ({vector_rows} indexed rows, "
                f"{local_files} on-disk files) but nothing close enough to your "
                "screens turned up — likely an off-domain run (e.g. you uploaded "
                "a payment screen but indexed dashboards). Use the search below "
                "to widen the lookup."
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
    elif vector_rows == 0:
        status = (
            "No local CLIP index yet — searching the live web below. To enable "
            "image-similarity matches, drop reference images into data/reference/ "
            "and run `make ingest`."
        )
    else:
        status = (
            f"No on-screen match in the {vector_rows}-row local index for this "
            "query — try a broader keyword, or see the live-web results below."
        )

    # Live web. Always run, even when the local gallery is empty, so the
    # search box is useful out-of-the-box (the bug Person E hit: typed
    # 'sites similar to stripe', saw nothing). _format_web_references is
    # already wrapped in try/except internally; we wrap once more so a
    # network blip never reaches the user as a Gradio error.
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
    # Shown whenever either the local gallery OR the web result block came
    # back empty — the search panel must never feel "broken". Earlier
    # this triggered only when BOTH were empty, which made fragile DDG
    # lookups silently lose the curated layer.
    editorial_block = ""
    has_web_results = "<li>" in web_refs and "(none yet" not in web_refs.lower()
    if not gallery_items or not has_web_results:
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
