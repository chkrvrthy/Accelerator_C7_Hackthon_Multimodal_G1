"""MCP server exposing design-analysis tools over stdio."""
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
