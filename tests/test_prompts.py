"""Tests pinning the anti-hallucination contract on every prompt.

Why this exists
---------------
The single biggest failure mode of multi-agent LLM systems is models
inventing facts when evidence runs out (URLs, brand names, WCAG SCs,
percentage lifts, contrast ratios, font names). We added an
``ANTI_HALLUCINATION_RULE`` and an ``ABSTENTION_RULE`` to the shared
prompt scaffolding to defend against this. The rules are useless if a
later refactor drops them from any prompt — these tests make that
mistake catch in CI instead of in production.

Each test checks ONE structural guarantee per prompt:

  - The hard anti-hallucination block is present.
  - The abstention block is present.
  - The self-check block is present.
  - The output / JSON contract is present.
  - The evidence rule is present.

We deliberately do NOT pin the exact text of the rules — that would
make every prompt edit fail tests. We only pin the section headings,
which are stable.
"""

from __future__ import annotations

import pytest

from src.utils.prompts import (
    accessibility_system,
    accessibility_user,
    brand_consistency_system,
    brand_consistency_user,
    market_research_system,
    synthesizer_system,
    ux_critique_system,
    ux_critique_user,
    visual_analysis_system,
    visual_analysis_user,
)
from src.utils.prompts._shared import (
    ABSTENTION_RULE,
    ANTI_HALLUCINATION_RULE,
    EVIDENCE_RULE,
    JSON_OUTPUT_RULE,
    SELF_CHECK_RULE,
)

# Every system prompt builder. User-prompt builders are tested
# separately because they take state objects and don't carry the
# rule scaffolding (it's the system prompt's job).
SYSTEM_PROMPT_BUILDERS = [
    pytest.param(visual_analysis_system, id="visual"),
    pytest.param(ux_critique_system, id="ux"),
    pytest.param(market_research_system, id="market"),
    pytest.param(accessibility_system, id="accessibility"),
    pytest.param(brand_consistency_system, id="brand"),
    pytest.param(synthesizer_system, id="synthesizer"),
]


@pytest.mark.parametrize("builder", SYSTEM_PROMPT_BUILDERS)
def test_prompt_carries_anti_hallucination_block(builder) -> None:
    s = builder()
    assert "ANTI-HALLUCINATION RULES" in s, (
        "Prompt is missing the shared ANTI_HALLUCINATION_RULE block. "
        "Re-add it; the model will fabricate facts without it."
    )


@pytest.mark.parametrize("builder", SYSTEM_PROMPT_BUILDERS)
def test_prompt_carries_abstention_block(builder) -> None:
    s = builder()
    assert "HOW TO ABSTAIN" in s, (
        "Prompt is missing the shared ABSTENTION_RULE block. The model "
        "needs explicit permission to return null/empty when evidence "
        "is missing — otherwise it will guess."
    )


@pytest.mark.parametrize(
    "builder",
    # Synthesizer is excluded because it never sees pixels — only the
    # structured outputs of the specialists. The shared SELF_CHECK rule
    # already covers grounding in the structured-data case.
    [b for b in SYSTEM_PROMPT_BUILDERS if b.id != "synthesizer"],
)
def test_specialist_prompts_carry_evidence_rule(builder) -> None:
    s = builder()
    assert "EVIDENCE RULES" in s


@pytest.mark.parametrize("builder", SYSTEM_PROMPT_BUILDERS)
def test_prompt_carries_self_check(builder) -> None:
    s = builder()
    assert "SELF-CHECK" in s


@pytest.mark.parametrize("builder", SYSTEM_PROMPT_BUILDERS)
def test_prompt_carries_json_output_rule(builder) -> None:
    s = builder()
    assert "OUTPUT RULES" in s


# --------------------------------------------------------------------------- #
# Specific anti-hallucination clauses we never want to lose                    #
# --------------------------------------------------------------------------- #
def test_market_forbids_inventing_competitors() -> None:
    s = market_research_system()
    assert "DO NOT introduce a competitor not present in <results>" in s


def test_accessibility_caps_wcag_sc_list() -> None:
    s = accessibility_system()
    # The list must be present so the model can't invent SCs.
    for sc in ("1.4.3", "1.4.11", "2.5.5", "4.1.2"):
        assert sc in s
    # And the rule that forbids inventing is present.
    assert "Do NOT invent SCs" in s


def test_visual_forbids_inventing_font_names() -> None:
    s = visual_analysis_system()
    assert "do NOT name a font" in s


def test_ux_forbids_inventing_quoted_text() -> None:
    s = ux_critique_system()
    assert "must appear LITERALLY on the screenshot" in s


def test_brand_grounds_in_retrieved_refs_only() -> None:
    s = brand_consistency_system()
    assert "ids the user message provided" in s
    assert "no reference set available" in s.lower()


def test_synthesizer_grounds_proof_in_inputs_only() -> None:
    s = synthesizer_system()
    assert "have NO access to the screenshot" in s
    assert "metric_lift" in s
    # Collapse whitespace so substrings spanning a wrapped line still match.
    flat = " ".join(s.split())
    assert "NEVER fabricate" in flat
    assert "industry-standard" in flat


# --------------------------------------------------------------------------- #
# Sanity: shared constants are non-trivial                                     #
# --------------------------------------------------------------------------- #
def test_shared_rules_are_not_empty() -> None:
    for r in (ANTI_HALLUCINATION_RULE, ABSTENTION_RULE, EVIDENCE_RULE,
              SELF_CHECK_RULE, JSON_OUTPUT_RULE):
        assert len(r.strip()) > 100, "shared rule too short to be useful"


# --------------------------------------------------------------------------- #
# User-prompt builders still produce something                                 #
# --------------------------------------------------------------------------- #
def test_user_prompts_produce_non_empty_strings() -> None:
    from src.schemas.outputs import GraphState

    state = GraphState(
        image_path="/tmp/fake.png",
        instructions="A SaaS dashboard for engineers.",
    )
    assert visual_analysis_user(state)
    assert ux_critique_user(state)
    assert accessibility_user(state)
    # brand_consistency_user takes a list of refs
    assert brand_consistency_user([])
