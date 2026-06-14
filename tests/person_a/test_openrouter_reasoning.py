"""Reasoning-model handling on the OpenRouter client.

OpenAI's reasoning families (o1, o3, GPT-5) burn a slice of ``max_tokens``
on hidden chain-of-thought before producing visible content. Without an
explicit ``reasoning.effort`` cap, multi-image multimodal calls return
empty content or truncated JSON because the budget runs out mid-output.

These tests pin three behaviors:

1. ``_is_reasoning_model`` correctly classifies every model id we ship.
2. When a reasoning model is requested, ``extra_body`` carries
   ``reasoning={effort: minimal, exclude: True}`` AND ``max_tokens`` is
   bumped to 8192 (the empirical floor for multi-image reasoning runs).
3. When a non-reasoning model is requested, no ``extra_body`` is sent
   (so we don't accidentally pass ``reasoning`` to providers that
   reject it as an unknown parameter).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.llm.openrouter_client import (
    OpenRouterClient,
    _build_extra_body,
    _is_reasoning_model,
)
from src.schemas.outputs import VisualAnalysis

pytestmark = [pytest.mark.person_a]


@pytest.mark.parametrize(
    "model_id,is_reasoning",
    [
        ("openai/gpt-5", True),
        ("openai/gpt-5-mini", True),
        ("openai/gpt-5-nano", True),
        ("openai/o1", True),
        ("openai/o3-mini", True),
        ("openai/o4-mini", True),
        ("x-ai/grok-4", True),
        ("openai/gpt-4o", False),
        ("openai/gpt-4o-mini", False),
        ("anthropic/claude-3.5-sonnet", False),
        ("anthropic/claude-3.5-haiku", False),
        ("google/gemini-2.5-flash", False),
        ("meta-llama/llama-3.2-90b-vision-instruct", False),
        ("", False),
    ],
)
def test_is_reasoning_model_classifies_correctly(model_id: str, is_reasoning: bool) -> None:
    assert _is_reasoning_model(model_id) is is_reasoning


def test_build_extra_body_pins_minimal_effort_for_reasoning_models() -> None:
    eb = _build_extra_body("openai/gpt-5-mini")
    assert eb == {"reasoning": {"effort": "minimal", "exclude": True}}


def test_build_extra_body_empty_for_non_reasoning_models() -> None:
    eb = _build_extra_body("openai/gpt-4o-mini")
    assert eb == {}


def _stub_completion(content: str, *, finish_reason: str = "stop") -> Any:
    """Build a minimal SDK-compatible response for the test mock."""
    msg = MagicMock(content=content)
    choice = MagicMock(message=msg, finish_reason=finish_reason)
    usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return MagicMock(choices=[choice], usage=usage)


@pytest.fixture
def client_with_mocked_sdk(monkeypatch: pytest.MonkeyPatch) -> tuple[OpenRouterClient, MagicMock]:
    """Build a client whose ``_client()`` returns a mock OpenAI SDK."""
    client = OpenRouterClient()

    rich_visual = (
        '{"palette": ["#0A2440", "#FFFFFF", "#F2C200"], '
        '"layout": "card-grid hero", "hierarchy": "h1 > body", '
        '"typography": "sans-serif modern", "spacing_notes": "generous", '
        '"density_score": 35.0, "observations": ["bold hero", "clean"]}'
    )

    sdk = MagicMock()
    sdk.chat.completions.create = MagicMock(
        return_value=_stub_completion(rich_visual)
    )
    monkeypatch.setattr(client, "_client", lambda: sdk)
    return client, sdk


def test_chat_with_schema_passes_reasoning_effort_for_gpt5(
    client_with_mocked_sdk: tuple[OpenRouterClient, MagicMock],
) -> None:
    """GPT-5: extra_body must carry the reasoning cap, max_tokens bumped to 8192."""
    client, sdk = client_with_mocked_sdk
    messages = [
        {"role": "system", "content": "you analyze ui"},
        {"role": "user", "content": "describe this"},
    ]

    out = client._chat_with_schema(
        messages=messages,
        model="openai/gpt-5-mini",
        schema=VisualAnalysis,
        temperature=0.2,
    )

    assert isinstance(out, VisualAnalysis)
    sdk.chat.completions.create.assert_called_once()
    kwargs = sdk.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-5-mini"
    assert kwargs["extra_body"] == {
        "reasoning": {"effort": "minimal", "exclude": True}
    }
    assert kwargs["max_tokens"] >= 8192


def test_chat_with_schema_omits_extra_body_for_non_reasoning_model(
    client_with_mocked_sdk: tuple[OpenRouterClient, MagicMock],
) -> None:
    """gpt-4o-mini: extra_body must be None so it is not sent at all."""
    client, sdk = client_with_mocked_sdk
    messages = [
        {"role": "system", "content": "you analyze ui"},
        {"role": "user", "content": "describe this"},
    ]

    out = client._chat_with_schema(
        messages=messages,
        model="openai/gpt-4o-mini",
        schema=VisualAnalysis,
        temperature=0.2,
    )

    assert isinstance(out, VisualAnalysis)
    kwargs = sdk.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-4o-mini"
    # ``extra_body=None`` is what the OpenAI SDK treats as "do not send"
    # — we must NOT send the dict literal {} either, since a few
    # providers reject any unknown top-level key on the wire.
    assert kwargs["extra_body"] is None
