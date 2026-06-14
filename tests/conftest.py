"""Shared fixtures — the single file that makes all per-slice tests work.

OWNER: Person A
SPRINT CONCEPTS: testing infra (Code-Quality concept).

WHY THIS FILE MATTERS
---------------------
Every per-slice test imports the same ``fake_deps`` fixture so:

  * No teammate has to know how to construct an ``AgentDeps``.
  * Swapping a fake (e.g. when the real impl finally lands) is a one-line
    change here, not 30 changes across the test tree.
  * Fixture scope is ``function`` by default so test isolation is explicit.

If a fixture starts failing, this is the first file you read.
"""

from __future__ import annotations

import os
import struct
import zlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.agents.base import AgentDeps
from src.config import Settings
from src.fakes import FakeLLM, FakeRetriever, FakeSearch, FakeVisionLLM, ensure_sample_design

# --------------------------------------------------------------------------- #
# Fakes                                                                        #
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_vision() -> FakeVisionLLM:
    return FakeVisionLLM()


@pytest.fixture
def fake_retriever() -> FakeRetriever:
    return FakeRetriever()


@pytest.fixture
def fake_search() -> FakeSearch:
    return FakeSearch()


@pytest.fixture
def fake_deps(
    fake_llm: FakeLLM,
    fake_vision: FakeVisionLLM,
    fake_retriever: FakeRetriever,
    fake_search: FakeSearch,
) -> AgentDeps:
    """Composed AgentDeps for any agent under test."""
    return AgentDeps(
        llm=fake_llm,
        vision=fake_vision,
        retriever=fake_retriever,
        search=fake_search,
    )


# --------------------------------------------------------------------------- #
# Filesystem                                                                   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def sample_image() -> Path:
    """Path to the bundled tiny PNG. Idempotent."""
    return ensure_sample_design()


@pytest.fixture
def tiny_png(tmp_path: Path) -> Path:
    """Write a 32x32 solid-color PNG under tmp_path. Used by Person B tests
    so the ingestion pipeline has something to embed without external files.
    """
    width = height = 32
    raw = b""
    for _ in range(height):
        raw += b"\x00" + (b"\x10\x20\x80\xff" * width)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png += chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    p = tmp_path / "tiny.png"
    p.write_bytes(png)
    return p


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Clone settings, retarget every *_dir to ``tmp_path``, monkeypatch global.

    HINT: this is what stops one test from polluting another's data/ directory.
    """
    cfg = Settings(
        upload_dir=tmp_path / "uploads",
        reference_dir=tmp_path / "reference",
        report_dir=tmp_path / "reports",
        cache_dir=tmp_path / "cache",
        vector_store_dir=tmp_path / "vector_store",
    )
    cfg.ensure_dirs()
    monkeypatch.setattr("src.config.settings", cfg, raising=True)
    yield cfg


# --------------------------------------------------------------------------- #
# Real-API gating                                                              #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _skip_real_api_without_key(request: pytest.FixtureRequest) -> None:
    """Auto-skip ``@pytest.mark.real_api`` tests when no key is set."""
    if "real_api" in request.keywords and not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("real_api test requires OPENROUTER_API_KEY in env.")
