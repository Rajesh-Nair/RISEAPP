"""Google Gemini embedding (gemini-embedding-001) via google-genai."""

import os
from typing import List

import numpy as np

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger
from src.embedding.base import BaseEmbedding

logger = CustomLogger().get_logger(__file__)


class GoogleEmbedding(BaseEmbedding):
    def __init__(self, model_name: str = "gemini-embedding-001", api_key: str | None = None):
        self.model_name = model_name
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self._api_key:
            raise CustomException("Google embedding requires GOOGLE_API_KEY or GEMINI_API_KEY in .env")
        try:
            from google import genai
            from google.genai import types

            self._genai = genai
            self._types = types
            self._client = genai.Client(api_key=self._api_key)
        except Exception as e:
            raise CustomException(f"Failed to init Google embedding client: {e}")
        # Default output dim for FAISS compatibility; 768 matches common HF dims
        self._dim = 768
        logger.info("Google embedding loaded", model=model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        try:
            result = self._client.models.embed_content(
                model=self.model_name,
                contents=texts,
                config=self._types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self._dim,
                ),
            )
        except Exception as e:
            raise CustomException(f"Google embed_content failed: {e}")
        out = []
        for e in result.embeddings:
            arr = np.array(e.values, dtype=np.float32)
            n = np.linalg.norm(arr)
            if n > 0:
                arr = arr / n
            out.append(arr)
        return np.stack(out, axis=0)

    def embedding_dim(self) -> int:
        return self._dim
