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


def analyze_design_tool(image_path: str, instructions: str | None = None) -> dict[str, Any]:
    """Run the full design-analysis graph on ``image_path``."""
    log.info("mcp.analyze_design path=%s", image_path)
    report = run_graph(Path(image_path), instructions=instructions)
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
    def analyze_design(image_path: str, instructions: str | None = None) -> dict[str, Any]:
        """Run the full design-analysis graph on an uploaded image path."""
        return analyze_design_tool(image_path, instructions)

    @mcp.tool()
    def search_designs(query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search reference designs by text query."""
        return search_designs_tool(query, k)

    log.info("mcp: starting stdio server (tools: analyze_design, search_designs)")
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
