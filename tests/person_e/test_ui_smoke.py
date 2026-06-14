"""UI smoke — just verify the module imports and ``main`` exists.

We do NOT actually launch Gradio in CI. A real e2e UI test would use
``playwright`` and is out of scope for the hackathon.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.person_e


def test_ui_module_imports():
    import importlib

    mod = importlib.import_module("ui.app")
    assert hasattr(mod, "main")
    assert callable(mod.on_run)


def test_render_report_handles_none(fake_deps):
    from ui.app import render_report

    out = render_report(None)
    # Contract: empty-state placeholder must mention "no report" so the user
    # knows to run an analysis. Representation (markdown vs HTML vs plaintext)
    # is up to the UI author and may evolve.
    assert "no report" in out.lower()
