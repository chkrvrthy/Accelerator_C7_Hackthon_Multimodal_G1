"""LangChain-native tool registry.

OWNER: Person A
SPRINT CONCEPTS: Sprint 5 (tool-augmented agents), Sprint 6 (cost
optimization — measured facts beat hallucinated ones).

WHY THIS FILE EXISTS
--------------------
Two roles:

1. **Pre-tools** for our specialist agents. Run BEFORE the LLM, return
   measured ground truth, and let the agent prompt anchor on facts the
   model would otherwise have to invent. Net token saver.

2. **Basic tools** (file IO, web search) that any agent — or any
   future LangGraph routing node — can pull in via the standard
   ``model.bind_tools([...])`` API.

Implementation choice: every tool below is a `langchain_core.tools.tool`
decorated function. That makes the surface 100 % compatible with:

  * LangChain's ``ChatOpenAI(...).bind_tools([...])``
  * LangGraph's ``ToolNode``
  * LangSmith trace UI (each invocation gets its own span)

The local registry adds one piece of metadata LangChain doesn't carry
out of the box: ``owner_agent`` — so the Settings tab can render
"these are visual's tools, these are ux's, ..." for auditability.

NEVER CRASHES
-------------
Tools are best-effort. Every public tool either returns a JSON-able
dict, an empty dict, or ``None`` when its dependency is missing. None
of them raises. The agent run continues even if every tool comes back
empty — the LLM is the source of truth, the tools just make it cheaper.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agents._color_math import (
    hex_to_rgb01 as _hex_to_rgb01,
)
from src.agents._color_math import (
    lab_to_srgb as _lab_to_srgb,
)
from src.agents._color_math import (
    mini_kmeans as _mini_kmeans,
)
from src.agents._color_math import (
    srgb_to_lab as _srgb_to_lab,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


# --------------------------------------------------------------------------- #
# LangChain @tool import — lazy, so envs without langchain still import       #
# --------------------------------------------------------------------------- #
try:
    from langchain_core.tools import BaseTool, tool

    _HAS_LANGCHAIN = True
except ImportError:  # graceful: build a tiny shim so this module still loads
    _HAS_LANGCHAIN = False
    BaseTool = object  # type: ignore[assignment,misc]

    def tool(*dargs: Any, **dkw: Any) -> Any:  # type: ignore[no-redef]
        """Stand-in for langchain_core.tools.tool when langchain is missing.

        Returns the function unchanged; ``.invoke({...})`` is mimicked by
        attaching a small attribute proxy so :func:`call_tool` keeps
        working on a partial install.
        """

        def _decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            fn.name = getattr(fn, "name", fn.__name__)  # type: ignore[attr-defined]
            fn.description = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""  # type: ignore[attr-defined]

            def _invoke(payload: dict[str, Any]) -> Any:
                return fn(**payload)

            fn.invoke = _invoke  # type: ignore[attr-defined]
            return fn

        if dargs and callable(dargs[0]):  # bare @tool with no args
            return _decorate(dargs[0])
        return _decorate


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RegisteredTool:
    """A LangChain tool plus the owner-agent metadata.

    LangChain's ``BaseTool`` already carries the ``name``, ``description``
    and ``args_schema`` we need. The only thing it does not have is who
    owns the tool semantically (visual / ux / accessibility / brand /
    basic) — we add that here so the Settings tab can group by owner.
    """

    tool: Any  # BaseTool when LangChain is installed; bare function otherwise
    owner_agent: str

    @property
    def name(self) -> str:
        return getattr(self.tool, "name", "")

    @property
    def description(self) -> str:
        return getattr(self.tool, "description", "") or ""


_REGISTRY: dict[str, RegisteredTool] = {}


def register(owner_agent: str, *, alias: str | None = None) -> Callable[[Any], Any]:
    """Mark a ``@tool``-decorated function as belonging to ``owner_agent``.

    ``alias`` lets us register the SAME tool under two names — useful
    for backward compatibility (the v1 API used dotted names like
    ``visual.extract_palette``; the LangChain-native name is just
    ``extract_palette``).
    """

    def _decorate(t: Any) -> Any:
        _REGISTRY[t.name] = RegisteredTool(tool=t, owner_agent=owner_agent)
        if alias is not None:
            _REGISTRY[alias] = RegisteredTool(tool=t, owner_agent=owner_agent)
        return t

    return _decorate


def list_tools(owner_agent: str | None = None) -> list[RegisteredTool]:
    """Return every registered tool, or only those owned by ``owner_agent``.

    De-duplicates aliased entries so the Settings tab does not list the
    same tool twice.
    """
    seen: set[int] = set()
    out: list[RegisteredTool] = []
    for rt in _REGISTRY.values():
        if id(rt.tool) in seen:
            continue
        seen.add(id(rt.tool))
        if owner_agent is None or rt.owner_agent == owner_agent:
            out.append(rt)
    return sorted(out, key=lambda r: (r.owner_agent, r.name))


def list_langchain_tools(owner_agent: str | None = None) -> list[Any]:
    """Return raw ``BaseTool`` objects, e.g. for ``model.bind_tools(...)``.

    Use this when you want to hand a subset of our tools to a LangChain
    chat model so it can call them directly.
    """
    return [rt.tool for rt in list_tools(owner_agent)]


def call_tool(name: str, **kwargs: Any) -> Any:
    """Invoke a registered tool by name. Returns ``None`` on any error.

    The behavior is intentionally forgiving: if the tool is missing,
    its dependency is missing, or it raises mid-run, the call returns
    ``None`` and the caller's pipeline keeps moving. The full failure
    is logged at WARNING level.
    """
    rt = _REGISTRY.get(name)
    if rt is None:
        log.warning("call_tool: unknown tool %r", name)
        return None
    try:
        if hasattr(rt.tool, "invoke"):
            return rt.tool.invoke(kwargs)
        return rt.tool(**kwargs)
    except Exception as e:  # tools must never crash the agent run
        log.warning("call_tool(%s) failed (%s); returning None", name, e)
        return None


# --------------------------------------------------------------------------- #
# Visual agent — extract_palette                                              #
# --------------------------------------------------------------------------- #
@register(owner_agent="visual", alias="visual.extract_palette")
@tool
def extract_palette(image_path: str, k: int = 5) -> dict[str, Any] | None:
    """Extract a 3-6 colour palette from a screenshot via k-means in CIELab.

    Args:
        image_path: Path to the screenshot. Supports png / jpg / webp.
        k: Number of palette slots; clamped to 3-6.

    Returns a dict ``{"palette": ["#RRGGBB", ...], "method": "kmeans-lab",
    "k": int}`` or ``None`` when numpy / Pillow is missing.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None

    p = Path(image_path)
    if not p.exists():
        return None
    img = Image.open(p).convert("RGB")
    img.thumbnail((256, 256))
    arr = np.asarray(img).reshape(-1, 3).astype(np.float32) / 255.0
    lab = _srgb_to_lab(arr)
    centers, sizes = _mini_kmeans(lab, k=max(3, min(6, k)), iters=8)
    order = sizes.argsort()[::-1]
    centers = centers[order]
    rgb_centers = _lab_to_srgb(centers)
    rgb_centers = (rgb_centers.clip(0.0, 1.0) * 255).astype(int)
    palette = [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in rgb_centers]
    return {"palette": palette, "method": "kmeans-lab", "k": len(palette)}


# --------------------------------------------------------------------------- #
# Accessibility agent — estimate_text_size                                    #
# --------------------------------------------------------------------------- #
@register(owner_agent="accessibility", alias="accessibility.estimate_text_size")
@tool
def estimate_text_size(image_path: str) -> dict[str, Any] | None:
    """Measure smallest / median / largest text-region heights in pixels.

    Uses OpenCV adaptive-threshold + connected-components. The
    accessibility agent uses the smallest value as ground truth for
    WCAG 1.4.4 (resize text). Returns ``None`` when opencv / numpy is
    missing or the image cannot be read.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 21, 8
    )
    n, _, stats, _ = cv2.connectedComponentsWithStats(th)
    if n <= 1:
        return None
    heights = stats[1:, 3]
    plausible = heights[(heights >= 8) & (heights <= 64)]
    if plausible.size == 0:
        return None
    return {
        "smallest_text_px": int(np.percentile(plausible, 5)),
        "median_text_px": int(np.median(plausible)),
        "largest_text_px": int(np.percentile(plausible, 95)),
        "method": "opencv-cca",
    }


# --------------------------------------------------------------------------- #
# UX agent — cta_density                                                      #
# --------------------------------------------------------------------------- #
@register(owner_agent="ux", alias="ux.cta_density")
@tool
def cta_density(observations: list[str] | None = None) -> dict[str, Any] | None:
    """Count CTA-like phrases in the visual agent's observations.

    A 0-LLM heuristic: scans observations for keywords like 'cta',
    'button', 'sign up', 'start now'. Returns ``None`` when there is
    no evidence so the UX prompt is not seeded with empty noise.
    """
    if not observations:
        return None
    keywords = (
        "cta",
        "button",
        "primary action",
        "call-to-action",
        "start now",
        "sign up",
    )
    cited: list[str] = []
    for o in observations:
        ol = o.lower()
        if any(k in ol for k in keywords):
            cited.append(o[:140])
    if not cited:
        return None
    return {"cta_like_observations": len(cited), "evidence": cited[:5]}


# --------------------------------------------------------------------------- #
# Brand agent — palette_distance                                              #
# --------------------------------------------------------------------------- #
@register(owner_agent="brand", alias="brand.palette_distance")
@tool
def palette_distance(
    candidate_hex: list[str], reference_hex: list[str]
) -> dict[str, Any] | None:
    """Quantify color drift between two palettes using CIELab Delta-E.

    Verdict thresholds: < 5 imperceptible, 5-12 minor, > 12 off-brand.
    Returns ``None`` when numpy is missing or either palette is empty.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    if not candidate_hex or not reference_hex:
        return None
    cand = np.array([_hex_to_rgb01(h) for h in candidate_hex])
    ref = np.array([_hex_to_rgb01(h) for h in reference_hex])
    cand_lab = _srgb_to_lab(cand)
    ref_lab = _srgb_to_lab(ref)
    d2 = ((cand_lab[:, None, :] - ref_lab[None, :, :]) ** 2).sum(axis=2)
    nearest = np.sqrt(d2.min(axis=1))
    median = float(np.median(nearest))
    verdict = "on_brand" if median < 5 else ("minor_drift" if median < 12 else "off_brand")
    return {
        "median_delta_e": round(median, 2),
        "max_delta_e": round(float(nearest.max()), 2),
        "verdict": verdict,
    }


# --------------------------------------------------------------------------- #
# Basic tools — file IO + web search                                          #
# --------------------------------------------------------------------------- #
# These are the standard tools any agent (or any LangGraph routing
# node) can opt into. They are intentionally read-only / non-destructive
# so giving them to a model is safe even on a hostile prompt.

# Sandbox the file tools to a single root so a tool call cannot stray
# into someone's home directory. Override via FILE_TOOLS_ROOT env var.
_FILE_ROOT = Path(os.environ.get("FILE_TOOLS_ROOT", str(Path.cwd()))).resolve()


def _within_root(p: Path) -> bool:
    """True iff ``p`` is the file root or a descendant. Symlink-safe."""
    try:
        rp = p.resolve()
    except OSError:
        return False
    return rp == _FILE_ROOT or _FILE_ROOT in rp.parents


@register(owner_agent="basic")
@tool
def read_file(path: str, max_bytes: int = 100_000) -> dict[str, Any]:
    """Read a small text file from the project sandbox.

    Args:
        path: Path relative to FILE_TOOLS_ROOT (defaults to cwd).
        max_bytes: Cap on the returned content (cuts off at this size).

    Returns ``{"path": str, "content": str, "truncated": bool}`` on
    success or ``{"error": ...}`` on any failure (file missing, outside
    the sandbox, binary content). NEVER raises.
    """
    p = (_FILE_ROOT / path).resolve()
    if not _within_root(p):
        return {"error": f"path {path!r} is outside the sandbox"}
    if not p.exists() or not p.is_file():
        return {"error": f"file {path!r} not found"}
    raw = p.read_bytes()
    truncated = len(raw) > max_bytes
    if truncated:
        raw = raw[:max_bytes]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": f"file {path!r} is not utf-8 text"}
    return {"path": str(p.relative_to(_FILE_ROOT)), "content": text, "truncated": truncated}


@register(owner_agent="basic")
@tool
def list_files(directory: str = ".", glob: str = "*", max_results: int = 100) -> dict[str, Any]:
    """List files under ``directory`` matching ``glob``.

    Args:
        directory: Path relative to FILE_TOOLS_ROOT.
        glob: Glob pattern (e.g. '*.py', '**/*.md').
        max_results: Cap the returned list.

    Returns ``{"directory": str, "matches": [str, ...], "truncated": bool}``
    or ``{"error": ...}``.
    """
    root = (_FILE_ROOT / directory).resolve()
    if not _within_root(root):
        return {"error": f"directory {directory!r} is outside the sandbox"}
    if not root.exists() or not root.is_dir():
        return {"error": f"directory {directory!r} not found"}
    out: list[str] = []
    for p in root.glob(glob):
        if not _within_root(p):
            continue
        out.append(str(p.relative_to(_FILE_ROOT)))
        if len(out) >= max_results:
            return {"directory": str(root.relative_to(_FILE_ROOT)), "matches": out, "truncated": True}
    return {"directory": str(root.relative_to(_FILE_ROOT)), "matches": out, "truncated": False}


@register(owner_agent="basic")
@tool
def web_search(query: str, k: int = 5) -> dict[str, Any]:
    """Run a web search via the configured provider (Tavily preferred, DuckDuckGo fallback).

    Args:
        query: Search string.
        k: Max results.

    Returns ``{"query": str, "results": [{"title": ..., "url": ..., "snippet": ...}, ...]}``.
    Returns ``{"query": ..., "results": [], "error": ...}`` when the
    provider fails — the agent then falls back to its editorial list.
    """
    try:
        from src.tools.web_search import get_default_search

        search = get_default_search()
        if search is None:
            return {"query": query, "results": [], "error": "no provider configured"}
        hits = search.search(query, k=k)
        return {
            "query": query,
            "results": [
                {
                    "title": h.title,
                    "url": h.url,
                    "snippet": h.snippet,
                }
                for h in hits
            ],
        }
    except Exception as e:
        log.warning("web_search tool failed: %s", e)
        return {"query": query, "results": [], "error": str(e)[:200]}


def langchain_tools_summary() -> str:
    """Return a JSON string describing every registered tool.

    Useful as a one-shot "what tools do we have?" answer for an LLM
    routing node, and rendered as-is in the docs page.
    """
    return json.dumps(
        [
            {
                "name": rt.name,
                "owner_agent": rt.owner_agent,
                "description": rt.description,
            }
            for rt in list_tools()
        ],
        indent=2,
    )


# Math helpers (CIELab / k-means / hex parsing) live in
# ``src/agents/_color_math.py`` so this file stays under 500 LOC.
