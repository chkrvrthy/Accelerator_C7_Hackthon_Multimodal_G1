"""LanceDB upsert + query against a tmp directory (Person B owns the body)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.person_b


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
