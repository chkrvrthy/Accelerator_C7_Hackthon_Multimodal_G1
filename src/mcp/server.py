"""MCP server — expose ``analyze_design`` and ``search_designs`` over stdio.

OWNER: Person E
SPRINT CONCEPTS:
    - Sprint 4: MCP (Model Context Protocol).
CONSUMES: ``mcp`` Python SDK, ``run_graph``, ``LanceRetriever``.
PROVIDES: stdio MCP server with two tools, ~80 lines.

WHY YOU CARE
------------
MCP is a wire-protocol standard that lets an *external* LLM agent (Claude
Code, or any other MCP-compatible client) call our tools as if they were
native. This is the "agentic interoperability" demo. Watch the eyebrows
go up when you call ``analyze_design`` from a coding-agent chat panel and
the same DesignReport that the Gradio UI showed appears inline in their
chat.

WHY ONLY TWO TOOLS
------------------
Hackathon scope. ``ingest_reference`` would be a clean third tool — listed
as a post-MVP extension in the plan.

DEFINITION OF DONE
------------------
[ ] tests/person_e/test_mcp_server.py passes (calls the tool functions
    directly, no stdio loop required).
[ ] ``python -m src.mcp.server`` starts and lists both tools when probed
    by ``mcp-cli list-tools`` or any MCP client's tool-discovery view.
[ ] ``analyze_design`` round-trips a real screenshot to a DesignReport
    over stdio (test from any MCP-compatible client — that is the demo moment).
[ ] ``search_designs`` returns serialized RetrievedRef list.
[ ] All loguru / stdlib logs go to stderr — stdout is *only* MCP JSON-RPC.
[ ] README ships an ``mcp.json`` snippet.

DO NOT
------
- Do not print() inside the tool functions. stdout is reserved for MCP.
  Use ``log.info(...)`` — the project logger writes to stderr.
- Do not call run_graph with ``USE_REAL=0`` in production. The demo
  expects real model output here.
- Do not register a third tool until the first two are bullet-proof.
- Do not block on long graph runs without yielding progress events to MCP;
  most MCP clients time out at ~60 s.

`mcp.json` SNIPPET (paste into your MCP client's config — typical paths
are ``~/.config/claude-code/mcp.json`` or whatever the client documents)
----------------------------------------------------------------------
    {
      "design-analysis-suite": {
        "command": "python",
        "args": ["-m", "src.mcp.server"],
        "cwd": "/abs/path/to/ai_c7_hackathon",
        "env": {
          "OPENROUTER_API_KEY": "sk-or-v1-...",
          "USE_REAL": "1"
        }
      }
    }
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.graph import run_graph
from src.utils.logger import get_logger

log = get_logger(__name__)


def analyze_design_tool(image_path: str, instructions: str | None = None) -> dict[str, Any]:
    """Tool: run the full design-analysis graph on ``image_path``.

    Returns a serialized ``DesignReport`` dict. Logs go to stderr.
    """
    # NOTE: this function is the seam between MCP transport and our graph.
    # Keep it pure — no MCP types here so unit tests can call it directly.
    log.info("mcp.analyze_design path=%s", image_path)
    report = run_graph(Path(image_path), instructions=instructions)
    return report.model_dump()


def search_designs_tool(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Tool: search the reference corpus by text query.

    Returns a list of ``RetrievedRef`` dicts.
    """
    # HINT: build deps once at module level once you wire main(); for now
    # we use the default factory which honors USE_REAL.
    from src.agents.base import build_default_deps
    deps = build_default_deps()
    refs = deps.retriever.retrieve_by_text(query, k=k)
    return [r.model_dump() for r in refs]


def main() -> int:
    """Start a stdio MCP server with the two tools above."""
    try:
        from mcp.server import Server  # type: ignore[import-not-found]
        from mcp.server.stdio import stdio_server  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit(
            "mcp SDK is not installed. Run: pip install -r requirements/person-e-ui.txt"
        )

    server = Server("design-analysis-suite")

    # HINT: tool registration recipe (the SDK API has shifted across versions;
    # check the installed mcp version's README before pasting):
    #
    #   @server.tool(name="analyze_design",
    #                description="Run the full design-analysis graph on an uploaded image.")
    #   async def _analyze_design(image_path: str, instructions: str | None = None) -> dict:
    #       return analyze_design_tool(image_path, instructions)
    #
    #   @server.tool(name="search_designs",
    #                description="Search the reference design corpus by text query.")
    #   async def _search_designs(query: str, k: int = 5) -> list[dict]:
    #       return search_designs_tool(query, k)
    #
    # HINT: stdio loop (~5 lines):
    #   import asyncio
    #   async def _run():
    #       async with stdio_server() as (reader, writer):
    #           await server.run(reader, writer, server.create_initialization_options())
    #   asyncio.run(_run())
    #
    # NOTE: route logs to STDERR (the project logger already does this).
    # If you accidentally print to stdout, MCP clients will choke on the
    # invalid JSON-RPC frame.

    log.info("mcp: starting stdio server (tools: analyze_design, search_designs)")
    # TODO(person-e): wire the @server.tool decorators above and start
    # the stdio server. Tested by `python -m src.mcp.server` listing
    # both tools when probed.
    raise NotImplementedError("Person E: wire mcp.Server.tool() and stdio_server().")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
