"""Embedding abstraction; implementations in base, huggingface, google."""

from src.embedding.base import BaseEmbedding
from src.embedding.factory import get_embedding

__all__ = ["BaseEmbedding", "get_embedding"]
