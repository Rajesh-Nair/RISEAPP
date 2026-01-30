"""Tests for embedding module (HuggingFace only, no API key)."""

import numpy as np
import pytest

from src.embedding.base import BaseEmbedding
from src.embedding.factory import get_embedding

pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")


def test_hf_embedding() -> None:
    emb = get_embedding()
    dim = emb.embedding_dim()
    assert dim > 0
    out = emb.embed(["hello", "world"])
    assert isinstance(out, np.ndarray)
    assert out.shape == (2, dim)
    assert out.dtype == np.float32


def test_hf_embed_empty() -> None:
    emb = get_embedding()
    dim = emb.embedding_dim()
    out = emb.embed([])
    assert out.shape == (0, dim)


def test_factory_huggingface() -> None:
    emb = get_embedding()
    assert isinstance(emb, BaseEmbedding)
    assert emb.embedding_dim() > 0
    emb.embed(["test"])
