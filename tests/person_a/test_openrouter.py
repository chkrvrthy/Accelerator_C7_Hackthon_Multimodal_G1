"""Real OpenRouter round-trip — guarded by ``real_api`` mark.

This test only runs when ``OPENROUTER_API_KEY`` is set in the environment.
Locally and in CI without keys it is auto-skipped by ``conftest.py``.
"""

from __future__ import annotations

import pytest

from src.schemas.outputs import VisualAnalysis

pytestmark = [pytest.mark.person_a, pytest.mark.real_api]


def test_openrouter_complete_returns_visual_analysis():
    pytest.importorskip("openai")
    from src.llm.openrouter_client import OpenRouterClient

    client = OpenRouterClient()
    out = client.complete(
        system="You return a VisualAnalysis JSON.",
        user="Pretend you saw a fintech dashboard with a navy palette.",
        schema=VisualAnalysis,
    )
    assert isinstance(out, VisualAnalysis)
    assert out.palette  # at least one color recovered
