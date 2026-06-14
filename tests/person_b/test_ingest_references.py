"""Ingest CLI pipeline tests without loading CLIP or LanceDB."""

from __future__ import annotations

import os

import numpy as np
import pytest

pytestmark = pytest.mark.person_b


class _FakeEmbedder:
    dim = 2

    def embed_batch(self, images):
        return np.array([[1.0, 0.0] for _ in images], dtype="float32")


def test_ingest_references_builds_portable_records(tmp_settings, tmp_path, monkeypatch):
    from scripts import ingest_references
    from src.rag import embedder, vector_store

    source = tmp_path / "reference"
    source.mkdir(exist_ok=True)
    (source / "a.png").write_bytes(b"a")
    (source / "b.jpg").write_bytes(b"b")
    (source / "ignore.txt").write_text("not an image")

    captured = {}

    monkeypatch.setattr(ingest_references, "settings", tmp_settings)
    monkeypatch.setattr(embedder, "CLIPEmbedder", _FakeEmbedder)
    monkeypatch.setattr(vector_store, "open_db", lambda: "db")
    monkeypatch.setattr(vector_store, "get_or_create_table", lambda db, dim: "table")
    monkeypatch.setattr(
        vector_store,
        "upsert_records",
        lambda table, records: captured.update(table=table, records=records),
    )

    assert ingest_references.main(["--source", str(source), "--tag", "demo"]) == 0
    assert captured["table"] == "table"
    assert [r["image_path"] for r in captured["records"]] == [
        f"reference{os.sep}a.png",
        f"reference{os.sep}b.jpg",
    ]
    assert all(r["tags"] == ["demo"] for r in captured["records"])
    assert all(len(r["vector"]) == 2 for r in captured["records"])
