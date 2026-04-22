"""
backend/core/vectorstore.py
============================
Qdrant vector database client and collection management.

Architecture:
  - Single shared QdrantClient (file-based local storage at ./qdrant_data)
  - Two collections:
      • global_knowledge   — curated medical encyclopedia corpus
      • patient_specific   — per-session uploaded patient documents
  - Vector size: 768 (matches all-mpnet-base-v2)
  - Distance metric: Cosine
  - HNSW index for fast approximate nearest-neighbour search

Usage:
    from core.vectorstore import get_vectorstore
    vs = get_vectorstore()
    vs.upsert_chunks("global_knowledge", chunks)
    results = vs.search("global_knowledge", query_vector, top_k=5)
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

logger = logging.getLogger("medai.vectorstore")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VECTOR_DIM = 768
DISTANCE = qdrant_models.Distance.COSINE

COLLECTIONS = {
    "global_knowledge": "Global medical encyclopedia — WHO, CDC, textbooks",
    "patient_specific": "Per-session patient-uploaded documents and reports",
}

# Default Qdrant storage path (relative to backend/ root)
DEFAULT_QDRANT_PATH = str(Path(__file__).parent.parent / "qdrant_data")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A single text chunk stored in Qdrant."""
    text: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class SearchResult:
    """A single retrieval result from Qdrant."""
    text: str
    score: float                        # cosine similarity [0, 1]
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""


# ---------------------------------------------------------------------------
# VectorStore class
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Manages the Qdrant client and exposes high-level upsert / search helpers.
    Uses file-based local Qdrant — no separate server required.
    """

    def __init__(self, storage_path: str = DEFAULT_QDRANT_PATH) -> None:
        logger.info("Initialising Qdrant at path: %s", storage_path)
        Path(storage_path).mkdir(parents=True, exist_ok=True)

        self._client = QdrantClient(path=storage_path)
        self._ensure_collections()

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def _ensure_collections(self) -> None:
        """Create collections if they do not already exist."""
        existing = {c.name for c in self._client.get_collections().collections}

        for name in COLLECTIONS:
            if name not in existing:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=qdrant_models.VectorParams(
                        size=VECTOR_DIM,
                        distance=DISTANCE,
                    ),
                    hnsw_config=qdrant_models.HnswConfigDiff(
                        m=16,                   # number of edges per node
                        ef_construct=100,       # quality of index build
                    ),
                )
                logger.info("Created Qdrant collection: %s", name)
            else:
                logger.info("Collection already exists: %s", name)

    # ------------------------------------------------------------------
    # Write — upsert chunks
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        collection: str,
        chunks: List[Chunk],
        batch_size: int = 64,
    ) -> int:
        """
        Upsert a list of Chunk objects into a collection in batches.

        Args:
            collection: Target collection name.
            chunks:     List of Chunk objects (text + vector + metadata).
            batch_size: Number of points per Qdrant upsert call.

        Returns:
            Total number of chunks upserted.
        """
        if not chunks:
            return 0

        total = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            points = [
                qdrant_models.PointStruct(
                    id=c.chunk_id,
                    vector=c.vector,
                    payload={"text": c.text, **c.metadata},
                )
                for c in batch
            ]
            self._client.upsert(collection_name=collection, points=points)
            total += len(batch)

        logger.info("Upserted %d chunks → '%s'", total, collection)
        return total

    # ------------------------------------------------------------------
    # Read — semantic search
    # ------------------------------------------------------------------

    def search(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Semantic vector search with optional metadata filtering.

        Args:
            collection:      Collection to search.
            query_vector:    768-dim query embedding.
            top_k:           Maximum number of results to return.
            score_threshold: Minimum cosine similarity to include a result.
            filters:         Optional dict of metadata key→value pairs to filter on.
                             E.g. {"organ_system": "cardiovascular"}

        Returns:
            List of SearchResult sorted by similarity (descending).
        """
        # --- Strict Type Enforcement ---
        try:
            # Explicitly cast to prevent 'VectorStore > int' or string-to-slice errors
            safe_limit = int(top_k) if top_k is not None else 5
            safe_threshold = float(score_threshold) if score_threshold is not None else 0.0
        except (TypeError, ValueError) as e:
            logger.error("Invalid type passed to search: top_k=%s, threshold=%s. Error: %s", 
                         type(top_k), type(score_threshold), e)
            safe_limit = 5
            safe_threshold = 0.0

        qdrant_filter = None
        if filters:
            must_conditions = [
                qdrant_models.FieldCondition(
                    key=k,
                    match=qdrant_models.MatchValue(value=v),
                )
                for k, v in filters.items()
            ]
            qdrant_filter = qdrant_models.Filter(must=must_conditions)

        try:
            hits = self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=safe_limit,
                score_threshold=safe_threshold,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        except Exception as e:
            logger.error("Qdrant search failed on '%s': %s", collection, e)
            return []

        results = []
        for hit in hits:
            payload = hit.payload or {}
            text = payload.pop("text", "")
            results.append(
                SearchResult(
                    text=text,
                    score=float(hit.score),
                    metadata=payload,
                    chunk_id=str(hit.id),
                )
            )

        return results

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self, collection: str) -> int:
        """Return the number of vectors stored in a collection."""
        return self._client.count(collection_name=collection).count

    def delete_by_source(self, collection: str, source: str) -> None:
        """
        Delete all chunks whose 'source' metadata field matches the given value.
        Useful for replacing a patient document on re-upload.
        """
        self._client.delete(
            collection_name=collection,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="source",
                            match=qdrant_models.MatchValue(value=source),
                        )
                    ]
                )
            ),
        )
        logger.info("Deleted chunks with source='%s' from '%s'", source, collection)

    def status(self) -> Dict[str, int]:
        """Return document counts per collection."""
        return {name: self.count(name) for name in COLLECTIONS}


    def close(self) -> None:
        """Safely close the Qdrant client connection."""
        try:
            if hasattr(self, "_client"):
                self._client.close()
                logger.info("Qdrant connection closed.")
        except Exception as e:
            logger.error("Error closing Qdrant connection: %s", e)


# ---------------------------------------------------------------------------
# Singleton management (thread-safe)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_instance: VectorStore | None = None


def get_vectorstore(storage_path: str = DEFAULT_QDRANT_PATH) -> VectorStore:
    """
    Return the global singleton VectorStore instance.
    Creates it on first call (lazy + thread-safe).
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = VectorStore(storage_path)
    return _instance


def close_vectorstore() -> None:
    """Global helper to close the singleton vectorstore instance."""
    global _instance
    if _instance is not None:
        with _lock:
            if _instance is not None:
                _instance.close()
                _instance = None
