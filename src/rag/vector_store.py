"""LanceDB wrapper — open / create / upsert / query.

OWNER: Person B
SPRINT CONCEPTS:
    - Sprint 3: LanceDB (vector store).
CONSUMES: ``lancedb``, ``pyarrow``, ``numpy``.
PROVIDES: ``open_db``, ``get_or_create_table``, ``upsert_records``, ``query_by_vector``.

WHY YOU CARE
------------
LanceDB is embedded — no separate server, no docker, no networking. It speaks
columnar Arrow under the hood, so 50 K vectors is sub-millisecond on a laptop.
For a hackathon, that means "no infra page" between us and the demo. Switch
back to Qdrant / Pinecone post-MVP if the corpus exceeds ~100 K rows.

LOGIC OUTLINE
-------------
1. ``open_db`` opens (or creates) the on-disk LanceDB at ``vector_store_dir``.
2. ``get_or_create_table`` builds a stable schema: id, vector(dim), image_path,
   source, tags(list[str]), description.
3. ``upsert_records`` deletes by id then adds (LanceDB has no native upsert).
4. ``query_by_vector`` runs a k-NN search and returns Python dicts.

DEFINITION OF DONE
------------------
[ ] tests/person_b/test_vector_store.py passes when lancedb is installed.
[ ] ``get_or_create_table(db, dim=512)`` is idempotent — call it twice
    against the same db, get the same handle.
[ ] ``upsert_records`` over the same id twice ends with one row, not two.
[ ] ``query_by_vector`` returns rows with a ``_distance`` field; the
    retriever converts that to ``score = 1 - distance``.

DO NOT
------
- Do not hard-code ``"design_references"``; use ``settings.vector_collection``.
- Do not store absolute image paths. Store paths *relative* to
  ``data/reference`` so the DB is portable between laptops.
- Do not run ``add()`` without first running ``delete()`` on the same ids;
  you will get duplicate rows.
- Do not skip the schema declaration. Letting LanceDB infer the schema from
  the first batch breaks when the second batch has slightly different keys.

SCHEMA REFERENCE (paste into your pyarrow schema)
-------------------------------------------------
    id           string         — sha1 of file bytes (stable across machines)
    vector       fixed-size-list[float32, dim]  — L2-normalized CLIP embedding
    image_path   string         — relative to data/reference; portable
    source       string         — e.g. "example-corp-2024" for the ingest run that wrote it
    tags         list[string]   — e.g. ["dashboard", "fintech"] — used to filter
    description  string         — optional human caption, "" by default
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    import lancedb
    import numpy as np

log = get_logger(__name__)


def open_db() -> "lancedb.DBConnection":
    """Open or create the LanceDB at ``settings.vector_store_dir``.

    Idempotent — safe to call from CLI, from tests, from the UI.
    """
    # HINT: three lines:
    #   import lancedb
    #   settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
    #   return lancedb.connect(str(settings.vector_store_dir))
    #
    # NOTE: LanceDB's connect() takes a string path or a URL. For local
    # development the path is a directory; for S3 it's "s3://bucket/prefix".
    # That swap is the production-path migration described in the plan.
    # TODO(person-b): implement.
    import lancedb

    from src.config import settings as current_settings

    current_settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(current_settings.vector_store_dir))


def get_or_create_table(
    db: "lancedb.DBConnection",
    *,
    name: str | None = None,
    dim: int,
) -> Any:
    """Return the table named ``name`` (created if absent).

    Schema:
        id: str, vector: vector(dim), image_path: str, source: str,
        tags: list[str], description: str.
    """
    # HINT: pyarrow schema (this is the part that bites everyone the first time):
    #   import pyarrow as pa
    #   schema = pa.schema([
    #       pa.field("id", pa.string()),
    #       pa.field("vector", pa.list_(pa.float32(), dim)),  # FIXED-SIZE list
    #       pa.field("image_path", pa.string()),
    #       pa.field("source", pa.string()),
    #       pa.field("tags", pa.list_(pa.string())),
    #       pa.field("description", pa.string()),
    #   ])
    #   target = name or settings.vector_collection
    #   if target in db.table_names():
    #       return db.open_table(target)
    #   return db.create_table(target, schema=schema)
    #
    # LOGIC: ``pa.list_(pa.float32(), dim)`` is the FIXED-size variant — that
    # is what LanceDB indexes for vector search. ``pa.list_(pa.float32())``
    # (without ``dim``) compiles but search is slow.
    # TODO(person-b): implement.
    import pyarrow as pa

    from src.config import settings as current_settings

    schema = pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
            pa.field("image_path", pa.string()),
            pa.field("source", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("description", pa.string()),
        ]
    )
    target = name or current_settings.vector_collection
    if target in db.table_names():
        return db.open_table(target)
    return db.create_table(target, schema=schema)


def upsert_records(table: Any, records: list[dict[str, Any]]) -> None:
    """Delete-by-id then add. Records must include 'id' and 'vector'."""
    # HINT: ~6 lines:
    #   if not records: return
    #   ids = [r["id"] for r in records]
    #   in_clause = ",".join(f"'{i}'" for i in ids)  # SQL-style escaping
    #   table.delete(f"id IN ({in_clause})")
    #   table.add(records)
    #
    # HINT: batch in chunks of 100 to keep memory flat:
    #   for chunk in (records[i:i+100] for i in range(0, len(records), 100)):
    #       upsert_records(table, chunk)
    #
    # PITFALL: LanceDB's delete() uses SQL-style strings; if any id contains
    # a single quote you must escape it. Stable hex hashes (sha1) avoid this.
    # TODO(person-b): implement.
    if not records:
        return

    for start in range(0, len(records), 100):
        chunk = records[start : start + 100]
        ids = [r["id"] for r in chunk]
        in_clause = ",".join(f"'{i.replace(chr(39), chr(39) + chr(39))}'" for i in ids)
        table.delete(f"id IN ({in_clause})")
        table.add(chunk)


def query_by_vector(
    table: Any,
    vector: "np.ndarray",
    k: int = 5,
    where: str | None = None,
) -> list[dict[str, Any]]:
    """Return the top-k matches as plain dicts."""
    # HINT: four lines:
    #   q = table.search(vector).metric("cosine").limit(k)
    #   if where: q = q.where(where)
    #   return q.to_list()
    #
    # NOTE: result rows have a ``_distance`` field. The retriever converts
    # that to ``score = 1 - _distance`` (cosine distance to similarity).
    # TODO(person-b): implement.
    q = table.search(vector).metric("cosine").limit(k)
    if where:
        q = q.where(where)
    return q.to_list()
