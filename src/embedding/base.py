"""Abstract embedding interface."""

from abc import ABC, abstractmethod
from typing import List

import numpy as np


class BaseEmbedding(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Embed texts; returns (N, dim) float32 array."""
        ...

    @abstractmethod
    def embedding_dim(self) -> int:
        """Return vector dimension."""
        ...
