"""Tests for DB schema and repos."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.db.connection import init_schema
from src.db.repositories import DocumentsRepo, ChunksRepo, LineageRepo


@pytest.fixture
def db_conn():
    path = Path(tempfile.gettempdir()) / "riseapp_test_db.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def test_documents_upsert(db_conn) -> None:
    repo = DocumentsRepo(conn=db_conn)
    id1 = repo.upsert("external/foo/foo", "external", "foo", True, True, True)
    assert id1 > 0
    id2 = repo.upsert("external/foo/foo", "external", "foo", True, True, True)
    assert id2 == id1
    row = repo.get_by_path("external/foo/foo")
    assert row is not None
    assert row.doc_type == "external"


def test_chunks_and_lineage(db_conn) -> None:
    doc = DocumentsRepo(conn=db_conn)
    chunk = ChunksRepo(conn=db_conn)
    lin = LineageRepo(conn=db_conn)
    doc_id_int = doc.upsert("internal/bar/bar", "internal", "bar", True, True, True)
    doc_id_ext = doc.upsert("external/ext/ext", "external", "ext", True, True, True)
    chunk.insert("bar_0", doc_id_int, 0, "internal chunk text")
    chunk.insert("ext_0", doc_id_ext, 0, "external chunk text")
    lid = lin.insert("bar_0", "ext_0", 0.9)
    assert lid > 0
    rows = lin.list_by_internal("bar_0")
    assert len(rows) == 1
    assert rows[0].external_chunk_id == "ext_0"
