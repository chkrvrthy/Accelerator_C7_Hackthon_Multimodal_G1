"""Golden test cases — 3-5 hand-curated screenshots everyone agrees on.

OWNER: shared (infra by Person A)
SPRINT CONCEPTS: Sprint 4 — Evals.

Why so few cases? At 5 LLM calls per case + a synthesizer call, even a 5-case
eval is 30 model calls. With caching we can re-run instantly on subsequent
passes, but the first pass costs money. Five hand-picked screenshots that
together exercise every code path is the right hackathon trade-off.

MULTI-FRAME EVAL
----------------
At least one case should be multi-frame so the eval harness exercises
the multi-image code path (per_frame_scores, affected_frames, frame
labels). With fakes the cost is zero; with real APIs the harness is
opt-in via OPENROUTER_API_KEY anyway.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from src.fakes.fixtures import SAMPLE_DESIGN, ensure_sample_design


class GoldenCase(BaseModel):
    """One eval input.

    For single-frame cases set ``image_path``; the harness threads that
    through ``run_graph`` directly. For multi-frame cases set
    ``image_paths`` (and optionally ``frame_labels``); ``image_path``
    is then ignored. We deliberately keep both fields so existing
    cases stay valid and new cases can opt in without a migration.
    """

    name: str = Field(..., description="Short identifier for log lines.")
    image_path: Path | None = None
    image_paths: list[Path] = Field(default_factory=list)
    frame_labels: list[str] = Field(default_factory=list)
    instructions: str | None = None


# LOGIC: We seed the list with the bundled sample so a fresh clone can run
# `make eval` without any reference designs. Replace these with real
# screenshots before the demo (one per teammate).
ensure_sample_design()
GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        name="bundled-sample",
        image_path=SAMPLE_DESIGN,
        instructions="audience is retail banking customers in India",
    ),
    GoldenCase(
        # Multi-frame smoke case — re-uses the bundled sample 3x to
        # exercise the per_frame_scores / affected_frames code paths
        # against fakes for free. With real APIs this becomes the
        # canonical "comparison-mode" eval; replace the paths with
        # three real screens of one product before the demo.
        name="bundled-sample-multi-frame",
        image_paths=[SAMPLE_DESIGN, SAMPLE_DESIGN, SAMPLE_DESIGN],
        frame_labels=["Hero", "Pricing", "Dashboard"],
        instructions="audience is enterprise IT; brand is technical",
    ),
    # TODO(team): add 3-5 hand-picked screenshots here, one per teammate.
]
