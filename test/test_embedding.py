"""Tests for embedding module (HuggingFace only, no API key)."""

import numpy as np
import pytest

from src.embedding.base import BaseEmbedding
from src.embedding.huggingface_embedding import HuggingFaceEmbedding
from src.embedding.factory import get_embedding

pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")


def test_hf_embedding() -> None:
    emb = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    assert emb.embedding_dim() == 384
    out = emb.embed(["hello", "world"])
    assert isinstance(out, np.ndarray)
    assert out.shape == (2, 384)
    assert out.dtype == np.float32


def test_hf_embed_empty() -> None:
    emb = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    out = emb.embed([])
    assert out.shape == (0, 384)


def test_factory_huggingface() -> None:
    emb = get_embedding()
    assert isinstance(emb, BaseEmbedding)
    assert emb.embedding_dim() > 0
    emb.embed(["test"])
