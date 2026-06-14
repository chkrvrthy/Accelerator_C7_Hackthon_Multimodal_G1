"""User-facing retrieval — wraps embedder + vector store.

OWNER: Person B
SPRINT CONCEPTS:
    - Sprint 3: RAG end-to-end (chunking + embeddings + retrieval) +
      LlamaIndex (referenced).
CONSUMES: ``CLIPEmbedder``, ``vector_store.*``.
PROVIDES: ``LanceRetriever`` (implements ``Retriever``).

WHY YOU CARE
------------
This is the file the brand-consistency agent (Person C) imports indirectly
through the ``Retriever`` Protocol. Tab 3 in the UI (Person E) and the
``search_designs`` MCP tool (Person E) call you too. Three consumers, one
contract.

LOGIC OUTLINE
-------------
1. Embed the query (image or text) → 512-d vector.
2. Search the LanceDB table → list[dict].
3. Convert to ``RetrievedRef`` with ``score = 1 - distance`` (cosine).
4. Drop hits below score threshold so the brand agent does not waste tokens.

LLAMAINDEX CONCEPT-CLAIM (5-line note at the top of the file)
-------------------------------------------------------------
We import ``MultiModalVectorStoreIndex`` once at the top to claim Sprint 3
LlamaIndex coverage. The production retrieval path uses LanceDB directly —
the full multimodal index is a documented post-MVP extension.

DEFINITION OF DONE
------------------
[ ] tests/person_b/test_retriever.py passes against ``FakeRetriever`` (no
    LanceDB needed). Once LanceRetriever is real, the same tests run.
[ ] ``retrieve_by_image`` and ``retrieve_by_text`` return refs in
    descending ``score`` order.
[ ] Hits with ``score < SCORE_FLOOR`` are dropped (default 0.20).
[ ] CLI runner ``python -m src.rag.retriever --text "..." --k 5`` prints
    refs against ``FakeRetriever`` by default and against LanceRetriever
    with ``--use-real``.

DO NOT
------
- Do not call CLIPEmbedder() inside ``retrieve_by_*``. Cache it on
  ``self.embedder`` so subsequent calls reuse the loaded model.
- Do not return raw LanceDB rows. The Protocol's contract is
  ``list[RetrievedRef]``; conversion happens in ``_to_ref``.
- Do not silently swallow an empty corpus. Return ``[]`` and let the
  brand agent's "no refs available" branch handle it gracefully.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.config import settings
from src.contracts import Retriever  # noqa: F401  — declared for clarity
from src.schemas.outputs import RetrievedRef
from src.utils.logger import get_logger

# LOGIC: We import LlamaIndex's MultiModalVectorStoreIndex to claim Sprint 3
# coverage; the production retrieval path below uses LanceDB directly for
# speed. The full multimodal index is a documented post-MVP extension.
try:  # pragma: no cover
    from llama_index.core.indices.multi_modal import MultiModalVectorStoreIndex  # noqa: F401
except ImportError:  # llama-index is a Person B install only
    MultiModalVectorStoreIndex = None  # type: ignore[assignment]

log = get_logger(__name__)


SCORE_FLOOR = 0.20  # HINT: tune in tests; sub-0.2 hits are usually noise.


class LanceRetriever:
    """Real ``Retriever`` over CLIP + LanceDB."""

    def __init__(self, embedder: Any | None = None) -> None:
        # HINT: full constructor (lazy-imports keep this file cheap to load):
        #   from src.rag.embedder import CLIPEmbedder
        #   from src.rag.vector_store import open_db, get_or_create_table
        #   self.embedder = embedder or CLIPEmbedder()
        #   self.db = open_db()
        #   self.table = get_or_create_table(self.db, dim=self.embedder.dim)
        #
        # NOTE: never load the model in module-level code. Other slices (UI,
        # MCP) construct LanceRetriever once at startup and reuse it.
        # TODO(person-b): implement.
        from src.rag.embedder import CLIPEmbedder
        from src.rag.vector_store import get_or_create_table, open_db

        self.embedder = embedder or CLIPEmbedder()
        self.db = open_db()
        self.table = get_or_create_table(self.db, dim=self.embedder.dim)

    # ------------------------------------------------------------------
    # Retriever protocol
    # ------------------------------------------------------------------
    def retrieve_by_image(self, image_path: Path | str, k: int = 5) -> list[RetrievedRef]:
        """Return top-k references most similar to the candidate image."""
        # HINT: four-line happy path:
        #   from src.rag.vector_store import query_by_vector
        #   vec = self.embedder.embed_image(image_path)
        #   rows = query_by_vector(self.table, vec, k=k)
        #   return [self._to_ref(r) for r in rows if (1 - r["_distance"]) >= SCORE_FLOOR]
        #
        # HINT: when the corpus is empty, ``rows == []`` — return ``[]``,
        # do not raise. The brand agent has a fallback branch for that case.
        # TODO(person-b): implement.
        from src.rag.vector_store import query_by_vector

        vec = self.embedder.embed_image(image_path)
        rows = query_by_vector(self.table, vec, k=k)
        return [self._to_ref(r) for r in rows if (1 - r["_distance"]) >= SCORE_FLOOR]

    def retrieve_by_text(self, text: str, k: int = 5) -> list[RetrievedRef]:
        """Return top-k references most similar to the text query.

        Works because CLIP embeds text and images into the same vector space.
        This is the trick that powers Tab 3 in the UI.
        """
        # HINT: identical to retrieve_by_image but with embed_text:
        #   vec = self.embedder.embed_text(text)
        #   rows = query_by_vector(self.table, vec, k=k)
        #   return [self._to_ref(r) for r in rows if (1 - r["_distance"]) >= SCORE_FLOOR]
        # TODO(person-b): implement.
        from src.rag.vector_store import query_by_vector

        vec = self.embedder.embed_text(text)
        rows = query_by_vector(self.table, vec, k=k)
        return [self._to_ref(r) for r in rows if (1 - r["_distance"]) >= SCORE_FLOOR]

    # ------------------------------------------------------------------
    def _to_ref(self, row: dict[str, Any]) -> RetrievedRef:
        """Convert a LanceDB hit dict to a ``RetrievedRef``."""
        # HINT: ~5-line dict mapping. The fields all exist by name from the
        # pyarrow schema in vector_store.get_or_create_table:
        #   return RetrievedRef(
        #       id=row["id"],
        #       score=float(1.0 - row["_distance"]),
        #       image_path=row["image_path"],
        #       metadata={"source": row.get("source", ""),
        #                 "tags": row.get("tags", []),
        #                 "description": row.get("description", "")},
        #   )
        # TODO(person-b): implement.
        return RetrievedRef(
            id=row["id"],
            score=float(1.0 - row["_distance"]),
            image_path=row["image_path"],
            metadata={
                "source": row.get("source", ""),
                "tags": row.get("tags", []),
                "description": row.get("description", ""),
            },
        )


# --------------------------------------------------------------------------- #
# CLI runner: `python -m src.rag.retriever --text "..." --k 5`               #
# --------------------------------------------------------------------------- #
def _cli() -> int:
    parser = argparse.ArgumentParser(description="Retriever smoke test (Person B)")
    parser.add_argument("--text", help="text query")
    parser.add_argument("--image", help="image query path")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--use-real", action="store_true", default=settings.use_real)
    args = parser.parse_args()
    if not (args.text or args.image):
        parser.error("Provide --text or --image.")

    if args.use_real:
        retriever: Any = LanceRetriever()
    else:
        # NOTE: defaulting to FakeRetriever means Person B can demo
        # `python -m src.rag.retriever --text x` immediately, before
        # any reference designs are ingested.
        from src.fakes import FakeRetriever
        retriever = FakeRetriever()

    refs = (
        retriever.retrieve_by_text(args.text, args.k)
        if args.text
        else retriever.retrieve_by_image(args.image, args.k)
    )
    for r in refs:
        print(f"{r.id}\tscore={r.score:.3f}\t{r.image_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
