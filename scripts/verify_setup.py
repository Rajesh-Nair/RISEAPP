"""Quick sanity check: config, DB, chunker, embedding (HF), FAISS. Run from project root."""

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    import sys
    sys.path.insert(0, str(root))

    print("1. Config...")
    from utils.config import get_config
    cfg = get_config()
    assert cfg.data_blob
    print("   OK")

    print("2. DB schema...")
    from src.db.connection import get_connection, init_schema
    init_schema(get_connection())
    print("   OK")

    print("3. Chunker...")
    from src.chunking.chunker import chunk_text
    out = chunk_text("Hello world. " * 50, size=100, overlap=10)
    assert len(out) >= 1
    print("   OK")

    print("4. Embedding (HuggingFace)...")
    from src.embedding.factory import get_embedding
    emb = get_embedding()
    v = emb.embed(["test"])
    assert v.shape[0] == 1 and v.shape[1] == emb.embedding_dim()
    print("   OK")

    print("5. FAISS store...")
    import tempfile
    from src.vectordb.faiss_store import FaissStore
    import numpy as np
    d = emb.embedding_dim()
    t = Path(tempfile.mkdtemp()) / "v"
    store = FaissStore(dim=d, path=t)
    store.clear()
    vec = np.random.randn(1, d).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    store.add(["a"], vec, ["external"])
    hits = store.search(vec[0], k=1)
    assert len(hits) == 1
    print("   OK")

    print("All checks passed.")


if __name__ == "__main__":
    main()
