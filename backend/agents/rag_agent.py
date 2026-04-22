import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from core.vectorstore import get_vectorstore, SearchResult
from agents.router_agent import QueryIntent, to_canonical

logger = logging.getLogger("medai.rag_agent")

HF_API_KEY = os.getenv("HF_API_KEY")

HF_MODEL_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

HF_HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}"
}


@dataclass
class RagResult:
    chunks: List[SearchResult] = field(default_factory=list)
    confidence: float = 0.0
    collections_searched: List[str] = field(default_factory=list)
    query_used: str = ""
    filters_applied: Optional[Dict[str, Any]] = None

    @property
    def is_relevant(self) -> bool:
        return self.confidence > 0.3


def get_embedding(text: str) -> List[float]:
    if not HF_API_KEY:
        raise Exception("HF_API_KEY not set")

    try:
        response = requests.post(
            HF_MODEL_URL,
            headers=HF_HEADERS,
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
        logger.error("HF embedding failed: %s", e)
        return []


class RagAgent:

    def __init__(
        self,
        vectorstore=None,
        top_k: int = 5
    ) -> None:

        try:
            self.top_k = int(top_k)
        except (TypeError, ValueError):
            self.top_k = 5

        logger.info("Initializing RagAgent")
        self.vectorstore = vectorstore or get_vectorstore()

    def retrieve(
        self,
        query: str,
        intent: QueryIntent = QueryIntent.MEDICAL_QUESTION,
        filters: Optional[Dict[str, Any]] = None
    ) -> RagResult:

        if not query or not query.strip():
            return RagResult(query_used=query)

        logger.info("Retrieving query: '%s'", query[:50])

        query_vector = get_embedding(query)

        if not query_vector:
            return RagResult(query_used=query)

        canonical = to_canonical(intent)

        if canonical == QueryIntent.MEDICAL_QUESTION:
            collections = ["global_knowledge"]
        elif canonical == QueryIntent.REPORT_ANALYSIS:
            collections = ["patient_specific"]
        elif intent == QueryIntent.HYBRID:
            collections = ["global_knowledge", "patient_specific"]
        else:
            collections = ["global_knowledge"]

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
                logger.error("Search failed in '%s': %s", col, e)

        seen_ids = set()
        unique_chunks = []

        for chunk in all_chunks:
            if chunk.chunk_id not in seen_ids:
                unique_chunks.append(chunk)
                seen_ids.add(chunk.chunk_id)

        unique_chunks.sort(key=lambda x: x.score, reverse=True)
        final_chunks = unique_chunks[:self.top_k]

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