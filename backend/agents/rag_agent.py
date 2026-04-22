import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sentence_transformers import SentenceTransformer

from core.vectorstore import get_vectorstore, SearchResult
from agents.router_agent import QueryIntent, to_canonical

logger = logging.getLogger("medai.rag_agent")

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class RagResult:
    """Standardized result from the RAG retrieval pipeline."""
    chunks: List[SearchResult] = field(default_factory=list)
    confidence: float = 0.0
    collections_searched: List[str] = field(default_factory=list)
    query_used: str = ""
    filters_applied: Optional[Dict[str, Any]] = None

    @property
    def is_relevant(self) -> bool:
        return self.confidence > 0.3

# ---------------------------------------------------------------------------

# RagAgent Implementation
# ---------------------------------------------------------------------------

class RagAgent:
    """
    Agent responsible for semantic retrieval using Sentence Transformers and Qdrant.
    Handles embedding, routing, and result aggregation.
    """

    def __init__(
        self, 
        vectorstore=None, 
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
        top_k: int = 5
    ) -> None:
        """
        Initialize the RAG Agent.
        
        Args:
            vectorstore: Optional VectorStore instance (defaults to singleton).
            model_name:  SentenceTransformer model for embeddings.
            top_k:       Number of results to retrieve per collection.
        """
        # Ensure top_k is always int
        try:
            self.top_k = int(top_k)
        except (TypeError, ValueError):
            self.top_k = 5

        logger.info("Initializing RagAgent with model: %s", model_name)
        self.encoder = SentenceTransformer(model_name)
        self.vectorstore = vectorstore or get_vectorstore()

    def retrieve(
        self, 
        query: str, 
        intent: QueryIntent = QueryIntent.MEDICAL_QUESTION,
        filters: Optional[Dict[str, Any]] = None
    ) -> RagResult:
        """
        Retrieve relevant medical chunks based on query and intent.
        """
        if not query or not query.strip():
            return RagResult(query_used=query)

        logger.info("Retrieving for query: '%s' | Intent: %s", query[:50], intent)

        # 1. Embed the query
        try:
            query_vector = self.encoder.encode(query).tolist()
        except Exception as e:
            logger.error("Embedding generation failed: %s", e)
            return RagResult(query_used=query)

        # 2. Determine collections based on intent
        # Map intent to canonical to decide where to search
        canonical = to_canonical(intent)
        collections = []
        
        if canonical == QueryIntent.MEDICAL_QUESTION:
            collections = ["global_knowledge"]
        elif canonical == QueryIntent.REPORT_ANALYSIS:
            collections = ["patient_specific"]
        elif intent == QueryIntent.HYBRID:
            collections = ["global_knowledge", "patient_specific"]
        else:
            collections = ["global_knowledge"]

        # 3. Search Qdrant
        all_chunks: List[SearchResult] = []
        for col in collections:
            try:
                hits = self.vectorstore.search(
                    collection=col,
                    query_vector=query_vector,
                    top_k=self.top_k,
                    filters=filters
                )
                all_chunks.extend(hits)
            except Exception as e:
                logger.error("Search failed in collection '%s': %s", col, e)

        # 4. Deduplicate and Sort
        # Deduplicate by chunk_id
        seen_ids = set()
        unique_chunks = []
        for chunk in all_chunks:
            if chunk.chunk_id not in seen_ids:
                unique_chunks.append(chunk)
                seen_ids.add(chunk.chunk_id)
        
        # Sort by score descending
        unique_chunks.sort(key=lambda x: x.score, reverse=True)
        
        # Enforce top_k on the final list
        final_chunks = unique_chunks[:self.top_k]

        # 5. Compute Confidence (Average Score of top results)
        confidence = 0.0
        if final_chunks:
            confidence = sum(c.score for c in final_chunks) / len(final_chunks)

        return RagResult(
            chunks=final_chunks,
            confidence=confidence,
            collections_searched=collections,
            query_used=query,
            filters_applied=filters
        )