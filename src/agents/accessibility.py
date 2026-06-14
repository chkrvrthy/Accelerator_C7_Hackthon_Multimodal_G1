"""Accessibility agent — WCAG audit -> ``AccessibilityReport``.

OWNER: Person D
SPRINT CONCEPTS:
    - Sprint 1: prompts with explicit success criteria.
    - Sprint 6: one parallel branch of the multi-agent graph.
CONSUMES: ``VisionLLM``; OPTIONAL ``opencv-python`` for deterministic contrast.
PROVIDES: ``run(state, deps) -> {"accessibility": AccessibilityReport}``.

WHY YOU CARE
------------
A11y is unique among our agents because part of the answer is computable.
Color contrast can be measured. Touch target size can be measured. We mix
that deterministic signal with LLM judgement on text legibility, state
affordances, and motion. The LLM never overrides a measured value.

LOGIC OUTLINE
-------------
1. Vision call with ``schema=AccessibilityReport`` against the candidate.
2. (Optional bonus) deterministic contrast pass with opencv that overrides
   ``contrast_pass`` with a measured boolean — beats LLM guessing.

DEFINITION OF DONE
------------------
[ ] tests/person_d/test_accessibility.py green against fake_deps.
[ ] ``make run-d-a11y`` prints a valid AccessibilityReport JSON.
[ ] Every WCAG finding cites a numeric criterion (1.4.3, 2.5.5, …).
[ ] When opencv is installed, ``contrast_pass`` is a *measured* boolean,
    not the LLM's guess. The LLM may still narrate why.
[ ] ``est_min_touch_target_px`` is set when reasonable (mobile UIs); ``None``
    is fine for desktop layouts.

DO NOT
------
- Do not let the LLM cite WCAG 1.4.3 AND 1.4.11 in the same finding. Pick
  the most specific criterion. The prompt should say so.
- Do not duplicate findings between visual and accessibility agents (the
  synthesizer dedupes, but it's noise upstream).
- Do not depend on opencv being installed — it's optional for Person D.

PROMPT-ITERATION CHECKLIST
--------------------------
1. SC numbers missing → "EVERY finding MUST cite a numeric WCAG 2.2 SC
   (e.g. 1.4.3, 2.5.5). No SC → no finding."
2. Mixing 2.1 vs 2.2 → "use WCAG 2.2 numbering only."
3. Vague evidence ("text is hard to read") → "quote the visible text verbatim
   and estimate font size in px from the image."
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.agents.base import AgentDeps, build_default_deps, run_with_schema
from src.schemas.outputs import AccessibilityReport, GraphState
from src.utils.logger import get_logger
from src.utils.prompts import accessibility_system, accessibility_user

log = get_logger(__name__)


def _srgb_channel_to_linear(channel: float) -> float:
    """Convert an sRGB channel in [0, 1] to linear light for WCAG contrast."""
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _gray_to_relative_luminance(gray_value: int) -> float:
    """Return WCAG relative luminance for a grayscale sRGB value."""
    return _srgb_channel_to_linear(gray_value / 255.0)


def _measure_contrast_pass(image_path: str) -> bool | None:
    """Measure WCAG contrast from histogram peaks; None when opencv is unavailable."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    low_gray, high_gray = sorted(int(v) for v in np.argsort(hist)[-2:])
    low_lum = _gray_to_relative_luminance(low_gray)
    high_lum = _gray_to_relative_luminance(high_gray)
    ratio = (high_lum + 0.05) / (low_lum + 0.05)
    return bool(ratio >= 4.5)


def run(state: GraphState, deps: AgentDeps) -> dict[str, AccessibilityReport]:
    """Run the Accessibility agent."""
    result = run_with_schema(
        agent_name="agent.accessibility",
        system=accessibility_system(),
        user=accessibility_user(state),
        images=[Path(state.image_path)],
        schema=AccessibilityReport,
        deps=deps,
    )
    assert isinstance(result, AccessibilityReport)

    # HINT: deterministic contrast pass (post-MVP, ~12 lines). Skip silently
    # when opencv is missing so Person C/E who don't install it aren't broken.
    #
    # TODO(person-d): override contrast_pass with a measured value:
    #   try:
    #       import cv2, numpy as np
    #   except ImportError:
    #       return {"accessibility": result}
    #   img = cv2.imread(state.image_path)
    #   if img is None: return {"accessibility": result}
    #   gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    #   # peak background luminance vs peak text luminance:
    #   hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    #   bg_l, fg_l = sorted(np.argsort(hist)[-2:])  # top 2 modes
    #   ratio = (max(bg_l, fg_l) + 0.05) / (min(bg_l, fg_l) + 0.05)
    #   result.contrast_pass = ratio >= 4.5
    measured = _measure_contrast_pass(state.image_path)
    if measured is not None:
        log.info("agent.accessibility: contrast_pass overridden by opencv (%s)", measured)
        result = result.model_copy(update={"contrast_pass": measured})

    return {"accessibility": result}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Accessibility agent (Person D)")
    parser.add_argument("--image", required=True)
    parser.add_argument("--use-real", action="store_true", default=None)
    args = parser.parse_args()

    deps = build_default_deps(use_real=args.use_real)
    state = GraphState(image_path=str(args.image))
    out = run(state, deps)
    print(json.dumps(out["accessibility"].model_dump(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
