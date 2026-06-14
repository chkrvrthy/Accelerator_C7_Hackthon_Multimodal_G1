"""VisualAnalysis palette validator (Person C model rule).

The validator keeps only valid hex colors so UI swatches never choke on a
hallucinated color name, while staying lenient (filter, not raise) so one bad
entry never fails the whole graph.
"""

from __future__ import annotations

import pytest

from src.schemas.outputs import VisualAnalysis

pytestmark = pytest.mark.person_c


def test_palette_drops_color_names_keeps_hex():
    v = VisualAnalysis(palette=["#abcdef", "navy", "#000", "", "teal"])
    assert v.palette == ["#abcdef", "#000"]


def test_palette_accepts_three_and_six_digit_hex():
    v = VisualAnalysis(palette=["#fff", "#FFFFFF", "#0A2540"])
    assert v.palette == ["#fff", "#FFFFFF", "#0A2540"]


def test_palette_trims_whitespace():
    v = VisualAnalysis(palette=["  #0A2540  "])
    assert v.palette == ["#0A2540"]


def test_palette_rejects_malformed_hex():
    # wrong length / non-hex chars are dropped
    v = VisualAnalysis(palette=["#12", "#12345", "#1234567", "#ggg"])
    assert v.palette == []
