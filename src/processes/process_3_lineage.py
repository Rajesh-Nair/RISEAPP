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


_force_mode = False


def _run_process_3_sync(force: bool = False) -> None:
    global _force_mode
    _force_mode = force
    asyncio.run(_run_process_3_async())


async def _run_process_3_async() -> None:
    """
    Process-3: For each internal chunk, find external matches via FAISS + lineage agent, store lineage.
    
    In force mode, clears all lineage entries and reprocesses all internal chunks.
    """
    global _force_mode
    force = _force_mode
    
    cfg = get_config()
    init_schema(get_connection())

    if force:
        logger.info("Process-3 running in FORCE mode - reprocessing all internal chunks")
        # Clear all lineage entries
        lineage_repo.clear_all()
        # Get ALL internal chunks (not just unprocessed)
        internal = chunks_repo.list_internal_chunks()
    else:
        # Get only unprocessed internal chunks
        internal = chunks_repo.list_unprocessed_internal_chunks()
    
    if not internal:
        logger.info("Process-3: no internal chunks to process")
        return

    emb = get_embedding()
    store = FaissStore(dim=emb.embedding_dim())
    top_k = cfg.lineage_top_k

    processed_count = 0
    inserted = 0
    for c in internal:
        # Delete old lineage for this chunk (in non-force mode)
        if not force:
            lineage_repo.delete_by_internal_chunk(c.id)
        
        # Vector search with k=1 (closest match only)
        vec = emb.embed([c.content])
        if vec.size == 0:
            chunks_repo.mark_lineage_processed(c.id)
            continue
        
        # Search for top-1 external match
        hits = store.search(vec[0], k=1, doc_type_filter="external", multiplier=5)
        if not hits:
            chunks_repo.mark_lineage_processed(c.id)
            continue
        
        # Get only the top-1 match
        top_chunk_id, top_score = hits[0]
        top_chunk = chunks_repo.get(top_chunk_id)
        
        if not top_chunk:
            chunks_repo.mark_lineage_processed(c.id)
            continue
        
        # Pass single candidate to LLM
        candidates = [(top_chunk_id, top_chunk.content)]
        match = await detect_lineage(c.content, candidates)
        
        # Store results
        for eid in match.external_chunk_ids:
            if eid in [x[0] for x in candidates]:
                lineage_repo.insert(c.id, eid, match.confidence)
                inserted += 1
        
        # Mark as processed
        chunks_repo.mark_lineage_processed(c.id)
        processed_count += 1
        
    logger.info("Process-3 finished", processed_chunks=processed_count, lineage_inserted=inserted, force=force)


def run_process_3(force: bool = False) -> None:
    """
    Process-3: Lineage detection, store lineage.
    
    Args:
        force: If True, clear all lineage and reprocess all internal chunks.
    """
    _run_process_3_sync(force=force)
