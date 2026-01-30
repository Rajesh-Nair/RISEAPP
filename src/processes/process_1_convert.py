"""Process-1: Scan PDFs in blob, convert to HTML/MD, update documents table."""

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
        doc = pymupdf.open(pdf_path)
        html_parts = []
        md_parts = []
        for i, page in enumerate(doc):
            html_parts.append(page.get_text("html"))
            md_parts.append(page.get_text("markdown") or page.get_text())
        doc.close()
        html_content = "\n".join(html_parts)
        md_content = "\n".join(md_parts)
        write_text(html_path, html_content)
        write_text(md_path, md_content)
        return (True, True)
    except Exception as e:
        logger.warning("PDF convert failed", path=str(pdf_path), error=str(e))
        raise CustomException(f"Failed to convert {pdf_path}: {e}")


def run_process_1() -> None:
    cfg = get_config()
    blob = cfg.data_blob
    if not blob.exists():
        raise CustomException(f"Blob dir not found: {blob}")
    init_schema(get_connection())

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
            has_pdf = True
            has_html = has_md = False
            try:
                _convert_pdf(pdf_path, doc_dir)
                has_html = (doc_dir / (pdf_path.stem + ".html")).exists()
                has_md = (doc_dir / (pdf_path.stem + ".md")).exists()
            except Exception:
                pass
            doc_id = documents_repo.upsert(rel, sub, name, has_pdf, has_html, has_md)
            logger.info("Process-1 doc", relative_path=rel, doc_id=doc_id)

    logger.info("Process-1 finished")
