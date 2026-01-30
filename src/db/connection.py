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
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    converted_at TEXT,
    chunked_at TEXT,
    lineage_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    lineage_processed_at TEXT
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

MIGRATIONS = """
-- Add processing tracking columns to documents table if they don't exist
PRAGMA foreign_keys=off;

-- Check and add converted_at column
SELECT CASE 
    WHEN COUNT(*) = 0 THEN 
        'ALTER TABLE documents ADD COLUMN converted_at TEXT'
    ELSE 'SELECT 1'
END as sql
FROM pragma_table_info('documents') 
WHERE name='converted_at';

-- Check and add chunked_at column
SELECT CASE 
    WHEN COUNT(*) = 0 THEN 
        'ALTER TABLE documents ADD COLUMN chunked_at TEXT'
    ELSE 'SELECT 1'
END as sql
FROM pragma_table_info('documents') 
WHERE name='chunked_at';

-- Check and add lineage_at column
SELECT CASE 
    WHEN COUNT(*) = 0 THEN 
        'ALTER TABLE documents ADD COLUMN lineage_at TEXT'
    ELSE 'SELECT 1'
END as sql
FROM pragma_table_info('documents') 
WHERE name='lineage_at';

-- Check and add lineage_processed_at column to chunks
SELECT CASE 
    WHEN COUNT(*) = 0 THEN 
        'ALTER TABLE chunks ADD COLUMN lineage_processed_at TEXT'
    ELSE 'SELECT 1'
END as sql
FROM pragma_table_info('chunks') 
WHERE name='lineage_processed_at';

PRAGMA foreign_keys=on;
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
        # check_same_thread=False so the connection can be used from FastAPI worker threads
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _db_path = path
        return _conn
    except Exception as e:
        raise CustomException(f"Failed to connect to DB at {path}: {e}")


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run migrations to add new columns to existing tables."""
    try:
        # Check and add converted_at to documents
        cursor = conn.execute("PRAGMA table_info(documents)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "converted_at" not in columns:
            conn.execute("ALTER TABLE documents ADD COLUMN converted_at TEXT")
            logger.info("Added converted_at column to documents table")
        
        if "chunked_at" not in columns:
            conn.execute("ALTER TABLE documents ADD COLUMN chunked_at TEXT")
            logger.info("Added chunked_at column to documents table")
        
        if "lineage_at" not in columns:
            conn.execute("ALTER TABLE documents ADD COLUMN lineage_at TEXT")
            logger.info("Added lineage_at column to documents table")
        
        # Check and add lineage_processed_at to chunks
        cursor = conn.execute("PRAGMA table_info(chunks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "lineage_processed_at" not in columns:
            conn.execute("ALTER TABLE chunks ADD COLUMN lineage_processed_at TEXT")
            logger.info("Added lineage_processed_at column to chunks table")

        if "start_offset" not in columns:
            conn.execute("ALTER TABLE chunks ADD COLUMN start_offset INTEGER")
            logger.info("Added start_offset column to chunks table")

        if "end_offset" not in columns:
            conn.execute("ALTER TABLE chunks ADD COLUMN end_offset INTEGER")
            logger.info("Added end_offset column to chunks table")
        
        conn.commit()
    except Exception as e:
        logger.warning("Migration check/execution issue", error=str(e))


def init_schema(conn: Optional[sqlite3.Connection] = None) -> None:
    c = conn or get_connection()
    c.executescript(SCHEMA)
    c.commit()
    _run_migrations(c)
    logger.info("Schema initialized")
