"""Deterministic LLM doubles satisfying ``LLMClient`` and ``VisionLLM``.

OWNER: Person A

Why these matter
----------------
Without a fake LLM, every test would need an API key and would burn money on
every CI run. With a fake LLM:

    * Test runs are < 1 s.
    * Same canned output every time → assertions can compare exact values.
    * Person C/D/E can ship before Person A finishes the OpenRouter wiring.

Variability discipline
----------------------
The *test* fakes return constant data so assertions stay stable.
The *demo* fakes (used when ``USE_REAL=false`` in the UI) vary the
``DesignReport.overall_score`` by a small jitter derived from a hash of the
user prompt. Why: the user noticed "score never changes" — that was the fake
returning the same number on every click. Now the fake feels like a real
LLM scoring different screens differently, while staying deterministic
within a single (system, user) pair.

Implementation philosophy
-------------------------
We pattern-match on the requested *schema class name* and return a hand-built
instance of that schema. Adding a new agent? Add one branch in ``_canned``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.schemas.outputs import (
    CompetitorRef,
    Finding,
    Recommendation,
    Severity,
    WCAGFinding,
)


def _hash_jitter(seed: str, low: float, high: float) -> float:
    """Return a deterministic float in [low, high] derived from ``seed``.

    Same seed → same jitter, so cached calls stay stable. Different seeds
    yield different values, so the demo UI does not look frozen.
    """
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    n = int(h[:8], 16) / 0xFFFFFFFF  # in [0, 1]
    return round(low + n * (high - low), 1)


def _canned(schema: type[BaseModel], seed: str = "") -> dict[str, Any]:
    """Return a dict that will validate against ``schema``.

    LOGIC: keyed on ``schema.__name__`` (not isinstance) so subclassing does
    not silently route to the wrong canned response. ``seed`` lets us vary
    a few high-signal numbers (the overall score, breakdown bars) so the
    demo run in offline mode does not feel canned.
    """
    name = schema.__name__

    if name == "VisualAnalysis":
        return {
            "layout": "Two-column dashboard with sticky top nav.",
            "hierarchy": "Primary metrics first, secondary cards below.",
            "palette": ["#0A2540", "#FFC400", "#F5F7FA", "#1F2937"],
            "typography": "Inter for body, Space Grotesk for headings.",
            "spacing_notes": "Consistent 8 px grid; generous gutters.",
            "density_score": 62.0,
            "observations": ["Strong typographic hierarchy", "Subtle drop shadows on cards"],
        }

    if name == "UXCritique":
        finding = Finding(
            title="Low affordance on secondary CTA",
            description="Ghost button blends with card background.",
            severity=Severity.MEDIUM,
            evidence="1px border on light-gray card",
            recommendation="Increase contrast or use filled style.",
        )
        return {
            "heuristic_violations": [finding.model_dump()],
            "cognitive_load_score": 71.0,
            "friction_points": [],
        }

    if name == "AccessibilityReport":
        finding = WCAGFinding(
            title="Insufficient color contrast on secondary CTA",
            description="Foreground/background pair fails WCAG AA.",
            severity=Severity.HIGH,
            evidence="Measured 3.2:1; AA requires 4.5:1.",
            recommendation="Darken text or background to meet AA.",
            criterion="1.4.3",
        )
        return {
            "wcag_findings": [finding.model_dump()],
            "contrast_pass": False,
            "est_min_touch_target_px": 36,
        }

    if name == "MarketResearch":
        return {
            "competitors": [
                CompetitorRef(
                    name="Jupiter",
                    url="https://jupiter.money",
                    why_relevant="Indian retail fintech UX leader.",
                ).model_dump(),
                CompetitorRef(
                    name="Fi Money",
                    url="https://fi.money",
                    why_relevant="Strong Gen-Z UI patterns.",
                ).model_dump(),
            ],
            "trends": ["card stacking", "soft neumorphism receding", "mandatory dark mode"],
            "opportunities": ["education-first onboarding"],
            "threats": ["regulatory changes around UPI"],
            "citations": ["https://example.com/fintech-trends-2026"],
        }

    if name == "BrandConsistency":
        return {
            "consistency_score": 78.0,
            "color_drift": "Secondary teal 12% off corpus median.",
            "type_drift": "Two heading weights diverge from system.",
            "component_drift": "Card radius matches; button radius does not.",
            "comparable_refs": [],
        }

    if name == "DesignReport":
        # LOGIC: vary the overall score and the per-axis breakdown by a
        # deterministic hash of the prompt. Same prompt → same score (test
        # stability). Different prompts → score moves. Resolves the
        # "score never changes" complaint in offline demo mode.
        overall = _hash_jitter(seed or "default", 64.0, 86.0)
        breakdown = {
            "visual": _hash_jitter(seed + ":visual", 60.0, 90.0),
            "ux": _hash_jitter(seed + ":ux", 55.0, 85.0),
            "accessibility": _hash_jitter(seed + ":accessibility", 50.0, 90.0),
            "brand": _hash_jitter(seed + ":brand", 60.0, 92.0),
            "market": _hash_jitter(seed + ":market", 55.0, 80.0),
        }
        return {
            "overall_score": overall,
            "executive_summary": (
                "The primary action is doing its job: a single brand colour "
                "is reserved for one button, and the typographic scale "
                "stays disciplined under dense data. The drag on the score "
                "is a single failing contrast pair on the secondary CTA — "
                "the same element the UX agent flagged as low-affordance — "
                "which makes one of the two above-the-fold actions read as "
                "tertiary. Ship a contrast fix on the secondary CTA this "
                "sprint and the screen reads as production-ready."
            ),
            "score_rationale": (
                f"Overall {overall:.0f} reflects a polished visual layer "
                f"({breakdown['visual']:.0f}) carrying a softer UX surface "
                f"({breakdown['ux']:.0f}) and one accessibility hot-spot "
                f"({breakdown['accessibility']:.0f}). Brand consistency is "
                f"strong ({breakdown['brand']:.0f}); market alignment is "
                f"average ({breakdown['market']:.0f}). The score is held back "
                "by a single failing contrast pair on the secondary CTA — "
                "fixing it alone would raise the overall by ~6 points."
            ),
            "score_breakdown": breakdown,
            "top_strengths": [
                "Disciplined typographic scale: only two heading weights "
                "and one body weight; no rogue sizes anywhere on screen",
                "Primary CTA owns the brand purple — every other action "
                "is outline or text, so attention concentrates correctly",
                "Spacing rhythm holds at every breakpoint — 8 px grid is "
                "respected even inside dense card components",
            ],
            "top_recommendations": [
                Recommendation(
                    priority=1,
                    title="Raise secondary CTA contrast from 3.2:1 to ≥4.5:1",
                    rationale=(
                        "Accessibility agent flagged WCAG 1.4.3 failure on "
                        "the same element UX called out as low-affordance — "
                        "the cheapest, highest-leverage fix in this report."
                    ),
                    effort="S",
                    impact="L",
                    metric_lift="+8% expected click-through on secondary CTA",
                    proof="accessibility:1.4.3",
                ).model_dump(),
                Recommendation(
                    priority=2,
                    title="Promote one above-the-fold action; demote the others",
                    rationale=(
                        "UX agent's H8 (aesthetic and minimalist) flagged "
                        "three competing CTAs above the fold — a known "
                        "conversion-killer in this market segment."
                    ),
                    effort="M",
                    impact="L",
                    metric_lift="+12% first-screen conversion in similar tests",
                    proof="ux:heuristic_violations[0]",
                ).model_dump(),
                Recommendation(
                    priority=3,
                    title="Tighten brand palette: drop the secondary teal drift",
                    rationale=(
                        "Brand agent measured 12% drift from corpus median on "
                        "the secondary teal — visible inconsistency at scale."
                    ),
                    effort="S",
                    impact="M",
                    metric_lift="Brand consistency score +6 points",
                    proof="brand:color_drift",
                ).model_dump(),
            ],
            "run_id": hashlib.sha256(seed.encode()).hexdigest()[:8] if seed else "fakedemo",
            "analyzed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "analysis_status": {
                "visual": "ok",
                "ux": "ok",
                "accessibility": "ok",
                "brand": "ok",
                "market": "ok",
            },
        }

    raise ValueError(
        f"FakeLLM has no canned response for schema '{name}'. "
        f"Add one to src/fakes/fake_llm._canned()."
    )


class FakeLLM:
    """Schema-driven canned responses for ``LLMClient``."""

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        # LOGIC: structure-stable but content-varying. The schema name
        # selects the canned shape; ``user`` is a seed so the demo never
        # shows the same number twice for two different screens.
        return schema.model_validate(_canned(schema, seed=user))


class FakeVisionLLM:
    """Same as ``FakeLLM`` plus a sanity check that images exist on disk."""

    def analyze(
        self,
        *,
        system: str,
        user: str,
        images: list[Path | str],
        schema: type[BaseModel],
        model: str | None = None,
    ) -> BaseModel:
        # LOGIC: we DO check images exist — Person C/D often pass a wrong
        # path, and a fake that silently accepts that is worse than no fake.
        for img in images:
            p = Path(img)
            if not p.exists():
                raise FileNotFoundError(f"FakeVisionLLM: image not found: {p}")
        # LOGIC: seed jitter on the absolute image path so two different
        # screenshots produce two different score curves.
        seed = user + "|" + "|".join(str(Path(i).resolve()) for i in images)
        return schema.model_validate(_canned(schema, seed=seed))
