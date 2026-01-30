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


def run_process_2() -> None:
    cfg = get_config()
    blob = cfg.data_blob
    init_schema(get_connection())

    docs = documents_repo.list_with_md()
    if not docs:
        logger.info("Process-2: no docs with MD")
        return

    emb = get_embedding()
    dim = emb.embedding_dim()
    store = FaissStore(dim=dim)
    store.clear()
    for doc in docs:
        chunks_repo.delete_by_document(doc.id)

    total = 0
    for doc in docs:
        md_path = blob / (doc.relative_path + ".md")
        if not md_path.exists():
            logger.warning("Process-2: MD missing", path=str(md_path))
            continue
        chunks = chunk_md_file(md_path)
        texts = [c.content for c in chunks]
        if not texts:
            continue
        vecs = emb.embed(texts)
        chunk_ids = [f"{doc.id}_{c.index}" for c in chunks]
        for c, cid in zip(chunks, chunk_ids):
            chunks_repo.insert(cid, doc.id, c.index, c.content, c.metadata)
        store.add(chunk_ids, vecs, [doc.doc_type] * len(chunk_ids))
        total += len(chunk_ids)
        logger.info("Process-2 doc", doc_id=doc.id, name=doc.name, n_chunks=len(chunks))

    store.save()
    logger.info("Process-2 finished", total_chunks=total)
