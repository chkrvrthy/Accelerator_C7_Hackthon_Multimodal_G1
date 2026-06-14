"""Full graph runs end-to-end with fakes.

This test is the smoke check Person A relies on after every commit. If this
goes red, the demo is at risk.
"""

from __future__ import annotations

import pytest

from src.agents.graph import run_graph
from src.schemas.outputs import DesignReport

pytestmark = pytest.mark.person_a


def test_run_graph_returns_design_report(fake_deps, sample_image):
    rep = run_graph(sample_image, instructions="audience: Indian retail", deps=fake_deps)
    assert isinstance(rep, DesignReport)
    assert rep.visual is not None and rep.ux is not None and rep.brand is not None


def test_run_graph_persists_report_to_disk(fake_deps, sample_image, tmp_settings):
    rep = run_graph(sample_image, deps=fake_deps)
    files = list(tmp_settings.report_dir.glob("*.json"))
    assert files, f"synthesizer should write a report under {tmp_settings.report_dir}"
    assert isinstance(rep, DesignReport)
