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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    RESILIENCE: only ``title`` is truly required. ``description``, ``evidence``
    and ``recommendation`` default to "" and are cross-filled by
    ``_backfill_text`` so a single omitted field from the LLM never crashes
    the entire pipeline. ``severity`` defaults to ``MEDIUM``. The prompt is
    still the enforcement mechanism for *quality*; this schema is the
    enforcement mechanism for *shape*. We keep the contract surface stable
    even when the model occasionally folds two fields into one.
    """

    title: str = Field(..., description="Short, action-oriented headline.")
    description: str = Field(default="", description="One paragraph, plain English.")
    severity: Severity = Severity.MEDIUM
    evidence: str = Field(
        default="", description="What the agent saw — quote the screen."
    )
    recommendation: str = Field(
        default="", description="A concrete, one-sentence fix."
    )

    @model_validator(mode="after")
    def _backfill_text(self) -> "Finding":
        # LOGIC: when the LLM omits one of the optional text fields we'd
        # rather render a useful card than a blank one. Cross-fill from the
        # most-related sibling. Order chosen so the user's reading flow
        # (description -> evidence -> recommendation) makes sense even when
        # everything collapses to a single sentence.
        if not self.description.strip():
            self.description = self.evidence or self.recommendation or self.title
        if not self.evidence.strip():
            self.evidence = self.description or self.title
        if not self.recommendation.strip():
            self.recommendation = self.title
        return self


# TODO(person-d): require a WCAG 2.2 success-criterion number on every
#                 accessibility finding (e.g. 1.4.3). Implemented as WCAGFinding.
class WCAGFinding(Finding):
    """Accessibility finding with a best-effort WCAG 2.2 success-criterion citation.

    RESILIENCE: ``criterion`` defaults to "" and any non-numeric value
    ("contrast", "AA fail", "1.4") is silently coerced to "" so an LLM
    quirk on one finding never breaks the run. Prompt remains the
    enforcement mechanism — the UI badges blank citations as "uncited" so
    reviewers still notice when the model skipped a citation.
    """

    criterion: str = Field(
        default="",
        description="WCAG 2.2 SC number, e.g. '1.4.3'.",
    )

    @field_validator("criterion")
    @classmethod
    def _criterion_format(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or not re.match(r"^\d+\.\d+\.\d+$", v):
            return ""
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
    matched_frames: list[str] = Field(
        default_factory=list,
        description=(
            "Frame labels (from GraphState.frame_labels) whose query "
            "image surfaced this reference in the top-k. Empty for "
            "single-frame runs and for legacy callers that don't pass "
            "frame context. The brand agent uses this to attribute "
            "drift findings to specific screens (e.g. 'Pricing matched "
            "Stripe-pricing-2024 with score 0.83')."
        ),
    )
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
    """One actionable, ranked, evidence-backed recommendation.

    Why every field exists:
    - ``priority`` is the synthesizer's intent. Without it, render order
      betrays the user (the LLM emits in *reasoning* order, not *action*
      order). Defaults to 999 when the LLM omits it; the report-level
      validator renumbers densely 1..N.
    - ``metric_lift`` is what an executive reads first.
    - ``proof`` keeps the synthesizer honest — it must cite the specialist
      and the finding it derived from. Without proof we are guessing.
    - ``affected_frames`` is the multi-frame attribution. For multi-frame
      runs the synthesizer MUST populate it with the frame label(s) the
      finding applies to (e.g. ``["Pricing", "Checkout"]``). For
      single-frame runs it stays empty — the one frame is implied.

    RESILIENCE: only ``title`` is truly required. Every other field has a
    sensible default so an LLM that omits one piece of metadata never
    breaks the whole report.
    """

    priority: int = Field(default=999, ge=1, description="1 is highest. Renumbered densely 1..N.")
    title: str = Field(..., description="Imperative, target value when measurable.")
    rationale: str = Field(default="", description="One sentence with WHO flagged it AND WHY.")
    effort: Literal["S", "M", "L"] = "M"
    impact: Literal["S", "M", "L"] = "M"
    metric_lift: str | None = Field(
        default=None,
        description="Plain-English expected lift, e.g. '+8% sign-up conversion'.",
    )
    proof: str | None = Field(
        default=None,
        description="Citation: '<agent>:<field>'. Example: 'accessibility:1.4.3'.",
    )
    affected_frames: list[str] = Field(
        default_factory=list,
        description=(
            "Frame labels (e.g. 'Hero', 'Pricing') the finding applies to. "
            "Required for multi-frame runs; empty for single-frame. The UI "
            "renders these as badges so a reviewer can see which screens "
            "are affected at a glance."
        ),
    )

    @model_validator(mode="after")
    def _backfill_rationale(self) -> "Recommendation":
        # LOGIC: a recommendation without a rationale is a slogan. Fall back
        # to the title so the UI never renders a blank "why" column.
        if not self.rationale.strip():
            self.rationale = self.title
        return self


AgentStatus = Literal["ok", "partial", "failed", "skipped"]


class DesignReport(BaseModel):
    """The final synthesized output — one report per click of "Run".

    Adds an executive header (score + WHY + per-axis breakdown) and a
    runtime panel (per-agent status, run_id, timestamp) on top of the
    five specialist outputs. Designed to read like a billion-dollar
    product report, not a debug dump.
    """

    # --- executive header ---------------------------------------------- #
    executive_summary: str = Field(
        default="",
        description=(
            "60-100 word narrative paragraph that opens the report. Reads "
            "like a senior designer's memo: the headline finding, the "
            "single biggest opportunity, and the one action to ship first. "
            "This is the prose the user will paste into a ticket."
        ),
    )
    overall_score: Score = Field(default=0.0)
    score_rationale: str = Field(
        default="",
        description=(
            "One paragraph (40-80 words) explaining WHY the score is what "
            "it is. Required when overall_score>0."
        ),
    )
    score_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-axis 0-100 sub-scores keyed by 'visual', 'ux', "
            "'accessibility', 'brand', 'market'. Used by UI for breakdown bars."
        ),
    )

    # --- prioritized actions ------------------------------------------- #
    top_strengths: list[str] = Field(default_factory=list)
    top_recommendations: list[Recommendation] = Field(default_factory=list)

    # --- runtime panel ------------------------------------------------- #
    run_id: str = Field(default="", description="Short hex id, unique per run.")
    analyzed_at: str = Field(default="", description="ISO 8601 UTC timestamp.")
    analysis_status: dict[str, AgentStatus] = Field(
        default_factory=dict,
        description=(
            "Per-agent run status: 'ok' / 'partial' / 'failed' / 'skipped'. "
            "Lets the UI show 'Visual unavailable' instead of crashing."
        ),
    )

    # --- multi-frame attribution -------------------------------------- #
    frame_labels: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered labels for every frame this report covers (e.g. "
            "['Hero', 'Pricing', 'Dashboard']). Empty for single-frame "
            "runs. Used by the UI to render thumbnail strips and to "
            "validate Recommendation.affected_frames against."
        ),
    )
    per_frame_scores: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description=(
            "Per-frame sub-scores keyed by frame label, then by axis. "
            "Each inner dict has at most these keys: 'overall', 'visual', "
            "'ux', 'accessibility', 'brand', 'market', each clamped 0-100. "
            "Empty for single-frame runs. Lets the UI render 'Pricing is "
            "the weak link' style heatmaps."
        ),
    )

    # --- specialist payloads ------------------------------------------- #
    visual: VisualAnalysis | None = None
    ux: UXCritique | None = None
    accessibility: AccessibilityReport | None = None
    market: MarketResearch | None = None
    brand: BrandConsistency | None = None

    @field_validator("top_recommendations")
    @classmethod
    def _sort_and_validate_priorities(cls, v: list[Recommendation]) -> list[Recommendation]:
        # LOGIC: sort by the LLM-emitted priority asc (with stable order on
        # ties), then renumber DENSELY 1..N. We deliberately do NOT dedupe
        # by priority value — when the LLM omits priority entirely every
        # recommendation defaults to 999, and dropping duplicates would
        # silently kill all but one. Stable renumbering preserves the
        # model's emit order as the tiebreaker, which is the closest proxy
        # we have to "intended ranking" when explicit priorities are
        # missing.
        if not v:
            return v
        sorted_v = sorted(v, key=lambda x: x.priority)
        for i, r in enumerate(sorted_v, start=1):
            r.priority = i
        return sorted_v

    @field_validator("score_breakdown")
    @classmethod
    def _clamp_breakdown(cls, v: dict[str, float]) -> dict[str, float]:
        return {k: max(0.0, min(100.0, float(score))) for k, score in v.items()}

    @field_validator("per_frame_scores")
    @classmethod
    def _clamp_per_frame_scores(
        cls, v: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        # LOGIC: same clamp as score_breakdown but applied to each inner
        # dict. We do not enforce keys — the LLM may emit only "overall"
        # for some frames, or all six axes for others; the UI tolerates
        # either shape. We DO clamp every value to 0-100 so a stray
        # negative or 150 from the model never paints a broken bar.
        out: dict[str, dict[str, float]] = {}
        for frame_label, axes in v.items():
            if not isinstance(axes, dict):
                continue
            out[frame_label] = {
                k: max(0.0, min(100.0, float(s))) for k, s in axes.items()
            }
        return out


# --------------------------------------------------------------------------- #
# LangGraph state                                                              #
# --------------------------------------------------------------------------- #


# GraphState (the runtime container LangGraph threads through every node)
# lives in src/schemas/state.py to keep this file under the project's
# 500-LOC budget. We re-export it here so existing imports
# ``from src.schemas.outputs import GraphState`` keep working unchanged.
from src.schemas.state import GraphState  # noqa: E402,F401  (re-export)
