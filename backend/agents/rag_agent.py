"""
backend/agents/rag_agent.py
==========================
RAG Agent using the centralized RAGEngine.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from core.rag_engine import get_rag_engine
from agents.router_agent import QueryIntent

logger = logging.getLogger("medai.rag_agent")

@dataclass
class SearchResult:
    text: str
    score: float
    metadata: Dict[str, Any]
    source: str

@dataclass
class RagResult:
    chunks: List[SearchResult] = field(default_factory=list)
    confidence: float = 0.0
    is_relevant: bool = False
    collections_searched: List[str] = field(default_factory=list)

class RagAgent:
    def __init__(self, vectorstore=None, top_k: int = 5):
        self.rag_engine = get_rag_engine()
        self.top_k = top_k

    def retrieve(self, query: str, intent: QueryIntent = QueryIntent.MEDICAL_QUESTION, filters: Optional[Dict] = None) -> RagResult:
        """
        Retrieves relevant medical chunks using the RAGEngine.
        """
        results = self.rag_engine.search(query, top_k=self.top_k)
        
        chunks = [
            SearchResult(
                text=r["text"],
                score=r["score"],
                metadata=r["metadata"],
                source=r["source"]
            ) for r in results
        ]
        
        confidence = sum(c.score for c in chunks) / len(chunks) if chunks else 0.0
        is_relevant = confidence > 0.4  # Threshold for relevance
        
        return RagResult(
            chunks=chunks,
            confidence=confidence,
            is_relevant=is_relevant,
            collections_searched=["medical_knowledge"]
        )