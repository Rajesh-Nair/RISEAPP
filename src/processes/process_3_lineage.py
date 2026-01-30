"""Process-3: For each internal chunk, find external matches via FAISS + lineage agent, store lineage."""

import asyncio

from logger.custom_logger import CustomLogger
from utils.config import get_config

from src.db.connection import get_connection, init_schema
from src.db.repositories import chunks_repo, lineage_repo
from src.embedding.factory import get_embedding
from src.vectordb.faiss_store import FaissStore
from src.agents.lineage_detect_agent.agent import detect_lineage

logger = CustomLogger().get_logger(__file__)


def _run_process_3_sync() -> None:
    asyncio.run(_run_process_3_async())


async def _run_process_3_async() -> None:
    cfg = get_config()
    init_schema(get_connection())

    internal = chunks_repo.list_internal_chunks()
    if not internal:
        logger.info("Process-3: no internal chunks")
        return

    emb = get_embedding()
    store = FaissStore(dim=emb.embedding_dim())
    top_k = cfg.lineage_top_k

    lineage_repo.clear_all()
    inserted = 0
    for c in internal:
        vec = emb.embed([c.content])
        if vec.size == 0:
            continue
        hits = store.search(vec[0], k=top_k, doc_type_filter="external", multiplier=5)
        if not hits:
            continue
        candidates = []
        for eid, _ in hits:
            row = chunks_repo.get(eid)
            if row:
                candidates.append((eid, row.content))
        if not candidates:
            continue
        match = await detect_lineage(c.content, candidates)
        for eid in match.external_chunk_ids:
            if eid in [x[0] for x in candidates]:
                lineage_repo.insert(c.id, eid, match.confidence)
                inserted += 1
    logger.info("Process-3 finished", internal_chunks=len(internal), lineage_inserted=inserted)


def run_process_3() -> None:
    _run_process_3_sync()
