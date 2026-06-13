"""Gradio UI — the demo surface judges actually interact with.

OWNER: Person E
SPRINT CONCEPTS:
    - Sprint 2: Gradio.
CONSUMES: ``run_graph``, ``LanceRetriever`` (Tab 3), ``settings``.
PROVIDES: ``main()`` — launches the Gradio Blocks app at 127.0.0.1:7860.

WHY YOU CARE
------------
Gradio is the curriculum's pick for Sprint 2 — and the right one. Drag-drop,
streaming, gallery, JSON viewer, theming, and queue-aware button states for
~150 lines of code. Judges interact here for 90 % of the demo, so its
polish directly affects Code-Quality scoring.

LOGIC OUTLINE / TAB MAP
-----------------------
Tab 1 — Analyze (this stub already wires Run + log + JSON output)
Tab 2 — Report   (TODO — render DesignReport from a gr.State)
Tab 3 — References (TODO — text query → gallery of retrieved refs)
Tab 4 — Settings (TODO — model tier picker, real-vs-fake toggle)

DEFINITION OF DONE
------------------
[ ] ``make ui`` opens a Gradio app at 127.0.0.1:7860 with all four tabs.
[ ] Tab 1 streams progress as agents run (use ``compiled.stream(state)``
    once Person A wires LangGraph; until then a single "Done" yield is OK).
[ ] Tab 2 renders the DesignReport from a ``gr.State`` updated by Tab 1.
[ ] Tab 3 calls ``deps.retriever.retrieve_by_text`` and displays a gallery.
[ ] Tab 4's "Use real APIs" checkbox flips ``USE_REAL`` for subsequent runs.
[ ] tests/person_e/test_ui_smoke.py passes (module imports cleanly).

DO NOT
------
- Do not block the event loop with synchronous LLM calls. Gradio queues
  handle async natively — wrap with ``async def`` once tools are async.
- Do not store the report in a module global. Use ``gr.State`` so multi-
  user sessions don't leak each other's data.
- Do not embed model API keys in client-visible code. Read from settings
  inside the handler.
- Do not skip ``demo.queue()``. Without it, the second user blocks the
  first.

CROSS-REFERENCES
----------------
- ``src/agents/graph.run_graph`` — main work driver.
- ``src/agents/base.build_default_deps(use_real=...)`` — wiring real vs fake.
- ``src/contracts.Retriever`` — Tab 3 uses this Protocol, not LanceRetriever.
- ``src/schemas/outputs.DesignReport`` — Tab 2 renders this shape.
"""
from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

from src.agents.base import AgentDeps, build_default_deps
from src.agents.graph import run_graph
from src.config import settings
from src.schemas.outputs import DesignReport
from src.utils.logger import get_logger

log = get_logger(__name__)


def on_run(
    image: Any,
    instructions: str,
    use_real: bool,
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """Streaming run handler — yields (markdown_log, report_dict) tuples.

    HINT: yield once per major node so the user sees progress. Today we
    yield twice (start + done). Once Person A wires LangGraph, replace the
    single ``run_graph(...)`` line with::

        for event in compiled.stream(state):
            for node, partial in event.items():
                yield (f"### {node} done — {len(partial)} fields", {})
        yield (f"### Done. Score = {report.overall_score:.1f}", report.model_dump())
    """
    if image is None:
        yield ("**Error:** please upload an image first.", {})
        return

    image_path = Path(image.name if hasattr(image, "name") else image)
    deps: AgentDeps = build_default_deps(use_real=use_real)

    yield (f"### Running graph on `{image_path.name}` ...", {})
    # TODO(person-e): replace this single call with a per-node yield loop
    # using ``compiled.stream(state)`` once langgraph is installed.
    report: DesignReport = run_graph(image_path, instructions=instructions or None, deps=deps)
    yield (f"### Done. Score = {report.overall_score:.1f}/100", report.model_dump())


def render_report(report: DesignReport | None) -> str:
    """Format the report as Markdown for Tab 2.

    Tab 2 binds this to a ``gr.State`` carrying the report from Tab 1.
    """
    if report is None:
        return "_No report yet._"
    lines: list[str] = [
        f"## Overall score: **{report.overall_score:.1f}/100**",
        "### Top strengths",
        *[f"- {s}" for s in report.top_strengths],
        "### Top recommendations",
    ]
    for r in report.top_recommendations:
        lines.append(f"- **{r.title}** (effort {r.effort} / impact {r.impact}) — {r.rationale}")
    # HINT: add per-agent accordion sections post-MVP:
    #   if report.visual: lines.append(f"### Visual\n```json\n{json.dumps(report.visual.model_dump(), indent=2)}\n```")
    #   ... same for ux, accessibility, brand, market.
    return "\n".join(lines)


def _gallery_query(deps: AgentDeps, query: str, k: int = 12) -> list[tuple[str, str]]:
    """Tab 3 helper — text query → list of (image_path, caption) tuples.

    HINT: Gradio gallery accepts list[tuple[path, caption]]:
        return [(r.image_path, f"{r.id} • {r.score:.2f}") for r in refs]
    """
    refs = deps.retriever.retrieve_by_text(query, k=k)
    return [(r.image_path, f"{r.id} • {r.score:.2f}") for r in refs]


def main() -> None:
    """Build the Blocks app and launch."""
    try:
        import gradio as gr  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit(
            "gradio is not installed. Run: pip install -r requirements/person-e-ui.txt"
        )

    with gr.Blocks(theme=gr.themes.Soft(), title="Design Analysis Suite") as demo:
        gr.Markdown("# Multimodal AI Design Analysis Suite")

        # NOTE: shared state holding the latest DesignReport across tabs.
        # gr.State is per-session, which keeps multi-user demos isolated.
        report_state = gr.State(value=None)

        with gr.Tabs():
            # ----- Tab 1: Analyze ---------------------------------------
            with gr.Tab("Analyze"):
                image_in = gr.File(label="Design (PNG / JPG)", file_types=["image"])
                instructions_in = gr.Textbox(label="Instructions", placeholder="audience, brand…")
                use_real_in = gr.Checkbox(value=settings.use_real, label="Use real APIs")
                run_btn = gr.Button("Run", variant="primary")
                log_out = gr.Markdown()
                json_out = gr.JSON(label="Raw report")
                run_btn.click(
                    fn=on_run,
                    inputs=[image_in, instructions_in, use_real_in],
                    outputs=[log_out, json_out],
                )
                # TODO(person-e): bind json_out → report_state via a small lambda
                # so Tab 2 picks it up. Sketch:
                #   json_out.change(lambda d: DesignReport.model_validate(d) if d else None,
                #                   inputs=[json_out], outputs=[report_state])

            # ----- Tab 2: Report ----------------------------------------
            with gr.Tab("Report"):
                gr.Markdown("_Run an analysis on Tab 1, then come back here._")
                # TODO(person-e):
                #   refresh_btn = gr.Button("Refresh")
                #   md = gr.Markdown()
                #   refresh_btn.click(fn=render_report, inputs=[report_state], outputs=[md])
                # HINT: alternative: use report_state.change for live updates.

            # ----- Tab 3: References ------------------------------------
            with gr.Tab("References"):
                gr.Markdown("_Browse / search the corpus._")
                # TODO(person-e):
                #   q = gr.Textbox(label="Search corpus", placeholder="e.g. fintech dashboard")
                #   gallery = gr.Gallery(columns=4, height=380)
                #   q.submit(
                #       fn=lambda text: _gallery_query(build_default_deps(use_real=True), text),
                #       inputs=[q], outputs=[gallery],
                #   )
                # HINT: cache build_default_deps once at module level; building it
                # per query reloads CLIP weights and is painfully slow.

            # ----- Tab 4: Settings --------------------------------------
            with gr.Tab("Settings"):
                gr.Markdown(f"`USE_REAL` toggle — currently {settings.use_real}.")
                # TODO(person-e):
                #   - model_tier = gr.Radio(["fast", "balanced", "quality"], value="balanced")
                #   - cache_disabled = gr.Checkbox(value=settings.cache_disabled, label="Disable cache")
                # HINT: changing these should not require a restart. Wire each
                # widget's .change() to update settings via setattr().

    demo.queue().launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":  # pragma: no cover
    main()
