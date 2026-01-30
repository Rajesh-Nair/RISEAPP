"""CRUD for documents, chunks, lineage."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger
from src.db.connection import get_connection, init_schema

logger = CustomLogger().get_logger(__file__)


@dataclass
class DocumentRow:
    id: int
    relative_path: str
    doc_type: str
    name: str
    has_pdf: bool
    has_html: bool
    has_md: bool
    created_at: str
    updated_at: str
    converted_at: Optional[str] = None
    chunked_at: Optional[str] = None
    lineage_at: Optional[str] = None


@dataclass
class ChunkRow:
    id: str
    document_id: int
    chunk_index: int
    content: str
    metadata: Optional[str]
    created_at: str
    lineage_processed_at: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None


@dataclass
class LineageRow:
    id: int
    internal_chunk_id: str
    external_chunk_id: str
    confidence: Optional[float]
    created_at: str


def _get(r: Any, key: str, default: Any = None) -> Any:
    """Get key from row (dict or sqlite3.Row)."""
    if hasattr(r, "get"):
        return r.get(key, default)
    return r[key] if key in r.keys() else default


def _row_to_doc(r: Any) -> DocumentRow:
    return DocumentRow(
        id=r["id"],
        relative_path=r["relative_path"],
        doc_type=r["doc_type"],
        name=r["name"],
        has_pdf=bool(r["has_pdf"]),
        has_html=bool(r["has_html"]),
        has_md=bool(r["has_md"]),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        converted_at=_get(r, "converted_at"),
        chunked_at=_get(r, "chunked_at"),
        lineage_at=_get(r, "lineage_at"),
    )


def _row_to_chunk(r: Any) -> ChunkRow:
    return ChunkRow(
        id=r["id"],
        document_id=r["document_id"],
        chunk_index=r["chunk_index"],
        content=r["content"],
        metadata=r["metadata"],
        created_at=r["created_at"],
        lineage_processed_at=_get(r, "lineage_processed_at"),
        start_offset=_get(r, "start_offset"),
        end_offset=_get(r, "end_offset"),
    )


def _row_to_lineage(r: Any) -> LineageRow:
    return LineageRow(
        id=r["id"],
        internal_chunk_id=r["internal_chunk_id"],
        external_chunk_id=r["external_chunk_id"],
        confidence=r["confidence"],
        created_at=r["created_at"],
    )


class DocumentsRepo:
    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def upsert(
        self,
        relative_path: str,
        doc_type: str,
        name: str,
        has_pdf: bool,
        has_html: bool,
        has_md: bool,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO documents (relative_path, doc_type, name, has_pdf, has_html, has_md, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(relative_path) DO UPDATE SET
                has_pdf=excluded.has_pdf, has_html=excluded.has_html, has_md=excluded.has_md,
                updated_at=datetime('now')
            """,
            (relative_path, doc_type, name, int(has_pdf), int(has_html), int(has_md)),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT id FROM documents WHERE relative_path = ?", (relative_path,)).fetchone()
        return row["id"]

    def get_by_path(self, relative_path: str) -> Optional[DocumentRow]:
        r = self._conn.execute("SELECT * FROM documents WHERE relative_path = ?", (relative_path,)).fetchone()
        return _row_to_doc(r) if r else None

    def get_by_id(self, doc_id: int) -> Optional[DocumentRow]:
        r = self._conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return _row_to_doc(r) if r else None

    def list_with_md(self, doc_type: Optional[str] = None) -> List[DocumentRow]:
        if doc_type:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE has_md = 1 AND doc_type = ? ORDER BY id",
                (doc_type,),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM documents WHERE has_md = 1 ORDER BY id").fetchall()
        return [_row_to_doc(r) for r in rows]

    def list_all(self) -> List[DocumentRow]:
        rows = self._conn.execute("SELECT * FROM documents ORDER BY id").fetchall()
        return [_row_to_doc(r) for r in rows]

    def list_unprocessed_for_chunking(self) -> List[DocumentRow]:
        """Get docs with MD that haven't been chunked or were updated after chunking."""
        rows = self._conn.execute(
            """
            SELECT * FROM documents 
            WHERE has_md = 1 
            AND (chunked_at IS NULL OR updated_at > chunked_at)
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_doc(r) for r in rows]

    def mark_chunked(self, doc_id: int) -> None:
        """Set chunked_at = datetime('now')."""
        self._conn.execute(
            "UPDATE documents SET chunked_at = datetime('now') WHERE id = ?",
            (doc_id,),
        )
        self._conn.commit()

    def mark_converted(self, doc_id: int) -> None:
        """Set converted_at = datetime('now')."""
        self._conn.execute(
            "UPDATE documents SET converted_at = datetime('now') WHERE id = ?",
            (doc_id,),
        )
        self._conn.commit()


class ChunksRepo:
    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def insert(
        self,
        chunk_id: str,
        document_id: int,
        chunk_index: int,
        content: str,
        metadata: Optional[dict] = None,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
    ) -> None:
        meta_str = json.dumps(metadata) if metadata else None
        self._conn.execute(
            """INSERT OR REPLACE INTO chunks
               (id, document_id, chunk_index, content, metadata, start_offset, end_offset)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chunk_id, document_id, chunk_index, content, meta_str, start_offset, end_offset),
        )
        self._conn.commit()

    def get(self, chunk_id: str) -> Optional[ChunkRow]:
        r = self._conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        return _row_to_chunk(r) if r else None

    def list_by_document(self, document_id: int) -> List[ChunkRow]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        ).fetchall()
        return [_row_to_chunk(r) for r in rows]

    def list_internal_chunks(self) -> List[ChunkRow]:
        rows = self._conn.execute(
            """
            SELECT c.* FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.doc_type = 'internal'
            ORDER BY c.document_id, c.chunk_index
            """
        ).fetchall()
        return [_row_to_chunk(r) for r in rows]

    def list_external_chunk_ids(self) -> List[str]:
        rows = self._conn.execute(
            """
            SELECT c.id FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.doc_type = 'external'
            ORDER BY c.id
            """
        ).fetchall()
        return [r["id"] for r in rows]

    def delete_by_document(self, document_id: int) -> int:
        cur = self._conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        self._conn.commit()
        return cur.rowcount

    def list_unprocessed_internal_chunks(self) -> List[ChunkRow]:
        """Get internal chunks where lineage_processed_at IS NULL."""
        rows = self._conn.execute(
            """
            SELECT c.* FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.doc_type = 'internal'
            AND c.lineage_processed_at IS NULL
            ORDER BY c.document_id, c.chunk_index
            """
        ).fetchall()
        return [_row_to_chunk(r) for r in rows]

    def mark_lineage_processed(self, chunk_id: str) -> None:
        """Set lineage_processed_at = datetime('now')."""
        self._conn.execute(
            "UPDATE chunks SET lineage_processed_at = datetime('now') WHERE id = ?",
            (chunk_id,),
        )
        self._conn.commit()


class LineageRepo:
    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def insert(self, internal_chunk_id: str, external_chunk_id: str, confidence: Optional[float] = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO lineage (internal_chunk_id, external_chunk_id, confidence) VALUES (?, ?, ?)",
            (internal_chunk_id, external_chunk_id, confidence),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_by_internal(self, internal_chunk_id: str) -> List[LineageRow]:
        rows = self._conn.execute(
            "SELECT * FROM lineage WHERE internal_chunk_id = ? ORDER BY id",
            (internal_chunk_id,),
        ).fetchall()
        return [_row_to_lineage(r) for r in rows]

    def list_by_external(self, external_chunk_id: str) -> List[LineageRow]:
        rows = self._conn.execute(
            "SELECT * FROM lineage WHERE external_chunk_id = ? ORDER BY id",
            (external_chunk_id,),
        ).fetchall()
        return [_row_to_lineage(r) for r in rows]

    def clear_all(self) -> int:
        cur = self._conn.execute("DELETE FROM lineage")
        self._conn.commit()
        return cur.rowcount

    def delete_by_internal_chunk(self, internal_chunk_id: str) -> int:
        """Delete all lineage entries for a specific internal chunk."""
        cur = self._conn.execute(
            "DELETE FROM lineage WHERE internal_chunk_id = ?",
            (internal_chunk_id,),
        )
        self._conn.commit()
        return cur.rowcount


documents_repo = DocumentsRepo()
chunks_repo = ChunksRepo()
lineage_repo = LineageRepo()
