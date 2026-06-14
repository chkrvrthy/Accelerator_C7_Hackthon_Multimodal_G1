"""CLIP embedder smoke (skipped without the heavy deps).

Person B replaces ``pytest.importorskip("torch")`` with real torch + open_clip
once the slice is wired. Until then this test only verifies the class exists
and emits a useful error.
"""

from __future__ import annotations

import pytest

from src.rag.embedder import CLIPEmbedder

pytestmark = pytest.mark.person_b


def test_embedder_class_imports():
    # The class can be constructed without torch installed because we keep
    # the heavy imports lazy. The first method call is what fails loudly.
    e = CLIPEmbedder()
    assert e.dim == 512


@pytest.mark.slow
def test_embedder_image_returns_512_normalized(tiny_png):
    pytest.importorskip("torch")
    pytest.importorskip("open_clip")
    e = CLIPEmbedder()
    vec = e.embed_image(tiny_png)
    assert vec.shape == (512,)
    norm = float((vec * vec).sum() ** 0.5)
    assert abs(norm - 1.0) < 1e-3, "CLIP embeddings must be L2-normalized."


@pytest.mark.slow
def test_embedder_text_returns_512(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("open_clip")
    e = CLIPEmbedder()
    vec = e.embed_text("modern fintech dashboard")
    assert vec.shape == (512,)
