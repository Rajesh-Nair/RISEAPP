"""FAISS index with chunk_id mapping; optional doc_type filter for search."""

import json
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger
from utils.config import get_config

logger = CustomLogger().get_logger(__file__)


class FaissStore:
    def __init__(self, dim: int, path: Optional[Path] = None):
        self.dim = dim
        self.path = path or get_config().data_vectordb
        self.path.mkdir(parents=True, exist_ok=True)
        self._index = None
        self._chunk_ids: List[str] = []
        self._doc_types: List[str] = []
        self._build_index()
        self.load()

    def _build_index(self) -> None:
        import faiss

        self._index = faiss.IndexFlatIP(self.dim)  # inner product for normalized vectors

    def add(self, chunk_ids: List[str], vectors: np.ndarray, doc_types: List[str]) -> None:
        if len(chunk_ids) != len(doc_types) or len(chunk_ids) != len(vectors):
            raise CustomException("chunk_ids, vectors, doc_types length mismatch")
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[1] != self.dim:
            raise CustomException(f"vectors must be (N, {self.dim})")
        n = np.linalg.norm(vectors, axis=1, keepdims=True)
        n = np.where(n > 0, n, 1.0)
        vectors = vectors / n
        self._index.add(vectors)
        self._chunk_ids.extend(chunk_ids)
        self._doc_types.extend(doc_types)
        logger.info("FaissStore add", n=len(chunk_ids), total=len(self._chunk_ids))

    def search(
        self,
        query: np.ndarray,
        k: int,
        doc_type_filter: Optional[str] = None,
        multiplier: int = 5,
    ) -> List[Tuple[str, float]]:
        query = np.asarray(query, dtype=np.float32)
        if query.ndim == 1:
            query = query.reshape(1, -1)
        if query.shape[1] != self.dim:
            raise CustomException(f"query dim {query.shape[1]} != {self.dim}")
        qn = np.linalg.norm(query)
        if qn > 0:
            query = query / qn
        fetch = k * multiplier if doc_type_filter else k
        fetch = min(fetch, self._index.ntotal)
        if fetch <= 0:
            return []
        scores, indices = self._index.search(query, fetch)
        out: List[Tuple[str, float]] = []
        for i, idx in enumerate(indices[0]):
            if idx < 0:
                continue
            cid = self._chunk_ids[idx]
            doc_type = self._doc_types[idx]
            if doc_type_filter and doc_type != doc_type_filter:
                continue
            out.append((cid, float(scores[0][i])))
            if len(out) >= k:
                break
        return out

    def save(self, base_path: Optional[Path] = None) -> None:
        import faiss

        p = base_path or self.path
        p.mkdir(parents=True, exist_ok=True)
        idx_path = p / "index.faiss"
        meta_path = p / "meta.json"
        faiss.write_index(self._index, str(idx_path))
        meta = {"chunk_ids": self._chunk_ids, "doc_types": self._doc_types, "dim": self.dim}
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("FaissStore saved", path=str(p))

    def load(self, base_path: Optional[Path] = None) -> None:
        import faiss

        p = base_path or self.path
        idx_path = p / "index.faiss"
        meta_path = p / "meta.json"
        if not idx_path.exists() or not meta_path.exists():
            return
        self._index = faiss.read_index(str(idx_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self._chunk_ids = meta["chunk_ids"]
        self._doc_types = meta["doc_types"]
        self.dim = meta["dim"]
        logger.info("FaissStore loaded", n=len(self._chunk_ids), path=str(p))

    def clear(self) -> None:
        self._build_index()
        self._chunk_ids = []
        self._doc_types = []
