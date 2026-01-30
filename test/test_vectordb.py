"""Tests for FAISS store."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


@pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu not installed (e.g. no Windows wheel)")
def test_faiss_add_search() -> None:
    from src.vectordb.faiss_store import FaissStore
    dim = 4
    path = Path(tempfile.mkdtemp()) / "vd"
    store = FaissStore(dim=dim, path=path)
    store.clear()
    ids = ["a", "b", "c"]
    vecs = np.random.randn(3, dim).astype(np.float32)
    store.add(ids, vecs, ["external", "external", "internal"])
    out = store.search(vecs[0], k=2, doc_type_filter="external")
    assert len(out) >= 1
    assert out[0][0] in ids
    store.save()
    store2 = FaissStore(dim=dim, path=path)
    assert len(store2._chunk_ids) == 3
