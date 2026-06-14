"""Single source of truth for every typed object that crosses a module boundary.

OWNER: Person A (reviewed by everyone — these schemas are the API contract)
SPRINT CONCEPTS:
    - Sprint 1: Pydantic + JSON-schema prompting. Every agent's output schema
      is serialized via ``model_json_schema()`` and passed to OpenRouter as
      ``response_format={"type":"json_schema", ...}``. The model is forced to
      return exactly this shape; we re-validate on receipt to catch drift.
    - Sprint 6: Structured aggregated output. ``DesignReport`` is the final
      shape the synthesizer agent produces.

CONSUMES: nothing (schemas only depend on pydantic).
PROVIDES: every Pydantic model in the system.

LOGIC OUTLINE
-------------
1. Primitives: ``Severity`` enum, ``Finding`` row.
2. Per-agent outputs: VisualAnalysis, UXCritique, AccessibilityReport,
   MarketResearch, BrandConsistency.
3. Cross-cutting types: RetrievedRef (RAG), SearchResult (web), Recommendation.
4. Aggregate: DesignReport (synthesizer output).
5. State: GraphState (LangGraph carries this through every node).

TEACHING NOTES (mentor's voice)
-------------------------------
We keep schemas dumb on purpose. No methods, no business logic. If you need
behavior, write a function next to the consumer. This pattern matters because:

  a) JSON-schema mode wants a *shape*, not a class hierarchy. Pydantic v2 emits
     a clean schema only when the model is plain data.
  b) Two agents can be edited in parallel without merge conflicts so long as
     they touch their *own* output class. The schema is the seam.
  c) When a judge asks "where is the structured output?", you point at this
     file. One file. One answer.

HINTS
-----
- ``model_config = ConfigDict(extra="forbid")`` makes hallucinated fields fail
  fast — turn it on once your prompts are stable.
- Use ``Annotated[float, Field(ge=0, le=100)]`` for scores so validation is
  inline rather than in a separate validator.
- Every list field gets ``default_factory=list`` so a partial state still
  validates while agents are still running.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A palette entry must be a hex color: "#RGB" or "#RRGGBB". Color names like
# "navy" are dropped so downstream consumers (UI swatches) never choke.
_HEX_COLOR = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")

# --------------------------------------------------------------------------- #
# Type aliases                                                                #
# --------------------------------------------------------------------------- #

# A score is always a 0..100 float. Centralize the constraint so every agent
# uses the same range and we never argue about scales again.
Score = Annotated[float, Field(ge=0.0, le=100.0)]


class Severity(str, Enum):
    """How bad a finding is. The prompt rubric must reference these names verbatim."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --------------------------------------------------------------------------- #
# Building blocks                                                              #
# --------------------------------------------------------------------------- #


class Finding(BaseModel):
    """One observed issue with severity, evidence and a fix.

    Used by the UX, accessibility and brand agents. Keeping all "bad thing
    spotted" outputs in a single shape lets the UI and synthesizer treat them
    uniformly (sort by severity, group by agent, etc).
    """

    title: str = Field(..., description="Short, action-oriented headline.")
    description: str = Field(..., description="One paragraph, plain English.")
    severity: Severity
    evidence: str = Field(..., description="What the agent saw — quote the screen.")
    recommendation: str = Field(..., description="A concrete, one-sentence fix.")


# TODO(person-d): require a WCAG 2.2 success-criterion number on every
#                 accessibility finding (e.g. 1.4.3). Implemented as WCAGFinding.
class WCAGFinding(Finding):
    """Accessibility finding with a required WCAG 2.2 success-criterion citation."""

    criterion: str = Field(
        ...,
        description="WCAG 2.2 SC number, e.g. '1.4.3'.",
    )

    @field_validator("criterion")
    @classmethod
    def _criterion_format(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError(f"WCAG criterion must look like '1.4.3', got {v!r}")
        return v


# --------------------------------------------------------------------------- #
# Per-agent outputs                                                            #
# --------------------------------------------------------------------------- #


class VisualAnalysis(BaseModel):
    """Person C — Visual Analysis Agent output."""

    layout: str = Field(default="", description="High-level layout description.")
    hierarchy: str = Field(default="", description="Information hierarchy commentary.")
    palette: list[str] = Field(default_factory=list, description="Hex colors, e.g. '#0A2540'.")
    typography: str = Field(default="", description="Font families and weight notes.")
    spacing_notes: str = Field(default="")
    density_score: Score = Field(default=0.0, description="0=very sparse, 100=very dense.")
    observations: list[str] = Field(default_factory=list)

    @field_validator("palette")
    @classmethod
    def _strip_blanks(cls, v: list[str]) -> list[str]:
        # LOGIC: keep only valid hex colors ("#RGB" / "#RRGGBB"). This drops
        # the empty strings the LLM emits for "unknown" AND hallucinated color
        # names like "navy". We FILTER rather than raise so a single bad color
        # never fails validation and breaks the whole graph (prompt iteration,
        # not a runtime exception, is where hex discipline is enforced).
        return [c.strip() for c in v if c and _HEX_COLOR.match(c.strip())]


class UXCritique(BaseModel):
    """Person D — UX Critique Agent output (Nielsen-heuristic style)."""

    heuristic_violations: list[Finding] = Field(default_factory=list)
    cognitive_load_score: Score = Field(default=0.0)
    friction_points: list[Finding] = Field(default_factory=list)


class AccessibilityReport(BaseModel):
    """Person D — Accessibility Agent output (WCAG 2.2)."""

    wcag_findings: list[WCAGFinding] = Field(default_factory=list)
    # contrast_pass is None when the LLM was unsure and no opencv pass ran.
    contrast_pass: bool | None = None
    est_min_touch_target_px: int | None = Field(
        default=None, description="Smallest tappable element height in px (estimate)."
    )


class CompetitorRef(BaseModel):
    """One competitor identified by the market agent."""

    name: str
    url: str
    why_relevant: str


class MarketResearch(BaseModel):
    """Person E — Market Research Agent output."""

    competitors: list[CompetitorRef] = Field(default_factory=list)
    trends: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list, description="URLs cited by the LLM.")


class RetrievedRef(BaseModel):
    """One reference design pulled from the RAG corpus.

    Person B's ``Retriever`` returns these. Person C's brand agent consumes
    them. The UI may display the thumbnail.
    """

    id: str
    score: float = Field(..., description="Similarity in [0, 1]. Higher is closer.")
    image_path: str = Field(..., description="Relative to data/reference for portability.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrandConsistency(BaseModel):
    """Person C — Brand Consistency Agent output."""

    consistency_score: Score = Field(default=0.0)
    color_drift: str = Field(default="")
    type_drift: str = Field(default="")
    component_drift: str = Field(default="")
    comparable_refs: list[RetrievedRef] = Field(default_factory=list)


class SearchResult(BaseModel):
    """One web hit returned by the WebSearch protocol."""

    title: str
    url: str
    snippet: str


# --------------------------------------------------------------------------- #
# Synthesizer & report                                                         #
# --------------------------------------------------------------------------- #


class Recommendation(BaseModel):
    """One actionable recommendation in the final report."""

    title: str
    rationale: str
    effort: Literal["S", "M", "L"]
    impact: Literal["S", "M", "L"]


class DesignReport(BaseModel):
    """The final synthesized output — one report per click of "Run".

    Aggregates every specialist's typed output plus an executive layer
    (``overall_score``, ``top_strengths``, ``top_recommendations``).
    """

    overall_score: Score = Field(default=0.0)
    top_strengths: list[str] = Field(default_factory=list)
    top_recommendations: list[Recommendation] = Field(default_factory=list)

    visual: VisualAnalysis | None = None
    ux: UXCritique | None = None
    accessibility: AccessibilityReport | None = None
    market: MarketResearch | None = None
    brand: BrandConsistency | None = None


# --------------------------------------------------------------------------- #
# LangGraph state                                                              #
# --------------------------------------------------------------------------- #


class GraphState(BaseModel):
    """The single mutable object LangGraph hands to every node.

    Each agent reads what it needs and returns a *partial* dict; LangGraph
    merges that dict back into the state. The five specialist agents only
    write *their own* field, which is why parallel fan-out is safe — there
    are no write conflicts.

    HINT: the synthesizer is the only node that reads multiple agent fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_path: str
    image_b64: str | None = None
    instructions: str | None = None

    visual: VisualAnalysis | None = None
    ux: UXCritique | None = None
    accessibility: AccessibilityReport | None = None
    market: MarketResearch | None = None
    brand: BrandConsistency | None = None

    report: DesignReport | None = None
