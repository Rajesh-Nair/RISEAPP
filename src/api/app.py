"""FastAPI app: documents, content, chunks, process, upload."""

import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from fastapi import APIRouter, FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


class ProcessRequest(BaseModel):
    force: bool = False

from utils.config import get_config
from src.db.connection import get_connection, init_schema
from src.db.repositories import documents_repo, chunks_repo, lineage_repo

# Chunk ID format: document_id_chunk_index (e.g. 1_0, 2_3)
CHUNK_ID_PATTERN = re.compile(r"^\d+_\d+$")

app = FastAPI(title="RiseApp API", description="Document lineage for XYZ Bank")
api = APIRouter(prefix="/api", tags=["api"])


def _blob_path() -> Path:
    return get_config().data_blob.resolve()


def _safe_content_path(relative_path: str, ext: str) -> Path:
    """Resolve blob / (relative_path + ext). Ensure path is under blob (no traversal)."""
    if ".." in relative_path or relative_path.startswith("/"):
        raise HTTPException(status_code=404, detail="Invalid path")
    blob = _blob_path()
    full = (blob / (relative_path + "." + ext)).resolve()
    try:
        full.relative_to(blob)
    except ValueError:
        raise HTTPException(status_code=404, detail="Path outside blob")
    return full


# --- Documents list ---
@api.get("/documents")
def list_documents(
    doc_type: Optional[Literal["external", "internal"]] = Query(None),
) -> list:
    init_schema(get_connection())
    docs = documents_repo.list_all()
    if doc_type:
        docs = [d for d in docs if d.doc_type == doc_type]
    return [
        {
            "id": d.id,
            "relative_path": d.relative_path,
            "doc_type": d.doc_type,
            "name": d.name,
            "has_pdf": d.has_pdf,
            "has_html": d.has_html,
            "has_md": d.has_md,
            "converted_at": d.converted_at,
            "chunked_at": d.chunked_at,
        }
        for d in docs
    ]


# --- Document content (HTML / MD / PDF) ---
@api.get("/documents/{doc_id}/content")
def get_document_content(
    doc_id: int,
    format: Literal["html", "md", "pdf"] = Query(..., alias="format"),
) -> FileResponse:
    init_schema(get_connection())
    doc = documents_repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    ext = "html" if format == "html" else "md" if format == "md" else "pdf"
    path = _safe_content_path(doc.relative_path, ext)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media = "text/html" if ext == "html" else "text/markdown" if ext == "md" else "application/pdf"
    disposition = "attachment" if ext == "pdf" else "inline"
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        headers={"Content-Disposition": f'{disposition}; filename="{path.name}"'},
    )


# --- Document chunks with linked chunk IDs ---
@api.get("/documents/{doc_id}/chunks")
def get_document_chunks(doc_id: int) -> list:
    init_schema(get_connection())
    doc = documents_repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = chunks_repo.list_by_document(doc_id)
    preview_len = 120
    out = []
    for c in chunks:
        if doc.doc_type == "internal":
            links = lineage_repo.list_by_internal(c.id)
            linked_ids = [r.external_chunk_id for r in links]
        else:
            links = lineage_repo.list_by_external(c.id)
            linked_ids = [r.internal_chunk_id for r in links]
        preview = (c.content[:preview_len] + "…") if len(c.content) > preview_len else c.content
        out.append(
            {
                "chunk_id": c.id,
                "chunk_index": c.chunk_index,
                "content_preview": preview,
                "linked_chunk_ids": linked_ids,
            }
        )
    return out


# --- Chunk content by ID ---
@api.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str) -> dict:
    if not CHUNK_ID_PATTERN.match(chunk_id):
        raise HTTPException(status_code=400, detail="Invalid chunk_id format")
    init_schema(get_connection())
    chunk = chunks_repo.get(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    doc = documents_repo.get_by_id(chunk.document_id)
    doc_info = (
        {
            "relative_path": doc.relative_path,
            "doc_type": doc.doc_type,
            "name": doc.name,
        }
        if doc
        else None
    )
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "document": doc_info,
    }


# --- Process 1/2/3 with "already processed" check ---
def _check_process_1_work() -> bool:
    """True if there is work to do (unconverted PDFs)."""
    blob = _blob_path()
    if not blob.exists():
        return False
    for sub in ("external", "internal"):
        base = blob / sub
        if not base.is_dir():
            continue
        for doc_dir in base.iterdir():
            if not doc_dir.is_dir():
                continue
            pdfs = list(doc_dir.glob("*.pdf"))
            if not pdfs:
                continue
            rel = f"{sub}/{doc_dir.name}/{pdfs[0].stem}"
            doc = documents_repo.get_by_path(rel)
            html_path = doc_dir / (pdfs[0].stem + ".html")
            md_path = doc_dir / (pdfs[0].stem + ".md")
            if not doc or not doc.converted_at or not html_path.exists() or not md_path.exists():
                return True
    return False


def _check_process_2_work() -> bool:
    """True if there are docs to chunk."""
    return len(documents_repo.list_unprocessed_for_chunking()) > 0


def _check_process_3_work() -> bool:
    """True if there are internal chunks to process for lineage."""
    return len(chunks_repo.list_unprocessed_internal_chunks()) > 0


@api.post("/process/1")
def run_process_1(body: Optional[ProcessRequest] = None) -> dict:
    force = body.force if body else False
    init_schema(get_connection())
    if not force and not _check_process_1_work():
        return JSONResponse(
            status_code=200,
            content={
                "status": "already_processed",
                "message": "All PDFs already converted. Use force=true to reconvert.",
                "force_available": True,
            },
        )
    from src.processes.process_1_convert import run_process_1 as run

    run(force=force)
    return {"status": "completed", "process": 1}


@api.post("/process/2")
def run_process_2(body: Optional[ProcessRequest] = None) -> dict:
    force = body.force if body else False
    init_schema(get_connection())
    if not force and not _check_process_2_work():
        return JSONResponse(
            status_code=200,
            content={
                "status": "already_processed",
                "message": "All documents already chunked. Use force=true to rechunk.",
                "force_available": True,
            },
        )
    from src.processes.process_2_chunk_store import run_process_2 as run

    run(force=force)
    return {"status": "completed", "process": 2}


@api.post("/process/3")
def run_process_3(body: Optional[ProcessRequest] = None) -> dict:
    force = body.force if body else False
    init_schema(get_connection())
    if not force and not _check_process_3_work():
        return JSONResponse(
            status_code=200,
            content={
                "status": "already_processed",
                "message": "All internal chunks already processed for lineage. Use force=true to reprocess.",
                "force_available": True,
            },
        )
    from src.processes.process_3_lineage import run_process_3 as run

    run(force=force)
    return {"status": "completed", "process": 3}


# --- Upload PDF ---
@api.post("/upload")
def upload_pdf(
    file: UploadFile = File(...),
    doc_type: Literal["external", "internal"] = Form(...),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF file required")
    stem = Path(file.filename).stem
    if not stem or stem != Path(file.filename).stem:
        raise HTTPException(status_code=400, detail="Invalid filename")
    blob = _blob_path()
    folder = blob / doc_type / stem
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (stem + ".pdf")
    content = file.file.read()
    with open(dest, "wb") as f:
        f.write(content)
    relative_path = f"{doc_type}/{stem}/{stem}"
    return JSONResponse(
        status_code=201,
        content={"path": relative_path, "doc_type": doc_type},
    )


app.include_router(api)

# Static files: serve from project root "static" folder
_STATIC = Path(__file__).resolve().parent.parent.parent / "static"
if _STATIC.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
