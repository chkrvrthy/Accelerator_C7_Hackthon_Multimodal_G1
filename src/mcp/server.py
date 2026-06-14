"""MCP server exposing design-analysis tools over stdio.

OWNER: Person E
SPRINT CONCEPTS: Sprint 4 — Model Context Protocol.
CONSUMES: ``mcp`` SDK (lazy import), ``agents.graph.run_graph``,
          ``agents.base.build_default_deps``.
PROVIDES: ``analyze_design_tool``, ``search_designs_tool`` (testable
          callables), ``main()`` (FastMCP stdio server).

WHY THIS FILE EXISTS
--------------------
The Gradio UI is for humans. This file is for *other AI agents*. Any
MCP-compatible client (Claude Code, Continue, Cline, Zed, ...) can spawn
this server, list its tools, and invoke them as if they were native
function calls. Same backend; two completely different surface areas.

DEFINITION OF DONE
------------------
[x] ``analyze_design_tool`` runs the full graph and returns a serializable
    DesignReport dict.
[x] ``search_designs_tool`` returns a list of RetrievedRef dicts.
[x] ``main`` registers both as ``@mcp.tool()`` and starts a stdio server.
[x] Importing this module does NOT pull the mcp SDK (lazy import inside
    ``main``) so non-Person-E slices stay import-cheap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.graph import run_graph
from src.utils.logger import get_logger

log = get_logger(__name__)


def analyze_design_tool(
    image_path: str | None = None,
    instructions: str | None = None,
    *,
    image_paths: list[str] | None = None,
    frame_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full design-analysis graph on one or more frames.

    Args:
        image_path: Single-frame path. Backwards-compatible with the
            original MCP contract; ignored when ``image_paths`` is set.
        instructions: Optional brief about audience / brand / goal.
        image_paths: Multi-frame mode — 1..5 paths analysed as ONE
            coherent product. When provided, ``image_path`` is ignored.
        frame_labels: Optional human-readable labels parallel to
            ``image_paths`` (e.g. ``["Hero", "Pricing", "Dashboard"]``).
            Missing entries fall back to filename stems server-side.

    Returns:
        Serialized DesignReport dict including the new multi-frame
        fields (``frame_labels``, ``per_frame_scores``,
        ``top_recommendations[*].affected_frames``).

    Raises:
        ValueError: when neither ``image_path`` nor ``image_paths`` is set.
    """
    paths: list[str] | str
    if image_paths:
        paths = list(image_paths)
        log.info(
            "mcp.analyze_design paths=%d (multi-frame): %s",
            len(paths),
            ", ".join(paths),
        )
    elif image_path:
        paths = image_path
        log.info("mcp.analyze_design path=%s (single-frame)", image_path)
    else:
        raise ValueError(
            "analyze_design_tool requires either image_path (str) or "
            "image_paths (list[str])."
        )
    report = run_graph(
        [Path(p) for p in paths] if isinstance(paths, list) else Path(paths),
        instructions=instructions,
        frame_labels=frame_labels,
    )
    return report.model_dump()


def search_designs_tool(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Search the reference corpus by text query."""
    from src.agents.base import build_default_deps

    deps = build_default_deps()
    refs = deps.retriever.retrieve_by_text(query, k=k)
    return [r.model_dump() for r in refs]


def main() -> int:
    """Start a stdio MCP server with Person E's two tools."""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit(
            "mcp SDK is not installed. Run: pip install -r requirements/person-e-ui.txt"
        ) from e

    mcp = FastMCP("design-analysis-suite")

    @mcp.tool()
    def analyze_design(
        image_path: str | None = None,
        instructions: str | None = None,
        image_paths: list[str] | None = None,
        frame_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the full design-analysis graph on 1..5 frame(s).

        Pass either ``image_path`` (single-frame, legacy) OR
        ``image_paths`` (multi-frame). When multi-frame, attach optional
        ``frame_labels`` so the report cites screens by name rather than
        by index.
        """
        return analyze_design_tool(
            image_path=image_path,
            instructions=instructions,
            image_paths=image_paths,
            frame_labels=frame_labels,
        )

    @mcp.tool()
    def search_designs(query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search reference designs by text query."""
        return search_designs_tool(query, k)

    log.info("mcp: starting stdio server (tools: analyze_design, search_designs)")
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
