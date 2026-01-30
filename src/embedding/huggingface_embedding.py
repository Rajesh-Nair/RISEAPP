"""HuggingFace sentence-transformers embedding (e.g. all-MiniLM-L6-v2)."""

from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger
from src.embedding.base import BaseEmbedding

logger = CustomLogger().get_logger(__file__)


class HuggingFaceEmbedding(BaseEmbedding):
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        try:
            self._model = SentenceTransformer(model_name)
        except Exception as e:
            raise CustomException(f"Failed to load HuggingFace model {model_name}: {e}")
        logger.info("HuggingFace embedding loaded", model=model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embedding_dim()), dtype=np.float32)
        out = self._model.encode(texts, convert_to_numpy=True, dtype="float32")
        return np.asarray(out, dtype=np.float32)

    def embedding_dim(self) -> int:
        return self._model.get_sentence_embedding_dimension()
