#!/usr/bin/env python3
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
    ./ui/app.py                 # POSIX shells (shebang + executable bit)
    python ui/app.py            # cross-platform (works on Windows too)
    USE_REAL=1 python ui/app.py # real OpenRouter, ≈ $0.03 / run
"""

from __future__ import annotations

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

from ui.strings import (  # noqa: E402
    ANALYZE_HELP_HTML,
    CONTEXT_FIELD_INFO,
    CONTEXT_FIELD_PLACEHOLDER,
    COST_TELEMETRY_HEADER_HTML,
    EMPTY_LOG_BODY,
    FRAME_LABELS_INFO,
    HERO_BAND_HTML,
    REFERENCES_INTRO_HTML,
    REFERENCES_RUN_EMPTY_HTML,
    REFERENCES_SEARCH_EMPTY_HTML,
    REFERENCES_SEARCH_HEADER_HTML,
    REFERENCES_SEARCH_INFO,
    RUN_BUTTON_TIP_MARKDOWN,
    SETTINGS_INTRO_HTML,
    STEPS_EXPLAINER_HTML,
    TOOL_REGISTRY_HEADER_HTML,
    runtime_config_card_html,
)
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
        gr.HTML(HERO_BAND_HTML)
        gr.HTML(STEPS_EXPLAINER_HTML)

        report_state = gr.State(value=None)

        with gr.Tabs():
            with gr.Tab("Analyze"):
                gr.HTML(ANALYZE_HELP_HTML)
                with gr.Column(elem_classes=["upload-panel"]):
                    image_in = gr.File(
                        label="Design screenshots (up to 5 of the same product)",
                        file_types=["image"],
                        type="filepath",
                        file_count="multiple",
                    )
                    frame_labels_in = gr.Textbox(
                        label="Frame labels",
                        placeholder="Hero\nPricing\nDashboard",
                        lines=3,
                        info=FRAME_LABELS_INFO,
                    )
                    instructions_in = gr.Textbox(
                        label="Context",
                        placeholder=CONTEXT_FIELD_PLACEHOLDER,
                        lines=3,
                        info=CONTEXT_FIELD_INFO,
                    )
                    run_btn = gr.Button("Run analysis", variant="primary")
                    gr.Markdown(
                        RUN_BUTTON_TIP_MARKDOWN,
                        elem_classes=["upload-tip"],
                    )
                    gr.Markdown(
                        "Mode is read from *.env* — "
                        f"currently {'real APIs' if _default_real_mode() else 'offline fakes'}. "
                        "Toggle *USE_REAL* in *.env* to switch."
                    )
                    gr.Examples(
                        examples=[
                            [
                                ["src/fakes/fixtures/sample.png"],
                                "Sample dashboard",
                                "audience: Indian retail banking users; brand: trustworthy, modern, accessible",
                            ]
                        ],
                        inputs=[image_in, frame_labels_in, instructions_in],
                        label="Try the bundled sample",
                    )

                log_out = gr.HTML(_status_message("Ready", EMPTY_LOG_BODY))
                with gr.Accordion("Raw structured report", open=False):
                    json_out = gr.JSON(label="DesignReport JSON", elem_classes=["json-holder"])

                run_btn.click(
                    fn=on_run,
                    inputs=[image_in, instructions_in, frame_labels_in],
                    outputs=[log_out, json_out, report_state],
                )

            with gr.Tab("Report"):
                report_view = gr.HTML(render_report(None))
                report_state.change(fn=render_report, inputs=[report_state], outputs=[report_view])

            with gr.Tab("References"):
                gr.HTML(REFERENCES_INTRO_HTML)
                run_refs_gallery = gr.Gallery(
                    columns=4,
                    height=320,
                    label="Brand references retrieved by THIS run",
                    elem_classes=["reference-gallery"],
                )
                run_refs_notes = gr.HTML(REFERENCES_RUN_EMPTY_HTML)

                gr.HTML(REFERENCES_SEARCH_HEADER_HTML)
                with gr.Row(elem_classes=["reference-panel"]):
                    q = gr.Textbox(
                        label="Search",
                        placeholder="fintech dashboard, onboarding, checkout",
                        scale=4,
                        info=REFERENCES_SEARCH_INFO,
                    )
                    ref_btn = gr.Button("Search", variant="primary", scale=1)
                gallery = gr.Gallery(
                    columns=4,
                    height=380,
                    label="Search results",
                    elem_classes=["reference-gallery"],
                )
                reference_notes = gr.HTML(REFERENCES_SEARCH_EMPTY_HTML)
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

                report_state.change(
                    fn=_references_for_report,
                    inputs=[report_state],
                    outputs=[run_refs_gallery, run_refs_notes],
                )

            with gr.Tab("Settings"):
                gr.HTML(SETTINGS_INTRO_HTML)
                gr.HTML(
                    runtime_config_card_html(
                        cfg,
                        has_openrouter_key=_has_openrouter_key(),
                        cache_file_count=_cache_file_count(),
                        local_reference_file_count=_local_reference_file_count(),
                        vector_row_count=_vector_row_count(),
                    )
                )

                gr.HTML(COST_TELEMETRY_HEADER_HTML)
                cost_view = gr.HTML(_cost_telemetry_html())
                refresh_btn = gr.Button("Refresh telemetry", variant="secondary")
                refresh_btn.click(fn=_cost_telemetry_html, outputs=[cost_view])

                gr.HTML(TOOL_REGISTRY_HEADER_HTML)
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
