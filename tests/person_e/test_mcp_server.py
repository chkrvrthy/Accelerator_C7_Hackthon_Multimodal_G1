"""MCP server — verify the two tool functions work directly.

We don't spin up a stdio server in tests; we just call the functions that
``main()`` will register. That keeps the test fast and deterministic.
"""

from __future__ import annotations

import pytest

from src.mcp.server import analyze_design_tool, search_designs_tool
from src.schemas.outputs import DesignReport

pytestmark = pytest.mark.person_e


def test_analyze_design_tool_returns_design_report_dict(sample_image):
    out = analyze_design_tool(str(sample_image), instructions="audience: India")
    rep = DesignReport.model_validate(out)
    assert rep.visual is not None and rep.brand is not None


def test_search_designs_tool_returns_dicts():
    rows = search_designs_tool("dashboard", k=2)
    assert len(rows) == 2 and all("id" in r for r in rows)
