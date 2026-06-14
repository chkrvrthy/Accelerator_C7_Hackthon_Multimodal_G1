"""Per-agent deterministic pre-tools + a tiny tool registry.

OWNER: Person A
SPRINT CONCEPTS: Sprint 5 (tool-augmented agents), Sprint 6 (cost
optimization — measured facts beat hallucinated ones).

WHY THIS FILE EXISTS
--------------------
Most of our agents were single-shot LLM calls dressed up as agents.
A real agent has tools it can call BEFORE the LLM to ground its work
in measured facts. We do not need a full ReAct loop for v1; the simpler,
cheaper, and far more reliable pattern is **pre-tools**:

    1. Run cheap deterministic tools (PIL, opencv, numpy).
    2. Inject the measurements into the LLM's user prompt.
    3. Let the LLM enrich / interpret — but never invent — those facts.

That is a *token saver*, not a token consumer:
    - The model spends fewer output tokens speculating about colors,
      contrast, and text size — those are pasted in as ground truth.
    - The model is far less likely to hallucinate; the prompt anchors it.
    - The agent is auditable: the tool's measurement is in the trace.

The registry below is intentionally tiny: a name -> callable map. We
chose pure functions over objects because the only thing the rest of
the system needs is "what tools does agent X own?" for the Settings
tab and for documentation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger

log = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Tool:
    """One registered tool.

    Fields:
        name: stable identifier ("visual.extract_palette").
        owner_agent: the agent that uses it ("visual", "ux", ...).
        description: one-line human description for the Settings tab.
        run: the callable. Returns a JSON-able dict (or None if it could
             not run, e.g. dependency missing).
    """

    name: str
    owner_agent: str
    description: str
    run: Callable[..., dict[str, Any] | None]


_REGISTRY: dict[str, Tool] = {}


def register_tool(
    *,
    name: str,
    owner_agent: str,
    description: str,
) -> Callable[[Callable[..., dict[str, Any] | None]], Callable[..., dict[str, Any] | None]]:
    """Decorator: register a tool by name.

    Usage::

        @register_tool(name="visual.extract_palette",
                       owner_agent="visual",
                       description="K-means palette in CIELab")
        def extract_palette(image_path: str, k: int = 5) -> dict | None:
            ...
    """

    def _decorate(fn: Callable[..., dict[str, Any] | None]) -> Callable[..., dict[str, Any] | None]:
        _REGISTRY[name] = Tool(name=name, owner_agent=owner_agent, description=description, run=fn)
        return fn

    return _decorate


def list_tools(owner_agent: str | None = None) -> list[Tool]:
    """Return all registered tools, or only those owned by ``owner_agent``."""
    if owner_agent is None:
        return list(_REGISTRY.values())
    return [t for t in _REGISTRY.values() if t.owner_agent == owner_agent]


def call_tool(name: str, **kwargs: Any) -> dict[str, Any] | None:
    """Invoke a registered tool. Returns None on missing tool or runtime error."""
    tool = _REGISTRY.get(name)
    if tool is None:
        log.warning("tools.call_tool: unknown tool %r", name)
        return None
    try:
        return tool.run(**kwargs)
    except Exception as e:  # tools must never crash the agent run
        log.warning("tools.%s failed (%s); proceeding without measurement", name, e)
        return None


# --------------------------------------------------------------------------- #
# VISUAL agent tools                                                          #
# --------------------------------------------------------------------------- #
@register_tool(
    name="visual.extract_palette",
    owner_agent="visual",
    description="Extract a 3-6 colour palette from a screenshot via k-means in CIELab.",
)
def extract_palette(image_path: str | Path, k: int = 5) -> dict[str, Any] | None:
    """Return a deterministic top-k palette as a list of hex codes.

    Strategy:
      1. Read with PIL, resize to ~256 px max for speed.
      2. Convert to CIELab (perceptually uniform; clusters look right).
      3. K-means cluster the pixels, take centroid colors.
      4. Sort by cluster size (largest first), return hex codes.

    Returns:
        ``{"palette": ["#RRGGBB", ...], "method": "kmeans-lab"}`` or None
        when PIL / numpy is missing (we accept the cost: the LLM picks
        colors itself in that branch).
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

    # Convert sRGB -> CIELab via the simple matrix path (no skimage dep).
    # The math is not pixel-perfect against ICC profiles, but for picking
    # a 5-colour design palette it is more than enough.
    lab = _srgb_to_lab(arr)

    centers, sizes = _mini_kmeans(lab, k=max(3, min(6, k)), iters=8)
    order = sizes.argsort()[::-1]
    centers = centers[order]
    rgb_centers = _lab_to_srgb(centers)
    rgb_centers = (rgb_centers.clip(0.0, 1.0) * 255).astype(int)
    palette = [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in rgb_centers]
    return {"palette": palette, "method": "kmeans-lab", "k": len(palette)}


def _mini_kmeans(points: Any, k: int, iters: int = 8, seed: int = 0) -> tuple[Any, Any]:
    """Tiny numpy k-means. Deterministic via fixed seed."""
    import numpy as np

    rng = np.random.default_rng(seed)
    idx = rng.choice(len(points), size=k, replace=False)
    centers = points[idx].copy()
    sizes = np.zeros(k, dtype=np.int64)
    for _ in range(iters):
        # assign
        d2 = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = d2.argmin(axis=1)
        # update
        for j in range(k):
            mask = labels == j
            if mask.any():
                centers[j] = points[mask].mean(axis=0)
                sizes[j] = int(mask.sum())
    return centers, sizes


def _srgb_to_lab(rgb: Any) -> Any:
    """sRGB[0,1] -> CIELab. Inputs Nx3, outputs Nx3."""
    import numpy as np

    def _f(c: Any) -> Any:
        return np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)

    rgb_lin = _f(rgb)
    M = np.array(  # noqa: N806 — sRGB → XYZ transform matrix (linear-algebra convention)
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = rgb_lin @ M.T
    # Normalise by D65 reference white
    ref = np.array([0.95047, 1.00000, 1.08883])
    xyz_n = xyz / ref
    eps = 6.0 / 29.0

    def _g(t: Any) -> Any:
        return np.where(t > eps**3, np.cbrt(t), (t / (3 * eps**2)) + 4 / 29)

    f = _g(xyz_n)
    L = 116 * f[:, 1] - 16  # noqa: N806 — CIELab convention (L*a*b*)
    a = 500 * (f[:, 0] - f[:, 1])
    b = 200 * (f[:, 1] - f[:, 2])
    return np.stack([L, a, b], axis=1)


def _lab_to_srgb(lab: Any) -> Any:
    """CIELab -> sRGB[0,1]. Inputs Nx3."""
    import numpy as np

    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]  # noqa: N806 — CIELab convention
    fy = (L + 16) / 116
    fx = a / 500 + fy
    fz = fy - b / 200

    def _g_inv(t: Any) -> Any:
        eps = 6.0 / 29.0
        return np.where(t > eps, t**3, 3 * eps**2 * (t - 4 / 29))

    ref = np.array([0.95047, 1.00000, 1.08883])
    xyz = np.stack([_g_inv(fx) * ref[0], _g_inv(fy) * ref[1], _g_inv(fz) * ref[2]], axis=1)
    M_inv = np.array(  # noqa: N806 — XYZ → sRGB inverse transform
        [
            [3.2404542, -1.5371385, -0.4985314],
            [-0.9692660, 1.8760108, 0.0415560],
            [0.0556434, -0.2040259, 1.0572252],
        ]
    )
    rgb_lin = xyz @ M_inv.T

    def _g(c: Any) -> Any:
        return np.where(c > 0.0031308, 1.055 * (c ** (1 / 2.4)) - 0.055, c * 12.92)

    return _g(rgb_lin)


# --------------------------------------------------------------------------- #
# ACCESSIBILITY agent tools                                                   #
# --------------------------------------------------------------------------- #
@register_tool(
    name="accessibility.estimate_text_size",
    owner_agent="accessibility",
    description="Estimate the smallest visible text region in pixels via OpenCV connected components.",
)
def estimate_text_size(image_path: str | Path) -> dict[str, Any] | None:
    """Return a coarse "smallest text region in px" estimate.

    Useful as ground truth for the accessibility LLM:
        "We measured the smallest text region at ~12 px tall. Combined
         with the LLM's reading of the screenshot, this lets the agent
         make a confident call on WCAG 1.4.4 (text resize)."

    Returns None when opencv or numpy is unavailable.
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
    # Adaptive threshold pulls out text-like high-contrast strokes.
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 21, 8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(th)
    if n <= 1:
        return None
    # stats[:, 3] is height (cv2.CC_STAT_HEIGHT). Filter out single-pixel
    # noise and giant blocks (cards, bars), keep mid-range "text" heights.
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
# UX agent tools                                                              #
# --------------------------------------------------------------------------- #
@register_tool(
    name="ux.cta_density",
    owner_agent="ux",
    description="Estimate above-the-fold CTA count from the visual agent's observations (no LLM call).",
)
def cta_density(observations: list[str] | None) -> dict[str, Any] | None:
    """Crude but useful pre-tool: count CTA-like words in observations.

    The visual agent already reports observations like:
        "Primary button uses #635BFF, ~64px height"
        "Two competing CTAs above the fold: 'Start now', 'Talk to sales'"

    We pattern-match for CTA / button / action keywords. The result
    feeds the UX prompt as: "We counted N CTA-like elements; analyse
    whether that competes for attention."
    """
    if not observations:
        return None
    keywords = ("cta", "button", "primary action", "call-to-action", "start now", "sign up")
    count = 0
    cited: list[str] = []
    for o in observations:
        ol = o.lower()
        if any(k in ol for k in keywords):
            count += 1
            cited.append(o[:140])
    if not cited:
        return None
    return {"cta_like_observations": count, "evidence": cited[:5]}


# --------------------------------------------------------------------------- #
# BRAND agent tools                                                           #
# --------------------------------------------------------------------------- #
@register_tool(
    name="brand.palette_distance",
    owner_agent="brand",
    description="Median CIELab distance between candidate palette and reference palette.",
)
def palette_distance(candidate_hex: list[str], reference_hex: list[str]) -> dict[str, Any] | None:
    """Quantify color drift in CIELab Delta-E.

    < 5  : imperceptible (same brand)
    5-12 : noticeable but cohesive
    > 12 : visible drift, brand off-key

    Returns None when numpy is missing.
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

    # Pairwise distances; take min for each candidate to its closest ref,
    # then median across candidates. Stable, simple, interpretable.
    d2 = ((cand_lab[:, None, :] - ref_lab[None, :, :]) ** 2).sum(axis=2)
    nearest = np.sqrt(d2.min(axis=1))
    median = float(np.median(nearest))
    if median < 5:
        verdict = "on_brand"
    elif median < 12:
        verdict = "minor_drift"
    else:
        verdict = "off_brand"
    return {
        "median_delta_e": round(median, 2),
        "max_delta_e": round(float(nearest.max()), 2),
        "verdict": verdict,
    }


def _hex_to_rgb01(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)
