"""Gradio UI for the Multimodal AI Design Analysis Suite.

OWNER: Person E
SPRINT CONCEPTS: Sprint 4 — Gradio app surface for the multi-agent pipeline.
CONSUMES: ``agents.graph.run_graph``, ``agents.base.build_default_deps``,
          ``schemas.outputs.DesignReport``.
PROVIDES: a Gradio Blocks app on ``http://127.0.0.1:7860`` with three tabs:
          (1) full DesignReport JSON, (2) per-agent collapsibles, (3)
          retrieved reference matches.

WHY THIS FILE LIVES OUTSIDE ``src/``
------------------------------------
``src/`` is library code — imported by tests, the MCP server, and CI.
``ui/`` is user-facing entrypoint code. Keeping them separate avoids
"why did importing FakeLLM start a Gradio server?" surprises.

LAUNCH
------
    python ui/app.py            # offline (fakes), no API key
    USE_REAL=1 python ui/app.py # real OpenRouter, ≈ $0.03 / run
"""

from __future__ import annotations

import html
import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.base import AgentDeps, build_default_deps  # noqa: E402
from src.agents.graph import run_graph  # noqa: E402
import src.config as app_config  # noqa: E402
from src.config import Settings, settings  # noqa: E402
from src.schemas.outputs import DesignReport  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

log = get_logger(__name__)

APP_CSS = """
:root {
  color-scheme: light;
  --surface: #fbfaf6;
  --ink: #1d2528;
  --muted: #415054;
  --soft-text: #2f3b3f;
  --line: #d9ded8;
  --panel: #ffffff;
  --teal: #0f766e;
  --teal-dark: #0b5f58;
  --blue: #2563eb;
  --blue-dark: #1d4ed8;
  --coral: #d45d4c;
  --coral-dark: #a9473a;
  --gold: #b88718;
  --navy: #223645;
  --green-soft: #e7f4ef;
  --coral-soft: #faece8;
  --gold-soft: #f7efd8;
  --blue-soft: #e8f0f7;
}

html,
body {
  color-scheme: light;
}

.gradio-container {
  background:
    linear-gradient(180deg, #f7f6ef 0%, #fbfaf6 36%, #ffffff 100%) !important;
  color: var(--ink) !important;
}

.gradio-container label,
.gradio-container textarea,
.gradio-container input,
.gradio-container th,
.gradio-container td,
.gradio-container .prose,
.gradio-container .markdown,
.gradio-container .label-wrap,
.gradio-container .form,
.gradio-container .wrap {
  color: var(--ink) !important;
}

.gradio-container ::placeholder {
  color: #607174 !important;
  opacity: 1 !important;
}

.app-shell {
  max-width: 1180px;
  margin: 0 auto;
}

.hero-band {
  border: 1px solid var(--line);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(15, 118, 110, 0.10), rgba(212, 93, 76, 0.08)),
    #fffefa;
  padding: 28px 30px;
  margin: 18px 0 18px;
}

.hero-band h1 {
  margin: 0 0 10px;
  font-size: 34px;
  line-height: 1.08;
  letter-spacing: 0;
  color: var(--ink);
}

.hero-band p {
  max-width: 820px;
  margin: 0;
  color: #3f4c50;
  font-size: 16px;
  line-height: 1.55;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.chip {
  border: 1px solid rgba(15, 118, 110, 0.24);
  background: #ffffff;
  border-radius: 999px;
  color: #24504c;
  font-size: 13px;
  font-weight: 650;
  padding: 7px 11px;
}

.guide-card,
.result-card,
.status-card,
.settings-card,
.reference-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 18px;
}

.guide-card h3,
.result-card h3,
.status-card h3,
.settings-card h3,
.reference-card h3 {
  margin: 0 0 8px;
  font-size: 17px;
  letter-spacing: 0;
  color: var(--ink) !important;
}

.guide-card p,
.guide-card li,
.result-card p,
.result-card li,
.status-card p,
.settings-card p,
.settings-card li,
.reference-card p,
.reference-card li {
  color: var(--soft-text);
  line-height: 1.5;
}

.settings-card b,
.reference-card b {
  color: var(--ink) !important;
}

.reference-card a,
.settings-card a {
  color: #0b5f99 !important;
  font-weight: 700;
}

.steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 8px;
}

.step {
  border-radius: 8px;
  border: 1px solid #cdd6cf;
  background: #fffefb;
  padding: 14px;
  box-shadow: 0 1px 0 rgba(29, 37, 40, 0.04);
}

.step b {
  display: block;
  color: var(--ink);
  margin-bottom: 5px;
}

.step span {
  color: var(--soft-text);
  font-size: 13px;
  line-height: 1.4;
}

.accent-teal { border-left: 4px solid var(--teal); }
.accent-coral { border-left: 4px solid var(--coral); }
.accent-gold { border-left: 4px solid var(--gold); }

.upload-panel {
  border: 1px solid #c9d4cd;
  border-radius: 8px;
  background: #fffefb;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(29, 37, 40, 0.06);
}

.upload-panel h3,
.upload-panel p,
.upload-panel span,
.upload-panel label,
.upload-panel table,
.upload-panel th,
.upload-panel td {
  color: var(--ink) !important;
}

.upload-panel p {
  color: var(--soft-text) !important;
  font-size: 15px;
  line-height: 1.55;
}

.upload-panel textarea,
.upload-panel input {
  background: #ffffff !important;
  border-color: #bfcac3 !important;
  color: var(--ink) !important;
}

.upload-panel button,
.upload-panel [role="button"] {
  color: var(--ink) !important;
}

.upload-panel .table-wrap,
.upload-panel table {
  background: #ffffff !important;
}

.upload-panel th {
  background: #eef5f1 !important;
  color: #203235 !important;
  font-weight: 700 !important;
}

.upload-panel td {
  background: #ffffff !important;
  color: #243236 !important;
}

.upload-panel .wrap {
  gap: 14px;
}

.status-card {
  min-height: 124px;
  background: #f4fbf8;
  border-color: #bed8cc;
}

.status-card h3 {
  color: #0b5f58;
}

.reference-card {
  background: #f8fbff;
  border-color: #c9d9e8;
}

.settings-card {
  background: #ffffff;
  border-color: #c9d9e8;
  color: var(--ink) !important;
}

.settings-card,
.settings-card *,
.reference-card,
.reference-card * {
  color: var(--ink) !important;
  -webkit-text-fill-color: currentColor !important;
}

.settings-card p,
.settings-card li,
.reference-card p,
.reference-card li,
.reference-card span {
  color: var(--soft-text) !important;
}

.reference-panel,
.reference-panel .form,
.reference-panel .block,
.reference-panel .wrap,
.reference-panel .input-container,
.reference-panel .checkbox-container,
.reference-panel textarea,
.reference-panel input,
.reference-gallery,
.reference-gallery .wrap,
.reference-gallery .block,
.reference-gallery .empty,
.reference-gallery [data-testid="gallery"] {
  background: #ffffff !important;
  background-color: #ffffff !important;
  border-color: #b9c8c0 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

.reference-panel label.float,
.reference-panel .float,
.reference-panel [data-testid="block-info"],
.reference-panel .label-wrap,
.reference-panel .label-wrap *,
.reference-panel .block-label,
.reference-panel .block-title,
.reference-gallery label.float,
.reference-gallery .float,
.reference-gallery [data-testid="block-info"],
.reference-gallery .label-wrap,
.reference-gallery .label-wrap *,
.reference-gallery .block-label,
.reference-gallery .block-title {
  background: #eef5f1 !important;
  background-color: #eef5f1 !important;
  border: 1px solid #bed8cc !important;
  border-radius: 7px !important;
  color: #16282b !important;
  -webkit-text-fill-color: #16282b !important;
  font-weight: 750 !important;
}

.reference-panel input[type="checkbox"] {
  accent-color: var(--blue) !important;
}

.reference-panel button.primary,
.reference-panel button.primary *,
.reference-panel .primary,
.reference-panel .primary * {
  background: var(--blue) !important;
  background-color: var(--blue) !important;
  border-color: var(--blue-dark) !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}

.report-wrap,
.report-wrap * {
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

.report-wrap h2 {
  margin: 0 0 12px;
  font-size: 22px;
}

.report-wrap h3 {
  margin: 22px 0 8px;
  font-size: 16px;
}

.report-wrap ul {
  margin: 0;
  padding-left: 20px;
}

.report-wrap li {
  color: var(--soft-text) !important;
  -webkit-text-fill-color: var(--soft-text) !important;
  line-height: 1.55;
  margin-bottom: 7px;
}

.report-score {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--green-soft);
  border: 1px solid #bedccd;
  font-weight: 750;
}

.report-score,
.report-score * {
  color: #0b5f58 !important;
  -webkit-text-fill-color: #0b5f58 !important;
}

.report-score span {
  font-size: 30px;
  line-height: 1;
}

.report-tag {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 999px;
  background: #eef2f7;
  border: 1px solid #cdd6e0;
  margin-right: 6px;
}

.json-holder {
  border-radius: 8px;
  overflow: hidden;
}

button.primary,
.gradio-button.primary {
  background: #0f766e !important;
  border-color: #0f766e !important;
}

/* Contrast safety overrides for Gradio-generated controls. */
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4,
.gradio-container h5,
.gradio-container h6,
.gradio-container p,
.gradio-container li,
.gradio-container label,
.gradio-container legend,
.gradio-container .prose,
.gradio-container .markdown,
.gradio-container .caption,
.gradio-container .label-wrap,
.gradio-container .block-title,
.gradio-container .block-label {
  color: var(--ink) !important;
}

.gradio-container p,
.gradio-container li,
.gradio-container .prose,
.gradio-container .markdown {
  color: var(--soft-text) !important;
}

.gradio-container button,
.gradio-container button span,
.gradio-container [role="button"],
.gradio-container [role="button"] span {
  color: var(--ink) !important;
}

.gradio-container button:not([role="tab"]):not(.primary),
.gradio-container button:not([role="tab"]):not(.primary) span {
  background: #ffffff !important;
  border-color: #9db2bf !important;
  color: #173247 !important;
  font-weight: 700 !important;
}

.gradio-container button:not([role="tab"]):not(.primary):hover {
  background: #e8f1ff !important;
  border-color: var(--blue) !important;
}

.gradio-container button.primary,
.gradio-container button.primary span,
.gradio-container .gradio-button.primary,
.gradio-container .gradio-button.primary span {
  background: var(--blue) !important;
  border-color: var(--blue-dark) !important;
  color: #ffffff !important;
  font-weight: 750 !important;
}

.gradio-container button.primary:hover,
.gradio-container .gradio-button.primary:hover {
  background: var(--blue-dark) !important;
  border-color: #1e40af !important;
}

.gradio-container button[role="tab"],
.gradio-container button[role="tab"] span,
.gradio-container .tab-nav button,
.gradio-container .tab-nav button span {
  background: #ffffff !important;
  border-color: #cbd7cf !important;
  color: #1d2528 !important;
  font-weight: 700 !important;
}

.gradio-container button[role="tab"][aria-selected="true"],
.gradio-container button[role="tab"][aria-selected="true"] span,
.gradio-container .tab-nav button.selected,
.gradio-container .tab-nav button.selected span {
  background: #0f766e !important;
  border-color: #0f766e !important;
  color: #ffffff !important;
}

.gradio-container textarea,
.gradio-container input,
.gradio-container table,
.gradio-container th,
.gradio-container td {
  color: #1d2528 !important;
}

.gradio-container th {
  background: #eaf3ef !important;
  color: #16282b !important;
}

.gradio-container td {
  background: #ffffff !important;
}

.gradio-container [data-testid="file"],
.gradio-container [data-testid="file"] *,
.gradio-container .file-preview,
.gradio-container .file-preview *,
.gradio-container .upload-container,
.gradio-container .upload-container *,
.gradio-container .filepond--drop-label,
.gradio-container .filepond--drop-label * {
  color: #1d2528 !important;
}

.gradio-container [data-testid="file"],
.gradio-container .upload-container,
.gradio-container .filepond--root {
  background: #ffffff !important;
  border-color: #b9c8c0 !important;
}

.gradio-container .upload-panel .form,
.gradio-container .upload-panel .block,
.gradio-container .upload-panel .wrap,
.gradio-container .upload-panel .input-container,
.gradio-container .upload-panel .checkbox-container,
.gradio-container .upload-panel [data-testid="file"],
.gradio-container .upload-panel .file-preview,
.gradio-container .upload-panel .upload-container,
.gradio-container .upload-panel .filepond--root,
.gradio-container .upload-panel .filepond--panel,
.gradio-container .upload-panel .filepond--drop-label {
  background: #ffffff !important;
  background-color: #ffffff !important;
  border-color: #b9c8c0 !important;
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

.gradio-container .upload-panel .form *,
.gradio-container .upload-panel .block *,
.gradio-container .upload-panel [data-testid="file"] *,
.gradio-container .upload-panel .file-preview *,
.gradio-container .upload-panel .upload-container *,
.gradio-container .upload-panel .filepond--drop-label *,
.gradio-container .upload-panel .checkbox-container *,
.gradio-container .upload-panel textarea,
.gradio-container .upload-panel textarea *,
.gradio-container .upload-panel input,
.gradio-container .upload-panel input * {
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

.gradio-container .upload-panel label.float,
.gradio-container .upload-panel .float,
.gradio-container .upload-panel [data-testid="block-info"],
.gradio-container .upload-panel .label-wrap,
.gradio-container .upload-panel .label-wrap *,
.gradio-container .upload-panel .block-label,
.gradio-container .upload-panel .block-title {
  background: #eef5f1 !important;
  background-color: #eef5f1 !important;
  color: #16282b !important;
  -webkit-text-fill-color: #16282b !important;
  border: 1px solid #bed8cc !important;
  border-radius: 7px !important;
  font-weight: 750 !important;
}

.gradio-container .upload-panel textarea,
.gradio-container .upload-panel input[type="text"] {
  background: #ffffff !important;
  background-color: #ffffff !important;
  border: 1px solid #b9c8c0 !important;
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

.gradio-container .upload-panel input[type="checkbox"] {
  accent-color: #0f766e !important;
}

.gradio-container .gr-accordion,
.gradio-container .gr-accordion *,
.gradio-container details,
.gradio-container details * {
  background-color: #fffefb !important;
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

@media (max-width: 760px) {
  .hero-band {
    padding: 22px 18px;
  }

  .hero-band h1 {
    font-size: 28px;
  }

  .steps {
    grid-template-columns: 1fr;
  }
}

.gradio-container .upload-panel button.primary,
.gradio-container .upload-panel button.primary.svelte-xzq5jh,
.gradio-container button.primary,
.gradio-container button.primary *,
.gradio-container .primary,
.gradio-container .primary * {
  background-color: var(--blue) !important;
  border-color: var(--blue-dark) !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
"""

FORCE_LIGHT_THEME_JS = """
() => {
  const root = document.documentElement;
  root.classList.remove("dark");
  root.classList.add("light");
  root.dataset.theme = "light";
  localStorage.setItem("theme", "light");
  localStorage.setItem("__theme", "light");
  localStorage.setItem("gradio-theme", "light");

  const params = new URLSearchParams(window.location.search);
  if (params.get("__theme") !== "light") {
    params.set("__theme", "light");
    const nextUrl = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
  }

  return [];
}
"""

FORCE_LIGHT_THEME_HEAD = """
<script>
  document.documentElement.classList.remove("dark");
  document.documentElement.classList.add("light");
  document.documentElement.dataset.theme = "light";
  localStorage.setItem("theme", "light");
  localStorage.setItem("__theme", "light");
  localStorage.setItem("gradio-theme", "light");
</script>
"""


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
            setattr(module, "settings", settings)
    return settings


def _has_openrouter_key() -> bool:
    cfg = _fresh_settings()
    return bool(
        cfg.openrouter_api_key
        and "REPLACE_ME" not in cfg.openrouter_api_key
    )


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
        f"<a href=\"{html.escape(hit.url)}\" target=\"_blank\">"
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


def on_run(
    image: Any,
    instructions: str,
    use_real: bool,
) -> Generator[tuple[str, dict[str, Any], dict[str, Any] | None], None, None]:
    """Streaming run handler for Tab 1."""
    if image is None:
        yield (
            _status_message(
                "Upload needed",
                "Add a PNG or JPG screenshot first.",
            ),
            {},
            None,
        )
        return

    image_path = Path(image.name if hasattr(image, "name") else image)
    _fresh_settings()
    if use_real and not _has_openrouter_key():
        yield (
            _status_message(
                "Missing API key",
                "Set OPENROUTER_API_KEY in .env and click Run again.",
            ),
            {},
            None,
        )
        return

    deps: AgentDeps = build_default_deps(use_real=use_real)

    yield (
        _status_message(
            "Analysis running",
            f"Reviewing {image_path.name} with {'real APIs' if use_real else 'offline fakes'}.",
        ),
        {},
        None,
    )
    report: DesignReport = run_graph(image_path, instructions=instructions or None, deps=deps)
    report_dict = report.model_dump()
    yield (
        _status_message(
            "Report ready",
            f"Score: {report.overall_score:.1f}/100. Open Report.",
        ),
        report_dict,
        report_dict,
    )


def _ul(items: list[str]) -> str:
    """Render an escaped HTML list (items may contain pre-escaped markup)."""
    rows = "".join(f"<li>{item}</li>" for item in items)
    return f"<ul>{rows}</ul>"


def render_report(report: DesignReport | dict[str, Any] | None) -> str:
    """Format the latest report as a self-contained HTML block for the Report tab."""
    if report is None:
        return """
<div class="result-card">
  <h3>No report yet</h3>
  <p>Run an analysis from the Analyze tab. The score, strengths, recommendations,
  and specialist findings will appear here.</p>
</div>
"""
    if isinstance(report, dict):
        report = DesignReport.model_validate(report)

    e = html.escape
    parts: list[str] = [
        '<div class="report-wrap">',
        "<h2>Design report</h2>",
        f'<div class="report-score"><span>{report.overall_score:.1f}</span> / 100</div>',
        "<h3>Top strengths</h3>",
        _ul([e(s) for s in report.top_strengths] or ["No strengths returned yet."]),
        "<h3>Prioritized recommendations</h3>",
    ]
    if report.top_recommendations:
        recs = [
            f"<b>{e(r.title)}</b><br>"
            f'<span class="report-tag">Effort {e(str(r.effort))}</span>'
            f'<span class="report-tag">Impact {e(str(r.impact))}</span><br>'
            f"{e(r.rationale)}"
            for r in report.top_recommendations
        ]
        parts.append(_ul(recs))
    else:
        parts.append(_ul(["No recommendations returned yet."]))

    if report.visual:
        parts.append("<h3>Visual analysis</h3>")
        parts.append(
            _ul(
                [
                    f"Layout: {e(report.visual.layout or 'Not returned')}",
                    f"Hierarchy: {e(report.visual.hierarchy or 'Not returned')}",
                    f"Density score: {report.visual.density_score:.1f}/100",
                ]
            )
        )

    if report.accessibility:
        pass_text = (
            "pass"
            if report.accessibility.contrast_pass is True
            else "needs review" if report.accessibility.contrast_pass is False else "not measured"
        )
        parts.append("<h3>Accessibility</h3>")
        parts.append(_ul([f"Contrast: {pass_text}"]))

    if report.market:
        parts.append("<h3>Market signals</h3>")
        parts.append(_ul([e(t) for t in report.market.trends] or ["No trends returned yet."]))

    parts.append("</div>")
    return "\n".join(parts)


def _gallery_query(deps: AgentDeps, query: str, k: int = 12) -> list[tuple[str, str]]:
    """Return Gradio gallery tuples from the configured retriever."""
    refs = deps.retriever.retrieve_by_text(query, k=k)
    return [(_resolve_reference_path(r.image_path), f"{r.id} - {r.score:.2f}") for r in refs]


def _reference_query_from_ui(query: str) -> tuple[list[tuple[str, str]], str]:
    """Search local image refs (LanceDB) and live web refs (Tavily/DuckDuckGo)."""
    _fresh_settings()
    if not query.strip():
        return [], """
<div class="reference-card">
  <h3>Similar references</h3>
  <p>Type a pattern or product category.</p>
</div>
"""

    gallery_items: list[tuple[str, str]] = []
    local_files = _local_reference_file_count()
    vector_rows = _vector_row_count()

    if vector_rows > 0:
        try:
            deps = build_default_deps(use_real=True)
            gallery_items = _gallery_query(deps, query, k=12)
        except Exception as e:
            log.warning("references: retriever failed: %s", e)

    status = (
        f"{vector_rows} indexed references from {local_files} local files."
        if gallery_items
        else "No indexed matches yet. Add images to the reference dir and run make ingest."
    )

    web_refs = _format_web_references(query, use_real=True)
    return gallery_items, f"""
<div class="reference-card">
  <h3>Similar references</h3>
  <p>{html.escape(status)}</p>
</div>
{web_refs}
"""


def main() -> None:
    """Build and launch the Gradio Blocks app."""
    cfg = _fresh_settings()
    try:
        import gradio as gr  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit(
            "gradio is not installed. Run: pip install -r requirements/person-e-ui.txt"
        ) from e

    with gr.Blocks(title="Design Analysis Suite") as demo, gr.Column(elem_classes=["app-shell"]):
        gr.HTML(
            """
<section class="hero-band">
  <h1>Design Analysis Suite</h1>
  <p>
    Upload a screen for a fast visual, UX, accessibility, brand, and market review.
  </p>
  <div class="chip-row">
    <span class="chip">Visual</span>
    <span class="chip">UX</span>
    <span class="chip">Accessibility</span>
    <span class="chip">Market</span>
  </div>
</section>
"""
        )

        gr.HTML(
            """
<div class="steps">
  <div class="step accent-teal"><b>1. Upload</b><span>Use a clear PNG or JPG.</span></div>
  <div class="step accent-coral"><b>2. Add context</b><span>Audience, brand, goal.</span></div>
  <div class="step accent-gold"><b>3. Review</b><span>Score, fixes, and evidence.</span></div>
</div>
"""
        )

        report_state = gr.State(value=None)

        with gr.Tabs():
            with gr.Tab("Analyze"):
                with gr.Row():
                    with gr.Column(scale=3, elem_classes=["upload-panel"]):
                        gr.Markdown(
                            """
### Analyze a screen
Upload a screenshot. Add context if useful.
"""
                        )
                        image_in = gr.File(label="Design screenshot", file_types=["image"])
                        instructions_in = gr.Textbox(
                            label="Context",
                            placeholder="Audience, brand, market, or goal",
                            lines=3,
                        )
                        with gr.Row():
                            use_real_in = gr.Checkbox(
                                value=_default_real_mode(),
                                label="Use real APIs from .env",
                            )
                            run_btn = gr.Button("Run analysis", variant="primary")
                        gr.Examples(
                            examples=[
                                [
                                    "src/fakes/fixtures/sample.png",
                                    "audience: Indian retail banking users; brand: trustworthy, modern, accessible",
                                    False,
                                ]
                            ],
                            inputs=[image_in, instructions_in, use_real_in],
                            label="Try the bundled sample",
                        )

                    with gr.Column(scale=2):
                        gr.HTML(
                            """
<div class="guide-card accent-teal">
  <h3>Good inputs</h3>
  <ul>
    <li>Readable UI screenshots</li>
    <li>Dashboards, onboarding, checkout</li>
    <li>Full screens work best</li>
  </ul>
</div>
<br>
<div class="guide-card accent-coral">
  <h3>Output</h3>
  <ul>
    <li>Score and key strengths</li>
    <li>Prioritized fixes</li>
    <li>Evidence and references</li>
  </ul>
</div>
"""
                        )

                log_out = gr.HTML(
                    _status_message(
                        "Ready",
                        "Upload a screenshot. Real mode reads .env.",
                    )
                )
                with gr.Accordion("Raw structured report", open=False):
                    json_out = gr.JSON(label="DesignReport JSON", elem_classes=["json-holder"])

                run_btn.click(
                    fn=on_run,
                    inputs=[image_in, instructions_in, use_real_in],
                    outputs=[log_out, json_out, report_state],
                )

            with gr.Tab("Report"):
                report_view = gr.HTML(render_report(None))
                report_state.change(
                    fn=render_report, inputs=[report_state], outputs=[report_view]
                )

            with gr.Tab("References"):
                gr.HTML(
                    """
<div class="guide-card accent-teal">
  <h3>References</h3>
  <p>Search returns similar indexed designs (LanceDB) plus live web examples (Tavily).</p>
</div>
"""
                )
                with gr.Row(elem_classes=["reference-panel"]):
                    q = gr.Textbox(
                        label="Search",
                        placeholder="fintech dashboard, onboarding, checkout",
                        scale=4,
                    )
                    ref_btn = gr.Button("Search", variant="primary", scale=1)
                gallery = gr.Gallery(
                    columns=4,
                    height=380,
                    label="Similar references",
                    elem_classes=["reference-gallery"],
                )
                reference_notes = gr.HTML(
                    """
<div class="reference-card">
  <h3>Similar references</h3>
  <p>Search for local matches and live web references.</p>
</div>
"""
                )
                q.submit(
                    fn=_reference_query_from_ui,
                    inputs=[q],
                    outputs=[gallery, reference_notes],
                )
                ref_btn.click(
                    fn=_reference_query_from_ui,
                    inputs=[q],
                    outputs=[gallery, reference_notes],
                )

            with gr.Tab("Settings"):
                gr.HTML(
                    f"""
<div class="settings-card">
  <h3>Runtime settings</h3>
  <p><b>Real API key loaded</b>: {_has_openrouter_key()}</p>
  <p><b>USE_REAL in .env</b>: {cfg.use_real}</p>
  <p><b>Tavily key loaded</b>: {bool(cfg.tavily_api_key)}</p>
  <p><b>Local reference images</b>: {_local_reference_file_count()}</p>
  <p><b>Indexed reference rows</b>: {_vector_row_count()}</p>
  <p><b>Reports</b>: {cfg.report_dir}</p>
</div>
"""
                )

    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        theme=gr.themes.Soft(),
        css=APP_CSS,
        js=FORCE_LIGHT_THEME_JS,
        head=FORCE_LIGHT_THEME_HEAD,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
