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

import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.base import AgentDeps, build_default_deps  # noqa: E402
from src.agents.graph import run_graph  # noqa: E402
from src.config import settings  # noqa: E402
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
  --coral: #d45d4c;
  --gold: #b88718;
  --green-soft: #e7f4ef;
  --coral-soft: #faece8;
  --gold-soft: #f7efd8;
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
.status-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 18px;
}

.guide-card h3,
.result-card h3,
.status-card h3 {
  margin: 0 0 8px;
  font-size: 17px;
  letter-spacing: 0;
}

.guide-card p,
.guide-card li,
.result-card p,
.result-card li,
.status-card p {
  color: var(--soft-text);
  line-height: 1.5;
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

.report-wrap h2 {
  margin-top: 0;
}

.report-score {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--green-soft);
  color: #165a50;
  font-weight: 750;
}

.report-score span {
  font-size: 28px;
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

.gradio-container button.primary,
.gradio-container button.primary span,
.gradio-container .gradio-button.primary,
.gradio-container .gradio-button.primary span {
  background: #0f766e !important;
  border-color: #0f766e !important;
  color: #ffffff !important;
  font-weight: 750 !important;
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
  background-color: #0f766e !important;
  border-color: #0f766e !important;
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
  <h3>{title}</h3>
  <p>{body}</p>
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
                "Add a PNG or JPG screenshot first. Best inputs are full screens, flows, "
                "or dashboard views where text and visual hierarchy are readable.",
            ),
            {},
            None,
        )
        return

    image_path = Path(image.name if hasattr(image, "name") else image)
    deps: AgentDeps = build_default_deps(use_real=use_real)

    yield (
        _status_message(
            "Analysis running",
            f"Reviewing {image_path.name}. The agents are checking visual design, UX, "
            "accessibility, brand consistency, and market context.",
        ),
        {},
        None,
    )
    report: DesignReport = run_graph(image_path, instructions=instructions or None, deps=deps)
    report_dict = report.model_dump()
    yield (
        _status_message(
            "Report ready",
            f"Overall score: {report.overall_score:.1f}/100. Open the Report tab for "
            "strengths, recommendations, and market notes.",
        ),
        report_dict,
        report_dict,
    )


def render_report(report: DesignReport | dict[str, Any] | None) -> str:
    """Format the latest report as Markdown/HTML for Tab 2."""
    if report is None:
        return """_No report yet._

<div class="result-card">
  <h3>No report yet</h3>
  <p>Run an analysis from the Analyze tab. The report will appear here with a score,
  strengths, recommendations, and specialist findings.</p>
</div>
"""
    if isinstance(report, dict):
        report = DesignReport.model_validate(report)

    lines: list[str] = [
        '<div class="report-wrap">',
        "<h2>Design report</h2>",
        f'<div class="report-score"><span>{report.overall_score:.1f}</span>/100</div>',
        "<h3>Top strengths</h3>",
    ]
    lines.extend(f"- {s}" for s in report.top_strengths or ["No strengths returned yet."])
    lines.append("<h3>Prioritized recommendations</h3>")
    if report.top_recommendations:
        for r in report.top_recommendations:
            lines.append(
                f"- **{r.title}**  \n"
                f"  Effort: `{r.effort}` | Impact: `{r.impact}`  \n"
                f"  {r.rationale}"
            )
    else:
        lines.append("- No recommendations returned yet.")

    if report.visual:
        lines.extend(
            [
                "<h3>Visual analysis</h3>",
                f"- Layout: {report.visual.layout or 'Not returned'}",
                f"- Hierarchy: {report.visual.hierarchy or 'Not returned'}",
                f"- Density score: {report.visual.density_score:.1f}/100",
            ]
        )

    if report.accessibility:
        pass_text = (
            "pass"
            if report.accessibility.contrast_pass is True
            else "needs review" if report.accessibility.contrast_pass is False else "not measured"
        )
        lines.extend(["<h3>Accessibility</h3>", f"- Contrast: {pass_text}"])

    if report.market:
        lines.append("<h3>Market signals</h3>")
        lines.extend(f"- {t}" for t in report.market.trends or ["No trends returned yet."])

    lines.append("</div>")
    return "\n".join(lines)


def _gallery_query(deps: AgentDeps, query: str, k: int = 12) -> list[tuple[str, str]]:
    """Return Gradio gallery tuples from the configured retriever."""
    refs = deps.retriever.retrieve_by_text(query, k=k)
    return [(r.image_path, f"{r.id} - {r.score:.2f}") for r in refs]


def _gallery_query_from_ui(query: str, use_real: bool) -> list[tuple[str, str]]:
    """Build deps from the UI toggle and run a text search."""
    if not query.strip():
        return []
    deps = build_default_deps(use_real=use_real)
    return _gallery_query(deps, query, k=12)


def main() -> None:
    """Build and launch the Gradio Blocks app."""
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
  <h1>Multimodal AI Design Analysis Suite</h1>
  <p>
    Upload a product screenshot and get a structured review from specialist AI agents:
    visual design, UX, accessibility, brand consistency, and market research. Use it for
    product screens, dashboards, checkout flows, landing pages, or mobile app concepts.
  </p>
  <div class="chip-row">
    <span class="chip">Screenshot review</span>
    <span class="chip">Multi-agent critique</span>
    <span class="chip">Market context</span>
    <span class="chip">JSON report</span>
  </div>
</section>
"""
        )

        gr.HTML(
            """
<div class="steps">
  <div class="step accent-teal"><b>1. Upload</b><span>Use a clear PNG or JPG. Full screens work better than tiny crops.</span></div>
  <div class="step accent-coral"><b>2. Add context</b><span>Tell the agents the audience, brand, market, or goal.</span></div>
  <div class="step accent-gold"><b>3. Review</b><span>Expect a score, strengths, recommendations, findings, and citations.</span></div>
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
### Start a design review
Upload one screen or flow image. For best results, avoid blurry exports, heavy cropping,
or screenshots where important text is unreadable.
"""
                        )
                        image_in = gr.File(label="Design screenshot", file_types=["image"])
                        instructions_in = gr.Textbox(
                            label="Context for the agents",
                            placeholder="Example: audience: India fintech users; brand: premium but approachable; goal: improve onboarding conversion",
                            lines=4,
                        )
                        with gr.Row():
                            use_real_in = gr.Checkbox(
                                value=settings.use_real,
                                label="Use real APIs",
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
  <h3>What to upload</h3>
  <ul>
    <li>Mobile app or web product screenshots</li>
    <li>Dashboards, checkout flows, onboarding, landing pages</li>
    <li>PNG or JPG files with readable UI text</li>
  </ul>
</div>
<br>
<div class="guide-card accent-coral">
  <h3>What you will get</h3>
  <ul>
    <li>Overall design score</li>
    <li>Top strengths and prioritized fixes</li>
    <li>UX, accessibility, brand, and visual findings</li>
    <li>Market trends and competitor references</li>
  </ul>
</div>
"""
                        )

                log_out = gr.HTML(
                    _status_message(
                        "Ready",
                        "Upload a design screenshot and add a little context. The offline fake mode is safe for demos; real API mode uses configured keys.",
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
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML(
                            """
<div class="guide-card accent-gold">
  <h3>How to read the report</h3>
  <p>
    Start with the score and top recommendations. Then scan specialist sections
    for evidence you can hand to design, product, engineering, or brand partners.
  </p>
</div>
"""
                        )
                        refresh_btn = gr.Button("Refresh report")
                    with gr.Column(scale=3):
                        report_md = gr.Markdown(render_report(None))
                refresh_btn.click(fn=render_report, inputs=[report_state], outputs=[report_md])
                report_state.change(fn=render_report, inputs=[report_state], outputs=[report_md])

            with gr.Tab("References"):
                gr.HTML(
                    """
<div class="guide-card accent-teal">
  <h3>Reference search</h3>
  <p>Search the design corpus for comparable patterns. In fake mode this returns deterministic sample references; real mode uses the configured retriever.</p>
</div>
"""
                )
                with gr.Row():
                    q = gr.Textbox(
                        label="Search corpus",
                        placeholder="e.g. fintech dashboard, onboarding card stack, accessible checkout",
                        scale=4,
                    )
                    gallery_real = gr.Checkbox(
                        value=settings.use_real,
                        label="Use real retriever",
                        scale=1,
                    )
                gallery = gr.Gallery(columns=4, height=380, label="Similar references")
                q.submit(
                    fn=_gallery_query_from_ui,
                    inputs=[q, gallery_real],
                    outputs=[gallery],
                )

            with gr.Tab("Settings"):
                gr.HTML(
                    f"""
<div class="guide-card accent-gold">
  <h3>Runtime settings</h3>
  <p><b>USE_REAL</b>: {settings.use_real}</p>
  <p><b>Cache disabled</b>: {settings.cache_disabled}</p>
  <p><b>Reports directory</b>: {settings.report_dir}</p>
</div>
"""
                )

    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=7860,
        theme=gr.themes.Soft(),
        css=APP_CSS,
        js=FORCE_LIGHT_THEME_JS,
        head=FORCE_LIGHT_THEME_HEAD,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
