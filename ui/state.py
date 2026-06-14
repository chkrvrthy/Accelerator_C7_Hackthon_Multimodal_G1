"""UI-side state + small render helpers.

OWNER: Person E
USED BY: ui/app.py, ui/handlers.py, ui/references.py, ui/render.py.

This module owns the small functions that:
  - Re-read settings from ``.env`` per run (``_fresh_settings``).
  - Render the global status banner + the Settings-tab cards.
  - Translate the retriever's portable image paths into local files.
  - Format web references and the cost / tools telemetry blocks.

These were originally inline in ``ui/app.py``; pulling them out keeps
that file under the project's 500 LOC limit. Behavior is unchanged.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any

import src.config as app_config
from src.config import Settings
from src.utils.logger import get_logger

log = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _status_message(title: str, body: str) -> str:
    return f"""
<div class="status-card">
  <h3>{html.escape(title)}</h3>
  <p>{html.escape(body)}</p>
</div>
"""


def _fresh_settings() -> Settings:
    """Re-read .env and point UI-adjacent modules at the fresh Settings."""
    global settings

    app_config.get_settings.cache_clear()
    settings = app_config.get_settings()
    app_config.settings = settings

    modules = (
        "src.agents.base",
        "src.tools.web_search",
        "src.llm.openrouter_client",
        "src.llm.multimodal",
        "src.rag.retriever",
        "src.rag.embedder",
    )
    for module_name in modules:
        module = sys.modules.get(module_name)
        if module is not None:
            module.settings = settings
    return settings


def _has_openrouter_key() -> bool:
    cfg = _fresh_settings()
    return bool(cfg.openrouter_api_key and "REPLACE_ME" not in cfg.openrouter_api_key)


def _default_real_mode() -> bool:
    cfg = _fresh_settings()
    return cfg.use_real or _has_openrouter_key()


def _resolve_reference_path(image_path: str) -> str:
    """Convert portable retriever paths into browser-readable local paths."""
    cfg = _fresh_settings()
    candidates = [
        Path(image_path),
        PROJECT_ROOT / image_path,
        cfg.reference_dir.parent / image_path,
        cfg.reference_dir / image_path,
    ]
    for p in candidates:
        if p.exists():
            return str(p.resolve())
    return image_path


def _vector_row_count() -> int:
    try:
        from src.rag.vector_store import get_or_create_table, open_db

        table = get_or_create_table(open_db(), dim=512)
        return int(table.count_rows())
    except Exception as e:
        log.warning("references: could not count vector rows: %s", e)
        return 0


def _local_reference_file_count() -> int:
    cfg = _fresh_settings()
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    if not cfg.reference_dir.exists():
        return 0
    return sum(1 for p in cfg.reference_dir.rglob("*") if p.suffix.lower() in exts)


def _cache_file_count() -> int:
    """Number of disk-cached LLM responses. Useful for the Settings tab."""
    cfg = _fresh_settings()
    if not cfg.cache_dir.exists():
        return 0
    return sum(1 for _ in cfg.cache_dir.glob("*.json"))


def _tool_registry_html() -> str:
    """Render the agent-tool registry as a Settings-tab card.

    Reads from ``src.agents.tools._REGISTRY`` (via the public
    ``list_tools`` helper). Static — does not need a refresh button.
    """
    from src.agents.tools import list_tools

    tools = list_tools()
    if not tools:
        return (
            '<div class="settings-card" style="margin-top:14px">'
            "<h3>Agent tools</h3>"
            "<p><i>No tools registered.</i></p></div>"
        )

    by_owner: dict[str, list[Any]] = {}
    for t in tools:
        by_owner.setdefault(t.owner_agent, []).append(t)

    sections = []
    for owner in sorted(by_owner):
        rows = "".join(
            f"<tr><td><code>{html.escape(t.name)}</code></td>"
            f"<td>{html.escape(t.description)}</td></tr>"
            for t in sorted(by_owner[owner], key=lambda t: t.name)
        )
        sections.append(
            f"<h4 style='margin:14px 0 6px'>{html.escape(owner.title())} agent</h4>"
            "<table style='width:100%;border-collapse:collapse'>"
            "<tr style='text-align:left'><th>Tool</th><th>Purpose</th></tr>"
            f"{rows}"
            "</table>"
        )
    return (
        '<div class="settings-card" style="margin-top:14px">'
        "<h3>Agent tools (deterministic pre-tools)</h3>"
        "<p>Each agent runs zero or more measurement tools BEFORE the LLM. "
        "These pre-tools ground the model in pixel facts and reduce the "
        "tokens the LLM has to spend speculating about colors, sizes, "
        "and metrics.</p>" + "".join(sections) + "</div>"
    )


def _cost_telemetry_html() -> str:
    """Render the cost-tracker snapshot as a Settings-tab card.

    Shows the LAST run's tokens + estimated USD + cache hits, plus the
    circuit-breaker state. Read-only — clicking "Refresh" regenerates
    the HTML, never reaches the API.
    """
    from src.llm.cost_tracker import get_circuit_breaker, get_cost_tracker

    s = get_cost_tracker().snapshot()
    b = get_circuit_breaker("openrouter").state()

    by_model_rows = ""
    for model, row in s["by_model"].items():
        by_model_rows += (
            f"<tr><td><code>{html.escape(model)}</code></td>"
            f"<td>{row['calls']}</td>"
            f"<td>{row['tokens']:,}</td>"
            f"<td>${row['usd']:.4f}</td></tr>"
        )
    if not by_model_rows:
        by_model_rows = "<tr><td colspan='4'><i>No LLM calls yet this session.</i></td></tr>"

    breaker_class = "ok" if b["state"] == "closed" else "fail"
    breaker_msg = (
        "Closed (normal traffic)"
        if b["state"] == "closed"
        else (
            f"OPEN — fast-failing for ~{b['remaining_s']:.0f}s "
            f"({b['fails']}/{b['threshold']} failures, "
            f"last={html.escape(b['last_reason'] or 'unknown')})"
        )
    )

    return (
        '<div class="settings-card" style="margin-top:14px">'
        "<h3>Cost &amp; resilience telemetry</h3>"
        "<p><b>This run</b></p>"
        "<ul>"
        f"<li>LLM calls: {s['calls']} &nbsp;·&nbsp; "
        f"cache hits: {s['cache_hits']} &nbsp;·&nbsp; "
        f"misses: {s['cache_misses']}</li>"
        f"<li>Tokens used: {s['total_tokens']:,} "
        f"(prompt {s['prompt_tokens']:,} / completion {s['completion_tokens']:,})</li>"
        f"<li>Estimated cost: <b>${s['estimated_usd']:.4f}</b></li>"
        "</ul>"
        '<table style="width:100%;border-collapse:collapse;margin-top:8px">'
        '<tr style="text-align:left">'
        "<th>Model</th><th>Calls</th><th>Tokens</th><th>Est. USD</th></tr>"
        f"{by_model_rows}"
        "</table>"
        f'<p style="margin-top:14px"><b>Circuit breaker</b>: '
        f'<span class="status-cell {breaker_class}" '
        'style="display:inline-flex;padding:4px 10px;border-radius:6px;font-size:12px">'
        f"{html.escape(breaker_msg)}</span></p>"
        "</div>"
    )


def _format_web_references(query: str, use_real: bool) -> str:
    if not use_real:
        return """
<div class="reference-card">
  <h3>Web references</h3>
  <p>Turn on real references for live web results.</p>
</div>
"""
    try:
        cfg = _fresh_settings()
        from src.tools.web_search import get_default_search

        provider = "Tavily" if cfg.tavily_api_key else "DuckDuckGo"
        hits = get_default_search().search(f"{query} UI design examples", k=5)
    except Exception as e:
        return f"""
<div class="reference-card">
  <h3>Web references</h3>
  <p>Search failed: {html.escape(str(e))}</p>
</div>
"""

    if not hits:
        return """
<div class="reference-card">
  <h3>Web references</h3>
  <p>No live results. Check TAVILY_API_KEY or network access.</p>
</div>
"""

    rows = "\n".join(
        "<li>"
        f'<a href="{html.escape(hit.url)}" target="_blank">'
        f"{html.escape(hit.title)}</a>"
        f"<br><span>{html.escape(hit.snippet[:180])}</span>"
        "</li>"
        for hit in hits
    )
    return f"""
<div class="reference-card">
  <h3>Web references from {provider}</h3>
  <ul>{rows}</ul>
</div>
"""
