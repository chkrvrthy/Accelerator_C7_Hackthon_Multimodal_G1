"""Cost layer — hash determinism + select_model contract."""

from __future__ import annotations

import pytest

from src.config import settings
from src.llm.cost import prompt_hash, select_model

pytestmark = pytest.mark.person_a


def test_prompt_hash_is_deterministic():
    a = prompt_hash(system="s", user="u", images=["x"], schema_name="X", model="m")
    b = prompt_hash(system="s", user="u", images=["x"], schema_name="X", model="m")
    assert a == b


def test_prompt_hash_changes_when_input_changes():
    a = prompt_hash(system="s", user="u", images=["x"], schema_name="X", model="m")
    b = prompt_hash(system="s", user="U", images=["x"], schema_name="X", model="m")
    assert a != b


def test_select_model_routes_text_and_vision():
    assert select_model("default") == settings.default_text_model
    assert select_model("vision") == settings.default_vision_model
