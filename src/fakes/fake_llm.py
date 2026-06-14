"""Deterministic LLM doubles satisfying ``LLMClient`` and ``VisionLLM``.

OWNER: Person A

Why these matter
----------------
Without a fake LLM, every test would need an API key and would burn money on
every CI run. With a fake LLM:

    * Test runs are < 1 s.
    * Same canned output every time → assertions can compare exact values.
    * Person C/D/E can ship before Person A finishes the OpenRouter wiring.

Implementation philosophy
-------------------------
We pattern-match on the requested *schema class name* and return a hand-built
instance of that schema. Adding a new agent? Add one branch in ``_canned``.
The LLM never inspects the prompt — that is the point: behavior is decoupled
from prompt iteration.
"""

from __future__ import annotations

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


def _canned(schema: type[BaseModel]) -> dict[str, Any]:
    """Return a dict that will validate against ``schema``.

    LOGIC: keyed on ``schema.__name__`` (not isinstance) so subclassing does
    not silently route to the wrong canned response.
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
        rec = Recommendation(
            title="Fix secondary CTA contrast",
            rationale="WCAG AA failure on a key conversion element.",
            effort="S",
            impact="L",
        )
        return {
            "overall_score": 72.5,
            "top_strengths": [
                "Clear hierarchy in primary stats panel",
                "Consistent color usage with brand palette",
                "Strong information density without clutter",
            ],
            "top_recommendations": [rec.model_dump()],
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
        # NOTE: we ignore system/user/model on purpose. Behaviour is driven
        # by the schema name — that is what makes this fake stable.
        return schema.model_validate(_canned(schema))


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
        return schema.model_validate(_canned(schema))
