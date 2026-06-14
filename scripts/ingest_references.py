"""Ingest CLI — walk ``data/reference``, embed every image, write to LanceDB.

OWNER: Person B
USAGE
-----
    python -m scripts.ingest_references --source ./data/reference --tag example-corp
    python -m scripts.ingest_references --clear     # drop and recreate the table

WHY THIS LIVES OUTSIDE ``src/``
------------------------------
``src/`` is library code — imported by tests, the UI, the MCP server.
``scripts/`` is operator code — run by humans on the command line. Mixing
them invites circular imports and "why did my test boot a model?"

WHAT IT DOES
------------
For every image under ``--source``:
  1. Compute SHA1 of file bytes (stable id; survives renames).
  2. Embed via ``CLIPEmbedder.embed_image``.
  3. Upsert into the LanceDB table with metadata (source, tag, description).

Re-running is idempotent — same id means an existing row is replaced, not
duplicated.

DEFINITION OF DONE
------------------
[ ] ``make ingest`` populates LanceDB from ``data/reference/*.png``.
[ ] Re-running does NOT create duplicates (count() unchanged).
[ ] ``--clear`` drops and recreates the table cleanly.
[ ] After ingest, ``python -m src.rag.retriever --text "fintech dashboard"``
    returns ≥ 3 hits with score > 0.2 (depends on the corpus).
[ ] Rich progress bar shows during ingest (judges love a polished CLI).

DO NOT
------
- Do not embed images one at a time — use ``embed_batch`` for bulk.
- Do not store absolute paths. Store paths relative to ``data/reference``
  so the LanceDB is portable between teammates' machines.
- Do not skip the SHA1 id — random UUIDs would explode the cache after one
  re-ingest and judges would notice the duplicate hits.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import sys
from pathlib import Path

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _stable_id(path: Path) -> str:
    """SHA1 of file bytes — stable id so we can skip-if-already-ingested."""
    return hashlib.sha1(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest reference designs into LanceDB.")
    parser.add_argument("--source", default=str(settings.reference_dir))
    parser.add_argument("--clear", action="store_true", help="Drop and recreate the table.")
    parser.add_argument("--tag", default="", help="Tag applied to all rows from this run.")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    if not source.exists():
        log.error("source directory %s does not exist", source)
        return 2

    # HINT: full pipeline (~25 lines, paste and adapt):
    #
    #   from src.rag.embedder import CLIPEmbedder
    #   from src.rag.vector_store import open_db, get_or_create_table, upsert_records
    #
    #   embedder = CLIPEmbedder()
    #   db = open_db()
    #   if args.clear:
    #       try: db.drop_table(settings.vector_collection)
    #       except Exception: pass  # table may not exist
    #   table = get_or_create_table(db, dim=embedder.dim)
    #
    #   files = sorted(p for p in source.rglob("*") if p.suffix.lower() in SUPPORTED_EXTS)
    #   if not files:
    #       log.warning("no supported images under %s", source)
    #       return 0
    #
    #   # HINT: use rich for the progress bar (already in base.txt):
    #   from rich.progress import track
    #
    #   records = []
    #   # HINT: batch embedding for speed.
    #   for batch in (files[i:i + args.batch_size]
    #                 for i in range(0, len(files), args.batch_size)):
    #       vecs = embedder.embed_batch(batch)
    #       for p, v in zip(batch, vecs):
    #           records.append({
    #               "id": _stable_id(p),
    #               "vector": v.tolist(),                     # numpy → JSON-serialisable
    #               "image_path": str(p.relative_to(source.parent)),
    #               "source": source.name,
    #               "tags": [args.tag] if args.tag else [],
    #               "description": "",
    #           })
    #   upsert_records(table, records)
    #   log.info("ingest: wrote %d records (tag=%s)", len(records), args.tag)
    #   return 0
    #
    # NOTE: relative path uses ``source.parent`` so paths are portable
    # ("reference/foo.png" instead of e.g. "/home/<user>/.../foo.png" on
    # Linux/Mac or "C:\\Users\\<user>\\...\\foo.png" on Windows).

    # TODO(person-b): paste the recipe above and run `make ingest`.
    from rich.progress import track

    from src.rag.embedder import CLIPEmbedder
    from src.rag.vector_store import get_or_create_table, open_db, upsert_records

    embedder = CLIPEmbedder()
    db = open_db()
    if args.clear:
        with contextlib.suppress(Exception):
            db.drop_table(settings.vector_collection)
    table = get_or_create_table(db, dim=embedder.dim)

    files = sorted(p for p in source.rglob("*") if p.suffix.lower() in SUPPORTED_EXTS)
    if not files:
        log.warning("no supported images under %s", source)
        return 0

    records = []
    batches = [files[i : i + args.batch_size] for i in range(0, len(files), args.batch_size)]
    for batch in track(batches, description="Embedding references"):
        vecs = embedder.embed_batch(batch)
        for p, v in zip(batch, vecs, strict=True):
            records.append(
                {
                    "id": _stable_id(p),
                    "vector": v.tolist(),
                    "image_path": str(p.relative_to(source.parent)),
                    "source": source.name,
                    "tags": [args.tag] if args.tag else [],
                    "description": "",
                }
            )
    upsert_records(table, records)
    log.info("ingest: wrote %d records (tag=%s)", len(records), args.tag)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
