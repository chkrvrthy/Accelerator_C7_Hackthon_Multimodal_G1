"""Centralized prompt library — package entry point.

OWNER: Shared (every agent author edits their own prompt; do not rewrite others').
SPRINT CONCEPTS: prompt engineering, structured output (JSON-schema mode).
PROVIDES: one system + one user prompt builder per agent, plus the shared
          rule fragments (TONE, EVIDENCE, JSON_OUTPUT, SELF_CHECK).

Layout:

  src/utils/prompts/
    _shared.py       # JSON / EVIDENCE / TONE / AUDIENCE / SELF_CHECK rules
    visual.py        # visual_analysis_system / visual_analysis_user
    ux.py            # ux_critique_system / ux_critique_user
    market.py        # market_research_system
    accessibility.py # accessibility_system / accessibility_user
    brand.py         # brand_consistency_system / brand_consistency_user
    synthesizer.py   # synthesizer_system

This module is the public surface — every importer that does
``from src.utils.prompts import visual_analysis_system`` keeps working.
The split is a code-organization fix only: behavior is identical to the
single-file version that came before it.
"""

from __future__ import annotations

from src.utils.prompts._shared import (
    ABSTENTION_RULE,
    ANTI_HALLUCINATION_RULE,
    AUDIENCE_RULE,
    EVIDENCE_RULE,
    JSON_OUTPUT_RULE,
    SELF_CHECK_RULE,
    TONE_HINT,
    TONE_RULE,
    multi_image_note,
)
from src.utils.prompts.accessibility import accessibility_system, accessibility_user
from src.utils.prompts.brand import brand_consistency_system, brand_consistency_user
from src.utils.prompts.market import market_research_system
from src.utils.prompts.synthesizer import synthesizer_system
from src.utils.prompts.ux import ux_critique_system, ux_critique_user
from src.utils.prompts.visual import visual_analysis_system, visual_analysis_user

__all__ = [
    "ABSTENTION_RULE",
    "ANTI_HALLUCINATION_RULE",
    "AUDIENCE_RULE",
    "EVIDENCE_RULE",
    "JSON_OUTPUT_RULE",
    "SELF_CHECK_RULE",
    "TONE_HINT",
    "TONE_RULE",
    "accessibility_system",
    "accessibility_user",
    "brand_consistency_system",
    "brand_consistency_user",
    "market_research_system",
    "multi_image_note",
    "synthesizer_system",
    "ux_critique_system",
    "ux_critique_user",
    "visual_analysis_system",
    "visual_analysis_user",
]
