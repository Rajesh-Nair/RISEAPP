"""Process-2: Read .md docs, chunk, embed, store in DB + FAISS."""

from pathlib import Path

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger
from utils.config import get_config
from src.chunking.chunker import chunk_md_file
from src.db.connection import get_connection, init_schema
from src.db.repositories import chunks_repo, documents_repo
from src.embedding.factory import get_embedding
from src.vectordb.faiss_store import FaissStore

logger = CustomLogger().get_logger(__file__)


def run_process_2(force: bool = False) -> None:
    """
    Process-2: Read .md docs, chunk, embed, store in DB + FAISS.
    
    Args:
        force: If True, clear vector store and re-chunk all documents.
               Deletes all existing chunks and rebuilds from scratch.
    """
    cfg = get_config()
    blob = cfg.data_blob
    init_schema(get_connection())

    emb = get_embedding()
    dim = emb.embedding_dim()
    store = FaissStore(dim=dim)

    if force:
        logger.info("Process-2 running in FORCE mode - re-chunking all documents")
        # Clear entire vector store
        store.clear()
        # Get ALL documents with MD (not just unprocessed)
        docs = documents_repo.list_with_md()
        # Delete all chunks for all docs
        for doc in docs:
            chunks_repo.delete_by_document(doc.id)
    else:
        # Get only unprocessed or updated documents
        docs = documents_repo.list_unprocessed_for_chunking()

    if not docs:
        logger.info("Process-2: no docs to process")
        return

    processed_count = 0
    total = 0
    for doc in docs:
        md_path = blob / (doc.relative_path + ".md")
        if not md_path.exists():
            logger.warning("Process-2: MD missing", path=str(md_path))
            continue
        
        # Delete old chunks for this doc only (if re-processing in non-force mode)
        if not force:
            chunks_repo.delete_by_document(doc.id)
        
        # Chunk, embed, and store
        chunks = chunk_md_file(md_path)
        texts = [c.content for c in chunks]
        if not texts:
            # Mark as chunked even if no chunks (to avoid reprocessing)
            documents_repo.mark_chunked(doc.id)
            continue
        
        vecs = emb.embed(texts)
        chunk_ids = [f"{doc.id}_{c.index}" for c in chunks]
        for c, cid in zip(chunks, chunk_ids):
            chunks_repo.insert(
                cid,
                doc.id,
                c.index,
                c.content,
                c.metadata,
                start_offset=getattr(c, "start_offset", None),
                end_offset=getattr(c, "end_offset", None),
            )
        store.add(chunk_ids, vecs, [doc.doc_type] * len(chunk_ids))
        
        # Mark as chunked
        documents_repo.mark_chunked(doc.id)
        
        total += len(chunk_ids)
        processed_count += 1
        logger.info("Process-2 doc", doc_id=doc.id, name=doc.name, n_chunks=len(chunks), force=force)

    store.save()
    logger.info("Process-2 finished", processed_docs=processed_count, total_chunks=total, force=force)
