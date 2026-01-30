"""Tests for REST API (documents, content, chunks, process, upload)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.db.connection import get_connection, init_schema
from src.db import connection as conn_module
from src.db.repositories import documents_repo, chunks_repo, lineage_repo

_project_root = Path(__file__).resolve().parent.parent


def _sanitize_node_name(name: str) -> str:
    """Replace characters invalid in Windows paths."""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name)


@pytest.fixture
def test_db_and_blob(request):
    """Create temp DB and blob dir under project test/tmp; patch config and connection."""
    tmp_path = _project_root / "test" / "tmp" / "api" / _sanitize_node_name(request.node.name)
    tmp_path.mkdir(parents=True, exist_ok=True)
    blob = tmp_path / "blob"
    sql_dir = tmp_path / "sql"
    blob.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)
    (blob / "external").mkdir(parents=True, exist_ok=True)
    (blob / "internal").mkdir(parents=True, exist_ok=True)

    config = MagicMock()
    config.data_blob = blob
    config.data_sql = sql_dir
    config.data_vectordb = tmp_path / "vectordb"
    config.project_root = tmp_path

    db_file = sql_dir / "riseapp.db"
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    conn_module._conn = conn
    conn_module._db_path = db_file
    documents_repo._conn = conn
    chunks_repo._conn = conn
    lineage_repo._conn = conn
    with patch("utils.config.get_config", return_value=config), patch(
        "src.api.app.get_config", return_value=config
    ):
        yield tmp_path, blob, sql_dir, conn, config


@pytest.fixture
def seeded_db(test_db_and_blob):
    """DB with one external and one internal doc, chunks, and lineage."""
    tmp_path, blob, sql_dir, conn, config = test_db_and_blob
    conn.execute("DELETE FROM lineage")
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM documents")
    conn.commit()
    # Insert documents
    conn.execute(
        "INSERT INTO documents (relative_path, doc_type, name, has_pdf, has_html, has_md) VALUES (?,?,?,?,?,?)",
        ("external/foo/foo", "external", "foo", 1, 1, 1),
    )
    conn.execute(
        "INSERT INTO documents (relative_path, doc_type, name, has_pdf, has_html, has_md) VALUES (?,?,?,?,?,?)",
        ("internal/bar/bar", "internal", "bar", 1, 1, 1),
    )
    conn.commit()
    ext_id = conn.execute("SELECT id FROM documents WHERE relative_path = ?", ("external/foo/foo",)).fetchone()[0]
    int_id = conn.execute("SELECT id FROM documents WHERE relative_path = ?", ("internal/bar/bar",)).fetchone()[0]
    # Chunks
    conn.execute(
        "INSERT OR REPLACE INTO chunks (id, document_id, chunk_index, content, metadata) VALUES (?,?,?,?,?)",
        (f"{ext_id}_0", ext_id, 0, "external chunk content", None),
    )
    conn.execute(
        "INSERT OR REPLACE INTO chunks (id, document_id, chunk_index, content, metadata) VALUES (?,?,?,?,?)",
        (f"{int_id}_0", int_id, 0, "internal chunk content", None),
    )
    conn.execute(
        "INSERT INTO lineage (internal_chunk_id, external_chunk_id, confidence) VALUES (?,?,?)",
        (f"{int_id}_0", f"{ext_id}_0", 0.9),
    )
    conn.commit()
    # Create blob files for external/foo/foo
    (blob / "external" / "foo").mkdir(parents=True, exist_ok=True)
    (blob / "external" / "foo" / "foo.html").write_text("<p>foo</p>", encoding="utf-8")
    (blob / "external" / "foo" / "foo.md").write_text("# foo", encoding="utf-8")
    (blob / "internal" / "bar").mkdir(parents=True, exist_ok=True)
    (blob / "internal" / "bar" / "bar.html").write_text("<p>bar</p>", encoding="utf-8")
    (blob / "internal" / "bar" / "bar.md").write_text("# bar", encoding="utf-8")

    yield {"ext_id": ext_id, "int_id": int_id, "conn": conn, "blob": blob, "config": config}


@pytest.mark.asyncio
async def test_list_documents_empty(test_db_and_blob):
    tmp_path, blob, sql_dir, conn, config = test_db_and_blob
    # test_db_and_blob already sets repo._conn
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/documents")
        assert r.status_code == 200
        data = r.json()
        assert data == []


@pytest.mark.asyncio
async def test_list_documents_with_data(seeded_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/documents")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert "foo" in names and "bar" in names
        r2 = await client.get("/api/documents?doc_type=external")
        assert r2.status_code == 200
        assert len(r2.json()) == 1
        assert r2.json()[0]["doc_type"] == "external"


@pytest.mark.asyncio
async def test_get_document_content(seeded_db):
    ext_id = seeded_db["ext_id"]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get(f"/api/documents/{ext_id}/content?format=html")
        assert r.status_code == 200
        assert "<p>foo</p>" in r.text or "foo" in r.text
        r2 = await client.get(f"/api/documents/{ext_id}/content?format=md")
        assert r2.status_code == 200
        assert "foo" in r2.text
        r3 = await client.get(f"/api/documents/99999/content?format=html")
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_get_document_chunks(seeded_db):
    ext_id = seeded_db["ext_id"]
    int_id = seeded_db["int_id"]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get(f"/api/documents/{ext_id}/chunks")
        assert r.status_code == 200
        chunks = r.json()
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == f"{ext_id}_0"
        assert chunks[0]["linked_chunk_ids"] == [f"{int_id}_0"]
        r2 = await client.get(f"/api/documents/{int_id}/chunks")
        assert r2.status_code == 200
        assert r2.json()[0]["linked_chunk_ids"] == [f"{ext_id}_0"]


@pytest.mark.asyncio
async def test_get_chunk_by_id(seeded_db):
    ext_id = seeded_db["ext_id"]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get(f"/api/chunks/{ext_id}_0")
        assert r.status_code == 200
        data = r.json()
        assert data["chunk_id"] == f"{ext_id}_0"
        assert "external chunk content" in data["content"]
        assert data["document"]["name"] == "foo"
        r2 = await client.get("/api/chunks/invalid")
        assert r2.status_code == 400
        r3 = await client.get("/api/chunks/999_0")
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_process_1_already_processed(seeded_db):
    """When no unconverted PDFs exist, process 1 returns already_processed."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/api/process/1", json={"force": False})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("already_processed", "completed")
        if data["status"] == "already_processed":
            assert data.get("force_available") is True


@pytest.mark.asyncio
async def test_upload_pdf(test_db_and_blob):
    tmp_path, blob, sql_dir, conn, config = test_db_and_blob
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        pdf_content = b"%PDF-1.4 fake"
        files = {"file": ("test.pdf", pdf_content, "application/pdf")}
        data = {"doc_type": "external"}
        r = await client.post("/api/upload", files=files, data=data)
        assert r.status_code == 201
        body = r.json()
        assert body["doc_type"] == "external"
        assert "external/test/test" in body["path"]
        assert (blob / "external" / "test" / "test.pdf").exists()
        assert (blob / "external" / "test" / "test.pdf").read_bytes() == pdf_content
