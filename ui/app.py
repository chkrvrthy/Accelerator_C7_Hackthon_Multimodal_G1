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
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402, F401  # `settings` is reassigned via `global` in _fresh_settings
    Settings,
    settings,
)
from src.utils.logger import get_logger  # noqa: E402

log = get_logger(__name__)

from ui.handlers import on_run  # noqa: E402
from ui.references import _reference_query_from_ui, _references_for_report  # noqa: E402
from ui.render import render_report  # noqa: E402
from ui.state import (  # noqa: E402
    _cache_file_count,
    _cost_telemetry_html,
    _default_real_mode,
    _fresh_settings,
    _has_openrouter_key,
    _local_reference_file_count,
    _status_message,
    _tool_registry_html,
    _vector_row_count,
)
from ui.styles import APP_CSS, FORCE_LIGHT_THEME_HEAD, FORCE_LIGHT_THEME_JS  # noqa: E402


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
  <span class="eyebrow">Multimodal review</span>
  <h1>Design Analysis Suite</h1>
  <p>
    Upload a screen for a fast visual, UX, accessibility, brand, and market review.
    Five specialist agents critique in parallel and ship a single prioritized report.
  </p>
  <div class="chip-row">
    <span class="chip">Visual</span>
    <span class="chip">UX</span>
    <span class="chip">Accessibility</span>
    <span class="chip">Brand</span>
    <span class="chip">Market</span>
  </div>
</section>
"""
        )

        gr.HTML(
            """
<div class="steps">
  <div class="step accent-teal"  data-step="1"><b>Upload</b><span>A clear PNG or JPG of the screen you want reviewed.</span></div>
  <div class="step accent-coral" data-step="2"><b>Add context</b><span>Audience, brand voice, market &mdash; helps every agent.</span></div>
  <div class="step accent-gold"  data-step="3"><b>Review</b><span>Score, prioritized fixes, and per-specialist evidence.</span></div>
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
                        image_in = gr.File(
                            label="Design screenshot",
                            file_types=["image"],
                            type="filepath",
                        )
                        gr.Markdown(
                            "_PNG / JPG / WebP up to 20 MB. Larger files are "
                            "rejected with a clear message; oversized images "
                            "are auto-resized to 1024 px on the long edge "
                            "before any model call._",
                            elem_classes=["upload-tip"],
                        )
                        instructions_in = gr.Textbox(
                            label="Context",
                            placeholder="Audience, brand, market, or goal",
                            lines=3,
                        )
                        run_btn = gr.Button("Run analysis", variant="primary")
                        gr.Markdown(
                            "_Mode is read from `.env` — "
                            f"currently **{'real APIs' if _default_real_mode() else 'offline fakes'}**. "
                            "Toggle `USE_REAL` in `.env` to switch._",
                            elem_classes=["mode-tip"],
                        )
                        gr.Examples(
                            examples=[
                                [
                                    "src/fakes/fixtures/sample.png",
                                    "audience: Indian retail banking users; brand: trustworthy, modern, accessible",
                                ]
                            ],
                            inputs=[image_in, instructions_in],
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
                        "Upload a screenshot. The mode (real APIs vs fakes) is read from .env.",
                    )
                )
                with gr.Accordion("Raw structured report", open=False):
                    json_out = gr.JSON(label="DesignReport JSON", elem_classes=["json-holder"])

                run_btn.click(
                    fn=on_run,
                    inputs=[image_in, instructions_in],
                    outputs=[log_out, json_out, report_state],
                )

            with gr.Tab("Report"):
                report_view = gr.HTML(render_report(None))
                report_state.change(fn=render_report, inputs=[report_state], outputs=[report_view])

            with gr.Tab("References"):
                gr.HTML(
                    """
<div class="guide-card accent-teal">
  <h3>References</h3>
  <p>The top section shows references the agents <b>actually used</b> in
  the latest analysis (brand RAG + market citations). Use search below to
  add supplementary references from the local index and the live web.</p>
</div>
"""
                )

                run_refs_gallery = gr.Gallery(
                    columns=4,
                    height=320,
                    label="Brand references retrieved by THIS run",
                    elem_classes=["reference-gallery"],
                )
                run_refs_notes = gr.HTML(
                    """
<div class="reference-card">
  <h3>References used in this run</h3>
  <p>Run an analysis from the <b>Analyze</b> tab. The references the
  brand and market agents consulted will appear here automatically.</p>
</div>
"""
                )

                gr.HTML(
                    """
<div class="guide-card accent-coral" style="margin-top:18px">
  <h3>Search for more references</h3>
  <p>Optional supplementary search across the local index and live web.</p>
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
                    label="Search results",
                    elem_classes=["reference-gallery"],
                )
                reference_notes = gr.HTML(
                    """
<div class="reference-card">
  <h3>Search results</h3>
  <p>Type a pattern or product category and press Search.</p>
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

                # Auto-populate the run-references section whenever a new
                # report lands in `report_state`. This is the contextual
                # link that ties the References tab to the current run.
                report_state.change(
                    fn=_references_for_report,
                    inputs=[report_state],
                    outputs=[run_refs_gallery, run_refs_notes],
                )

            with gr.Tab("Settings"):
                gr.HTML(
                    f"""
<div class="settings-card">
  <h3>Runtime settings</h3>
  <p><b>Real API key loaded</b>: {_has_openrouter_key()}</p>
  <p><b>USE_REAL in .env</b>: {cfg.use_real}</p>
  <p><b>Default text model</b>: <code>{html.escape(cfg.default_text_model)}</code></p>
  <p><b>Default vision model</b>: <code>{html.escape(cfg.default_vision_model)}</code></p>
  <p><b>Default temperature</b>: {cfg.default_temperature}</p>
  <p><b>Max tokens (per call)</b>: {cfg.default_max_tokens:,}</p>
  <p><b>Cache</b>: {"DISABLED" if cfg.cache_disabled else "enabled"}
     ({_cache_file_count()} cached responses on disk)</p>
  <p><b>Tavily key loaded</b>: {bool(cfg.tavily_api_key)}</p>
  <p><b>Local reference images</b>: {_local_reference_file_count()}</p>
  <p><b>Indexed reference rows</b>: {_vector_row_count()}</p>
  <p><b>Reports</b>: <code>{cfg.report_dir}</code></p>
</div>
"""
                )

                # Live cost telemetry — refreshes when the user clicks
                # the button. We don't auto-poll because that itself
                # would burn a tiny bit of CPU; one explicit click is
                # enough for a hackathon demo.
                cost_view = gr.HTML(_cost_telemetry_html())
                refresh_btn = gr.Button("Refresh telemetry", variant="secondary")
                refresh_btn.click(fn=_cost_telemetry_html, outputs=[cost_view])

                # Tool registry — auditable list of all per-agent tools.
                gr.HTML(_tool_registry_html())

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
