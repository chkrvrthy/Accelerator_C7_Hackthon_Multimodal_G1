"""Deterministic Retriever double for offline development.

OWNER: Person A

This is what unblocks Person C's brand-consistency agent before Person B's
LanceDB pipeline lands. Every call returns the same three references with
descending similarity scores, so test assertions can pin exact ordering.
"""

from __future__ import annotations

from pathlib import Path

from src.fakes.fixtures import SAMPLE_DESIGN, ensure_sample_design
from src.schemas.outputs import RetrievedRef


class FakeRetriever:
    """3 canned references that all point at the bundled sample image.

    HINT: real Retriever returns paths relative to ``data/reference``. We
    deliberately use a relative-looking string ("fakes/sample.png") so brand
    agent code that does ``str.startswith("data/reference")`` will *not*
    accidentally pass on the fake — that surfaces wrong assumptions early.
    """

    def __init__(self) -> None:
        ensure_sample_design()
        # LOGIC: the path string here is what shows up in BrandConsistency
        # output; agents should not rely on it being absolute.
        rel = (
            str(SAMPLE_DESIGN.relative_to(Path.cwd()))
            if SAMPLE_DESIGN.is_relative_to(Path.cwd())
            else str(SAMPLE_DESIGN)
        )
        self._refs = [
            RetrievedRef(
                id="ref-007",
                score=0.92,
                image_path=rel,
                metadata={"brand": "example-corp", "year": 2025, "tag": "dashboard"},
            ),
            RetrievedRef(
                id="ref-014",
                score=0.81,
                image_path=rel,
                metadata={"brand": "example-corp", "year": 2024, "tag": "card-grid"},
            ),
            RetrievedRef(
                id="ref-022",
                score=0.74,
                image_path=rel,
                metadata={"brand": "example-corp", "year": 2024, "tag": "settings"},
            ),
        ]

    def retrieve_by_image(self, image_path: Path | str, k: int = 5) -> list[RetrievedRef]:
        # LOGIC: we don't actually look at image_path; we just check it
        # exists so a typo in the agent fails loudly here.
        if not Path(image_path).exists():
            raise FileNotFoundError(f"FakeRetriever: image not found: {image_path}")
        return self._refs[:k]

    def retrieve_by_text(self, text: str, k: int = 5) -> list[RetrievedRef]:
        if not text.strip():
            raise ValueError("FakeRetriever.retrieve_by_text: empty query.")
        return self._refs[:k]
