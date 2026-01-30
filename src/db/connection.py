"""SQLite connection and schema init."""

import sqlite3
from pathlib import Path
from typing import Optional

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger
from utils.config import get_config

logger = CustomLogger().get_logger(__file__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relative_path TEXT NOT NULL UNIQUE,
    doc_type TEXT NOT NULL,
    name TEXT NOT NULL,
    has_pdf INTEGER NOT NULL DEFAULT 0,
    has_html INTEGER NOT NULL DEFAULT 0,
    has_md INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_chunk_id TEXT NOT NULL REFERENCES chunks(id),
    external_chunk_id TEXT NOT NULL REFERENCES chunks(id),
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_lineage_internal ON lineage(internal_chunk_id);
CREATE INDEX IF NOT EXISTS idx_lineage_external ON lineage(external_chunk_id);
"""

_conn: Optional[sqlite3.Connection] = None
_db_path: Optional[Path] = None


def get_db_path() -> Path:
    cfg = get_config()
    base = cfg.data_sql
    base.mkdir(parents=True, exist_ok=True)
    return base / "riseapp.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    global _conn, _db_path
    path = db_path or get_db_path()
    if _conn is not None and _db_path == path:
        return _conn
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _conn = sqlite3.connect(str(path))
        _conn.row_factory = sqlite3.Row
        _db_path = path
        return _conn
    except Exception as e:
        raise CustomException(f"Failed to connect to DB at {path}: {e}")


def init_schema(conn: Optional[sqlite3.Connection] = None) -> None:
    c = conn or get_connection()
    c.executescript(SCHEMA)
    c.commit()
    logger.info("Schema initialized")
