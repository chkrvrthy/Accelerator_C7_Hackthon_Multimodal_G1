"""Tiny self-contained colour-math helpers.

OWNER: Person A
USED BY: src.agents.tools (extract_palette, palette_distance).

These functions are extracted from ``src/agents/tools.py`` to keep that
module under the project's 500 LOC limit. They are intentionally
dependency-thin: every function is pure, deterministic, and works on
plain numpy arrays. No project-specific types cross this boundary.

WHY NOT skimage / colormath?
----------------------------
Both work, both add a heavy dependency. The math here covers our two
needs:

  1. K-means cluster a screenshot's pixel cloud in CIELab to pick a
     5-colour palette. Output: hex codes.
  2. Compare two palettes with a CIELab Delta-E proxy (Euclidean
     distance in Lab is close to perceptual difference for our use
     case; we are not doing print-shop colour grading).

For both jobs the precision of a 60-line numpy implementation is more
than enough.
"""

from __future__ import annotations

from typing import Any


def mini_kmeans(points: Any, k: int, iters: int = 8, seed: int = 0) -> tuple[Any, Any]:
    """Tiny numpy k-means. Deterministic via fixed seed.

    Returns (centers Nxk, sizes K) — same convention as scikit-learn but
    without the dependency.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    idx = rng.choice(len(points), size=k, replace=False)
    centers = points[idx].copy()
    sizes = np.zeros(k, dtype=np.int64)
    for _ in range(iters):
        d2 = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = d2.argmin(axis=1)
        for j in range(k):
            mask = labels == j
            if mask.any():
                centers[j] = points[mask].mean(axis=0)
                sizes[j] = int(mask.sum())
    return centers, sizes


def srgb_to_lab(rgb: Any) -> Any:
    """sRGB[0,1] -> CIELab. Inputs Nx3, outputs Nx3.

    Math: standard sRGB -> linear -> XYZ (D65) -> Lab path. No ICC
    profile. Accuracy is well within "looks right for k-means" — do
    NOT use for colorimetry-critical work.
    """
    import numpy as np

    def _f(c: Any) -> Any:
        return np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)

    rgb_lin = _f(rgb)
    matrix = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = rgb_lin @ matrix.T
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


def lab_to_srgb(lab: Any) -> Any:
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
    xyz = np.stack(
        [_g_inv(fx) * ref[0], _g_inv(fy) * ref[1], _g_inv(fz) * ref[2]], axis=1
    )
    matrix_inv = np.array(
        [
            [3.2404542, -1.5371385, -0.4985314],
            [-0.9692660, 1.8760108, 0.0415560],
            [0.0556434, -0.2040259, 1.0572252],
        ]
    )
    rgb_lin = xyz @ matrix_inv.T

    def _g(c: Any) -> Any:
        return np.where(c > 0.0031308, 1.055 * (c ** (1 / 2.4)) - 0.055, c * 12.92)

    return _g(rgb_lin)


def hex_to_rgb01(h: str) -> tuple[float, float, float]:
    """Hex string ('#RRGGBB' or '#RGB') -> normalized RGB tuple."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)
