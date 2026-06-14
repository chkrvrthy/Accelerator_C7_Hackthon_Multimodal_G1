"""Tests for per-agent pre-tools and the tool registry.

These tools are pure-Python, deterministic, and free. The contract:

  1. The registry is non-empty and tools are addressable by name.
  2. Each tool either returns a JSON-able dict OR ``None`` when its
     dependency (PIL / cv2 / numpy) is missing — never raises.
  3. Tool outputs match the agent prompt's expectations (palette is hex
     codes, text-size estimates are integers in px, brand verdict is one
     of three known strings).
"""

from __future__ import annotations

from src.agents.tools import call_tool, list_tools
from src.fakes.fixtures import ensure_sample_design


def test_registry_has_one_tool_per_specialist() -> None:
    owners = {t.owner_agent for t in list_tools()}
    assert {"visual", "accessibility", "ux", "brand"} <= owners


def test_unknown_tool_returns_none() -> None:
    assert call_tool("nope.does_not_exist") is None


def test_extract_palette_returns_hex_codes_or_none() -> None:
    img = ensure_sample_design()
    out = call_tool("visual.extract_palette", image_path=str(img))
    if out is None:
        return  # PIL/numpy not installed in the env; tool gracefully skipped
    assert "palette" in out
    assert all(p.startswith("#") and len(p) == 7 for p in out["palette"])
    assert out["method"] == "kmeans-lab"
    assert 3 <= len(out["palette"]) <= 6


def test_estimate_text_size_returns_ints_or_none() -> None:
    img = ensure_sample_design()
    out = call_tool("accessibility.estimate_text_size", image_path=str(img))
    if out is None:
        return  # cv2/numpy not installed; gracefully skipped
    for k in ("smallest_text_px", "median_text_px", "largest_text_px"):
        assert isinstance(out[k], int) and 4 <= out[k] <= 96


def test_palette_distance_verdict_is_bounded() -> None:
    out = call_tool(
        "brand.palette_distance",
        candidate_hex=["#0A2540", "#FFFFFF"],
        reference_hex=["#0A2540", "#F6F9FC"],
    )
    if out is None:
        return  # numpy not installed; gracefully skipped
    assert out["verdict"] in {"on_brand", "minor_drift", "off_brand"}
    assert isinstance(out["median_delta_e"], float)


def test_cta_density_handles_empty() -> None:
    assert call_tool("ux.cta_density", observations=None) is None
    assert call_tool("ux.cta_density", observations=[]) is None
    out = call_tool(
        "ux.cta_density",
        observations=[
            "Primary CTA: 'Start now' uses #635BFF",
            "Body copy at 16 px",
        ],
    )
    assert out is not None
    assert out["cta_like_observations"] == 1


# --------------------------------------------------------------------------- #
# Basic tools (read_file, list_files, web_search)                             #
# --------------------------------------------------------------------------- #
def test_read_file_returns_content_for_known_file() -> None:
    out = call_tool("read_file", path="pyproject.toml", max_bytes=200)
    assert "error" not in out
    assert out["path"] == "pyproject.toml"
    assert out["content"]
    assert isinstance(out["truncated"], bool)


def test_read_file_rejects_outside_sandbox() -> None:
    out = call_tool("read_file", path="../../etc/passwd")
    # Should be blocked by the sandbox check OR not found; either way no
    # /etc/passwd content leaks.
    assert "error" in out
    assert "passwd" not in out.get("content", "")


def test_list_files_returns_a_glob_match() -> None:
    out = call_tool("list_files", directory="src/agents", glob="*.py", max_results=5)
    assert "error" not in out
    assert out["matches"]
    assert all(m.endswith(".py") for m in out["matches"])
    assert all(m.startswith("src/agents") for m in out["matches"])


def test_list_files_rejects_outside_sandbox() -> None:
    out = call_tool("list_files", directory="..", glob="*")
    assert "error" in out


def test_web_search_returns_dict_with_results_key() -> None:
    # No keys configured in the test env: the tool returns
    # {"query": ..., "results": [], "error": ...} — never raises.
    out = call_tool("web_search", query="design heuristics", k=2)
    assert "query" in out
    assert "results" in out
    assert isinstance(out["results"], list)


def test_langchain_tools_are_real_basetool_instances() -> None:
    from src.agents.tools import list_langchain_tools

    tools = list_langchain_tools()
    assert tools, "no langchain tools registered"
    # Each must have the LangChain Tool surface even when langchain is
    # absent (the shim attaches .name + .invoke).
    for t in tools:
        assert getattr(t, "name", None)
        assert hasattr(t, "invoke") or callable(t)
