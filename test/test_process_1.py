"""Integration-style test for Process-1 (requires pymupdf, data/blob)."""

import tempfile
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf", reason="pymupdf not installed")


def test_process_1_run() -> None:
    """Run Process-1 against data/blob; verify documents table updated."""
    from src.db.connection import get_connection, init_schema
    from src.db.repositories import documents_repo
    from src.processes.process_1_convert import run_process_1

    init_schema(get_connection())
    run_process_1()
    docs = documents_repo.list_all()
    assert len(docs) >= 1
    with_md = [d for d in docs if d.has_md]
    assert len(with_md) >= 1
