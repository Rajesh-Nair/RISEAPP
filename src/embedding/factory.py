"""Config-based embedding factory."""

from utils.config import get_config

from src.embedding.base import BaseEmbedding
from src.embedding.google_embedding import GoogleEmbedding
from src.embedding.huggingface_embedding import HuggingFaceEmbedding


def get_embedding() -> BaseEmbedding:
    cfg = get_config()
    provider = cfg.embedding_provider.lower()
    model = cfg.embedding_model
    if provider == "google":
        return GoogleEmbedding(model_name=model or "gemini-embedding-001")
    if provider == "huggingface":
        return HuggingFaceEmbedding(model_name=model or "sentence-transformers/all-MiniLM-L6-v2")
    raise ValueError(f"Unknown embedding provider: {provider}. Use 'google' or 'huggingface'.")
