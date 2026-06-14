"""Golden test cases — 3-5 hand-curated screenshots everyone agrees on.

OWNER: shared (infra by Person A)
SPRINT CONCEPTS: Sprint 4 — Evals.

Why so few cases? At 5 LLM calls per case + a synthesizer call, even a 5-case
eval is 30 model calls. With caching we can re-run instantly on subsequent
passes, but the first pass costs money. Five hand-picked screenshots that
together exercise every code path is the right hackathon trade-off.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from src.fakes.fixtures import SAMPLE_DESIGN, ensure_sample_design


class GoldenCase(BaseModel):
    """One eval input."""

    name: str = Field(..., description="Short identifier for log lines.")
    image_path: Path
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
    # TODO(team): add 3-5 hand-picked screenshots here, one per teammate.
]
