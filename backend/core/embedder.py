"""
backend/core/embedder.py
=========================
Singleton sentence-transformer embedding model.

Model: all-mpnet-base-v2
  - Vector dimension: 768
  - Well-suited for semantic similarity over medical text
  - Runs fully offline after first download

Usage:
    from core.embedder import get_embedder
    emb = get_embedder()
    vector = emb.embed("patient presents with dyspnea")
"""

from __future__ import annotations

import logging
import threading
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger("medai.embedder")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
VECTOR_DIM = 768


# ---------------------------------------------------------------------------
# Embedder class
# ---------------------------------------------------------------------------

class Embedder:
    """
    Thread-safe singleton wrapper around SentenceTransformer.
    Provides both single-text and batch embedding utilities.
    """

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        logger.info("Loading embedding model: %s", model_name)
        self._model = SentenceTransformer(model_name)
        self.dim: int = VECTOR_DIM
        logger.info("Embedding model loaded (dim=%d)", self.dim)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> List[float]:
        """
        Embed a single text string into a 768-dimensional float vector.

        Args:
            text: Input text (will be truncated to model max length internally).

        Returns:
            List[float] of length 768.
        """
        if not text or not text.strip():
            # Return zero-vector for empty input (safe fallback)
            return [0.0] * self.dim

        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts efficiently.

        Args:
            texts: List of input strings.

        Returns:
            List of 768-dimensional float vectors.
        """
        if not texts:
            return []

        # Replace empty strings with a placeholder to avoid model errors
        safe_texts = [t if t.strip() else "<empty>" for t in texts]
        vectors = self._model.encode(safe_texts, normalize_embeddings=True, batch_size=32)
        return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Singleton management (thread-safe)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_instance: Embedder | None = None


def get_embedder() -> Embedder:
    """
    Return the global singleton Embedder instance.
    Creates it on first call (lazy + thread-safe).
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = Embedder(MODEL_NAME)
    return _instance
