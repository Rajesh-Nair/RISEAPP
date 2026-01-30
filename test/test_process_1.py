"""Integration-style test for Process-1 (requires pymupdf, data/blob)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

pymupdf = pytest.importorskip("pymupdf", reason="pymupdf not installed")


def test_process_1_run() -> None:
    """Run Process-1 against data/blob; verify documents table updated."""
    from src.db import connection as conn_mod
    from src.db.connection import init_schema
    from src.db.repositories import documents_repo
    from src.processes.process_1_convert import run_process_1

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    def _get_connection(db_path=None):
        return conn

    with patch("src.processes.process_1_convert.get_connection", _get_connection), \
         patch.object(conn_mod, "get_connection", _get_connection), \
         patch.object(conn_mod, "_conn", conn), \
         patch.object(conn_mod, "_db_path", Path(":memory:")), \
         patch.object(documents_repo, "_conn", conn):
        init_schema(conn)
        run_process_1()
        docs = documents_repo.list_all()
        assert len(docs) >= 1, "Process-1 should upsert at least one document"
    conn.close()
    conn_mod._conn = None
    conn_mod._db_path = None
