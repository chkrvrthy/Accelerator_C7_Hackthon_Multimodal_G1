"""Minimal eval harness — schema-validity only.

OWNER: Person A (infra), shared maintenance.
SPRINT CONCEPTS: Sprint 4 — Evals.
PROVIDES: ``run_eval``, ``aggregate``.

WHY SCHEMA-VALIDITY IS ENOUGH FOR A HACKATHON
---------------------------------------------
Schema validity proves the contract holds end-to-end across the whole
specialist surface. If the visual agent suddenly returns ``palette`` as a
string instead of a list, this harness catches it. That is the single most
likely real-world failure: prompt drift breaking the JSON shape.

Free-text "LLM-as-judge" scoring is documented as a post-MVP stretch. If you
have spare time on Day 2, plug it in by replacing ``schema_valid`` with a
``judge_score`` that asks a second LLM "rate this finding on rubric XYZ".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.agents.base import AgentDeps, build_default_deps
from src.agents.graph import run_graph
from src.schemas.outputs import (
    AccessibilityReport,
    BrandConsistency,
    DesignReport,
    MarketResearch,
    UXCritique,
    VisualAnalysis,
)
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.evals.golden_set import GoldenCase

log = get_logger(__name__)


class EvalResult(BaseModel):
    """Outcome for one ``GoldenCase``."""

    case_name: str
    schema_valid: dict[str, bool] = Field(default_factory=dict)
    pass_rate: float = 0.0
    error: str | None = None


class EvalSummary(BaseModel):
    """Aggregate over a batch of ``EvalResult``s."""

    total_cases: int = 0
    overall_pass_rate: float = 0.0
    per_agent_failures: dict[str, int] = Field(default_factory=dict)


_FIELD_TO_SCHEMA: dict[str, type[BaseModel]] = {
    "visual": VisualAnalysis,
    "ux": UXCritique,
    "accessibility": AccessibilityReport,
    "market": MarketResearch,
    "brand": BrandConsistency,
}


def run_eval(case: GoldenCase, deps: AgentDeps | None = None) -> EvalResult:
    """Run the graph on ``case`` and check schema validity per agent."""
    deps = deps or build_default_deps()
    try:
        report: DesignReport = run_graph(case.image_path, instructions=case.instructions, deps=deps)
    except Exception as e:
        log.error("eval.run_eval failed for %s: %s", case.name, e)
        return EvalResult(case_name=case.name, error=str(e), pass_rate=0.0)

    valid: dict[str, bool] = {}
    for field, schema in _FIELD_TO_SCHEMA.items():
        obj = getattr(report, field, None)
        if obj is None:
            valid[field] = False
            continue
        try:
            schema.model_validate(obj.model_dump())
            valid[field] = True
        except Exception as e:
            # LOGIC: in evals we deliberately keep going on a single bad
            # field — but the operator should see *which* one failed.
            log.warning("eval %s: %s failed schema check: %s", case.name, field, e)
            valid[field] = False

    pass_rate = sum(valid.values()) / max(len(valid), 1)
    return EvalResult(case_name=case.name, schema_valid=valid, pass_rate=pass_rate)


def aggregate(results: list[EvalResult]) -> EvalSummary:
    """Aggregate per-case results."""
    if not results:
        return EvalSummary()
    total = len(results)
    overall = sum(r.pass_rate for r in results) / total
    per_agent: dict[str, int] = {}
    for r in results:
        for agent, ok in r.schema_valid.items():
            if not ok:
                per_agent[agent] = per_agent.get(agent, 0) + 1
    return EvalSummary(
        total_cases=total,
        overall_pass_rate=overall,
        per_agent_failures=per_agent,
    )
