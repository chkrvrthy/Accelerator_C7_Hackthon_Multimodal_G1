"""LanceDB upsert + query against a tmp directory (Person B owns the body)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.person_b


class _FakeQuery:
    def __init__(self) -> None:
        self.metric_name = ""
        self.k = 0
        self.where_clause = None

    def metric(self, name: str):
        self.metric_name = name
        return self

    def limit(self, k: int):
        self.k = k
        return self

    def where(self, clause: str):
        self.where_clause = clause
        return self

    def to_list(self):
        return [{"id": "a", "_distance": 0.1}]


class _FakeTable:
    def __init__(self) -> None:
        self.deleted = []
        self.added = []
        self.query = _FakeQuery()

    def delete(self, where: str) -> None:
        self.deleted.append(where)

    def add(self, records: list[dict]) -> None:
        self.added.extend(records)

    def search(self, vector):
        self.vector = vector
        return self.query


@pytest.mark.slow
def test_open_db_creates_directory(tmp_settings):
    pytest.importorskip("lancedb")
    from src.rag.vector_store import open_db

    db = open_db()
    assert tmp_settings.vector_store_dir.exists()
    assert db is not None


@pytest.mark.slow
def test_get_or_create_table_idempotent(tmp_settings):
    pytest.importorskip("lancedb")
    from src.rag.vector_store import get_or_create_table, open_db

    db = open_db()
    t1 = get_or_create_table(db, dim=512)
    t2 = get_or_create_table(db, dim=512)
    assert t1.name == t2.name


def test_upsert_records_deletes_before_add():
    from src.rag.vector_store import upsert_records

    table = _FakeTable()
    upsert_records(table, [{"id": "a", "vector": [1.0]}, {"id": "b", "vector": [0.0]}])
    assert table.deleted == ["id IN ('a','b')"]
    assert [r["id"] for r in table.added] == ["a", "b"]


def test_query_by_vector_uses_cosine_limit_and_where():
    from src.rag.vector_store import query_by_vector

    table = _FakeTable()
    rows = query_by_vector(table, [1.0, 0.0], k=3, where="source = 'demo'")
    assert rows == [{"id": "a", "_distance": 0.1}]
    assert table.query.metric_name == "cosine"
    assert table.query.k == 3
    assert table.query.where_clause == "source = 'demo'"
