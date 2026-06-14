"""Tests for the synthesizer quality gate.

The gate is pure-Python and never calls an LLM, so we can be exhaustive
here. The contract this file pins down:

  1. A complete, prose-y DesignReport produces ZERO issues.
  2. A placeholder-thin DesignReport produces 'fail'-severity issues
     keyed by the specific field that is thin (so the agent retry loop
     can hand the LLM exactly the right corrective feedback).
"""

from __future__ import annotations

from src.agents.quality_gate import (
    check_design_report,
    format_issues_for_prompt,
)
from src.fakes.fake_llm import FakeLLM
from src.schemas.outputs import DesignReport, Recommendation


def _good_report() -> DesignReport:
    """A DesignReport that should pass every quality check."""
    fake = FakeLLM()
    rep = fake.complete(
        system="seed",
        user="for-test",
        schema=DesignReport,
    )
    assert isinstance(rep, DesignReport)
    return rep


def test_good_report_has_no_fail_issues() -> None:
    rep = _good_report()
    issues = check_design_report(rep)
    fails = [i for i in issues if i.severity == "fail"]
    assert (
        fails == []
    ), f"FakeLLM produces a placeholder-thin DesignReport: {[i.reason for i in fails]}"


def test_thin_executive_summary_is_flagged() -> None:
    rep = _good_report().model_copy(update={"executive_summary": "Too short."})
    issues = check_design_report(rep)
    fields = {i.field for i in issues if i.severity == "fail"}
    assert "executive_summary" in fields


def test_thin_score_rationale_is_flagged() -> None:
    rep = _good_report().model_copy(update={"score_rationale": "ok"})
    issues = check_design_report(rep)
    fields = {i.field for i in issues if i.severity == "fail"}
    assert "score_rationale" in fields


def test_too_few_recommendations_is_flagged() -> None:
    rep = _good_report().model_copy(
        update={
            "top_recommendations": [
                Recommendation(
                    title="Only one",
                    description="hi",
                    rationale="x" * 60,
                    impact="L",
                    effort="S",
                    priority=1,
                ),
            ],
        }
    )
    issues = check_design_report(rep)
    fields = {i.field for i in issues if i.severity == "fail"}
    assert "top_recommendations" in fields


def test_format_issues_for_prompt_is_terse() -> None:
    rep = _good_report().model_copy(update={"executive_summary": "x"})
    issues = check_design_report(rep)
    block = format_issues_for_prompt(issues)
    # Sanity: short, action-oriented, name the field name as the LLM hint.
    assert "executive_summary" in block
    assert len(block) < 1500, "corrective feedback should be << 1.5kB"


def test_format_issues_empty_returns_empty() -> None:
    assert format_issues_for_prompt([]) == ""
