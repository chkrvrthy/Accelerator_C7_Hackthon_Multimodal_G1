"""GraphState — the single mutable object LangGraph hands to every node.

OWNER: Person A
SPRINT CONCEPTS: Sprint 6 — multi-agent orchestration.
CONSUMES: every other schema in ``src/schemas/outputs.py``.
PROVIDES: ``GraphState``.

Why this file exists separately from ``outputs.py``
---------------------------------------------------
``outputs.py`` is the *contract layer* — every Pydantic model an agent
returns. ``GraphState`` is the *runtime container* the orchestrator
threads through every node. Splitting along that seam keeps each file
focused (and under the project's 500-LOC limit). Existing callers
import ``GraphState`` from ``src.schemas.outputs`` unchanged; the
re-export lives in ``__init__.py`` and in ``outputs.py`` itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.outputs import (
    AccessibilityReport,
    AgentStatus,
    BrandConsistency,
    DesignReport,
    MarketResearch,
    UXCritique,
    VisualAnalysis,
)

if TYPE_CHECKING:  # pragma: no cover
    pass


class GraphState(BaseModel):
    """The single mutable object LangGraph hands to every node.

    Each agent reads what it needs and returns a *partial* dict; LangGraph
    merges that dict back into the state. The five specialist agents only
    write *their own* field, which is why parallel fan-out is safe — there
    are no write conflicts.

    HINT: the synthesizer is the only node that reads multiple agent fields.

    MULTI-IMAGE
    -----------
    ``image_paths`` is the canonical list of frames the user uploaded
    (1..N screens of the SAME product). ``image_path`` is kept as a
    convenience alias for the *primary* (first) frame — pre-tools that
    operate on a single image (k-means palette, opencv contrast, text-size
    measurement) read this. Vision agents read ``image_paths`` and send
    every frame to the multimodal LLM so cross-frame findings (drift,
    inconsistency, broken flows) are first-class.

    The two fields stay consistent automatically via ``_sync_image_paths``
    so existing callers that still pass ``image_path="x.png"`` keep working.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_path: str = Field(default="", description="Primary frame (first of image_paths).")
    image_paths: list[str] = Field(
        default_factory=list,
        description=(
            "All frames the user uploaded. 1 element = single-screen "
            "review (legacy); 2+ elements = comparison run where every "
            "vision agent sees all frames in one call."
        ),
    )
    frame_labels: list[str] = Field(
        default_factory=list,
        description=(
            "Optional human-readable labels parallel to image_paths "
            "(e.g. ['Hero', 'Pricing', 'Dashboard']). When empty the "
            "downstream agents fall back to deriving labels from "
            "filenames; when partial, missing entries are filled from "
            "filenames so the list always has the same length as "
            "image_paths by the time it reaches the agents."
        ),
    )
    image_b64: str | None = None
    instructions: str | None = None

    visual: VisualAnalysis | None = None
    ux: UXCritique | None = None
    accessibility: AccessibilityReport | None = None
    market: MarketResearch | None = None
    brand: BrandConsistency | None = None

    # Per-agent run status, populated by the orchestrator. The synthesizer
    # reads it to know which axes to downweight in the overall score.
    analysis_status: dict[str, AgentStatus] = Field(default_factory=dict)

    report: DesignReport | None = None

    @model_validator(mode="after")
    def _sync_image_paths(self) -> "GraphState":
        # LOGIC: keep image_path and image_paths consistent regardless of
        # which one the caller populated. image_paths is canonical when
        # both are set; image_path stays as the alias for the primary
        # frame so single-image pre-tools never have to know about the
        # multi-image extension.
        if not self.image_paths and self.image_path:
            self.image_paths = [self.image_path]
        elif self.image_paths and not self.image_path:
            self.image_path = self.image_paths[0]
        elif self.image_paths and self.image_path and self.image_path not in self.image_paths:
            self.image_path = self.image_paths[0]
        if not self.image_paths and not self.image_path:
            raise ValueError(
                "GraphState requires at least one image: "
                "set either image_path=... or image_paths=[...]"
            )

        # FRAME LABEL NORMALIZATION: by the time the agents see the state
        # frame_labels MUST be the same length as image_paths so every
        # downstream consumer can index without bounds checking. Missing
        # entries fall back to the filename stem of the corresponding
        # image so a recommendation that cites a frame always has a
        # human-meaningful name to cite.
        from pathlib import Path as _P

        normalized: list[str] = []
        for i, img in enumerate(self.image_paths):
            label = self.frame_labels[i].strip() if i < len(self.frame_labels) else ""
            if not label:
                label = _P(img).stem or f"Frame {i + 1}"
            normalized.append(label)
        self.frame_labels = normalized
        return self
