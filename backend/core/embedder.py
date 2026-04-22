from __future__ import annotations

import logging
import os
import requests
from typing import List

logger = logging.getLogger("medai.embedder")

HF_API_KEY = os.getenv("HF_API_KEY")

MODEL_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}"
}

VECTOR_DIM = 384


class Embedder:

    def __init__(self) -> None:
        if not HF_API_KEY:
            raise Exception("HF_API_KEY not set in environment")

        self.dim: int = VECTOR_DIM
        logger.info("Using HuggingFace embeddings (dim=%d)", self.dim)

    def embed(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dim

        try:
            response = requests.post(
                MODEL_URL,
                headers=HEADERS,
                json={"inputs": text},
                timeout=20
            )

            if response.status_code != 200:
                raise Exception(response.text)

            data = response.json()

            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                return data[0]

            return data

        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return [0.0] * self.dim

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        results = []
        for text in texts:
            results.append(self.embed(text))

        return results


_instance: Embedder | None = None


def get_embedder() -> Embedder:
    global _instance

    if _instance is None:
        _instance = Embedder()

    return _instance