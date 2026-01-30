"""Process-1: Scan PDFs in blob, convert to HTML/MD, update documents table."""

import traceback
from pathlib import Path

import pymupdf

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger
from utils.config import get_config
from utils.file_io import write_text
from src.db.connection import get_connection, init_schema
from src.db.repositories import documents_repo

logger = CustomLogger().get_logger(__file__)


def _convert_pdf(pdf_path: Path, out_dir: Path) -> tuple[bool, bool]:
    """Convert PDF to HTML and MD in out_dir. Returns (has_html, has_md)."""
    html_path = out_dir / (pdf_path.stem + ".html")
    md_path = out_dir / (pdf_path.stem + ".md")
    try:
        # PyMuPDF on Windows expects a string path; pathlib.Path can raise or produce empty errors
        doc = pymupdf.open(str(pdf_path))
        html_parts = []
        md_parts = []
        # PyMuPDF get_text supports: "text", "html", "xhtml", "dict", "blocks", "words", "json", etc. NOT "markdown"
        for page in doc:
            html_parts.append(page.get_text("html"))
            md_parts.append(page.get_text("text") or "")
        doc.close()
        html_content = "\n".join(html_parts)
        md_content = "\n".join(md_parts)
        write_text(html_path, html_content)
        write_text(md_path, md_content)
        return (True, True)
    except Exception as e:
        tb = traceback.format_exc()
        # Last frame where exception was raised: file, line number, code line
        frame = traceback.extract_tb(e.__traceback__)[-1] if e.__traceback__ else None
        err_msg = str(e).strip() or repr(e)
        logger.warning(
            "PDF convert failed",
            path=str(pdf_path),
            error=err_msg,
            exc_type=type(e).__name__,
            python_file=frame.filename if frame else None,
            python_line=frame.lineno if frame else None,
            python_code=frame.line if frame else None,
            traceback=tb,
        )
        loc = f" at {frame.filename}:{frame.lineno}" if frame else ""
        raise CustomException(f"Failed to convert {pdf_path}: {err_msg}{loc}")


def run_process_1(force: bool = False) -> None:
    """
    Process-1: Scan PDFs in blob, convert to HTML/MD, update documents table.
    
    Args:
        force: If True, re-convert all PDFs even if already converted.
               Existing HTML/MD files will be overwritten.
    """
    cfg = get_config()
    blob = cfg.data_blob
    if not blob.exists():
        raise CustomException(f"Blob dir not found: {blob}")
    init_schema(get_connection())

    if force:
        logger.info("Process-1 running in FORCE mode - re-converting all documents")

    converted_count = 0
    skipped_count = 0

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
            pdf_path = pdfs[0]
            rel = f"{sub}/{doc_dir.name}/{pdf_path.stem}"
            name = pdf_path.stem
            
            # Check if already converted (skip check if force=True)
            existing_doc = documents_repo.get_by_path(rel)
            html_path = doc_dir / (pdf_path.stem + ".html")
            md_path = doc_dir / (pdf_path.stem + ".md")
            
            if not force and existing_doc and existing_doc.converted_at:
                if html_path.exists() and md_path.exists():
                    logger.info("Skipping already converted doc", relative_path=rel, doc_id=existing_doc.id)
                    skipped_count += 1
                    continue
            
            # Convert the PDF (overwrites existing HTML/MD if force=True)
            has_pdf = True
            has_html = has_md = False
            try:
                _convert_pdf(pdf_path, doc_dir)
                has_html = html_path.exists()
                has_md = md_path.exists()
                converted_count += 1
            except Exception:
                pass
            
            # Upsert and mark as converted
            doc_id = documents_repo.upsert(rel, sub, name, has_pdf, has_html, has_md)
            if has_html and has_md:
                documents_repo.mark_converted(doc_id)
            logger.info("Process-1 doc", relative_path=rel, doc_id=doc_id, converted=True, force=force)

    logger.info("Process-1 finished", converted=converted_count, skipped=skipped_count, force=force)
