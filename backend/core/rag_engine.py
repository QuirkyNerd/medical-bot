import os
from dotenv import load_dotenv
import logging
import uuid
import re
import time
import requests

load_dotenv()
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

logger = logging.getLogger("medai.rag_engine")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTION_NAME = "medical_knowledge"
VECTOR_SIZE = 384  # Matches all-MiniLM-L6-v2
DISTANCE = qdrant_models.Distance.COSINE

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")
HF_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
HF_API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_MODEL_ID}"

# ---------------------------------------------------------------------------
# Embedding Utility
# ---------------------------------------------------------------------------

def get_embedding(text: str, retries: int = 3, delay: int = 2) -> List[float]:
    """
    Calls HuggingFace Inference API to get embeddings for a single text string.
    Includes retry logic and timeouts.
    """
    if not HF_API_KEY:
        logger.error("HF_API_KEY not set. Embedding failed.")
        return [0.0] * VECTOR_SIZE

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    
    for attempt in range(retries):
        try:
            response = requests.post(
                HF_API_URL,
                headers=headers,
                json={"inputs": [text], "options": {"wait_for_model": True}},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                # Feature extraction returns List[List[float]] or List[float] depending on input
                if isinstance(result, list) and len(result) > 0:
                    embedding = result[0]
                    if len(embedding) == VECTOR_SIZE:
                        return embedding
                logger.error(f"Unexpected HF API response format: {result}")
            elif response.status_code == 503:
                logger.warning(f"HF Model loading (503). Retrying in {delay}s...")
            else:
                logger.error(f"HF API Error {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"HF API Request failed (Attempt {attempt+1}): {e}")
        
        time.sleep(delay * (attempt + 1))
    
    return [0.0] * VECTOR_SIZE

# ---------------------------------------------------------------------------
# RAG Engine Class
# ---------------------------------------------------------------------------

class RAGEngine:
    def __init__(self):
        # Initialize Qdrant Client
        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not self.qdrant_url:
            raise ValueError("QDRANT_URL not set")

        self.client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
        )
        self._ensure_collection()

        logger.info(f"RAG Engine initialized using HF Inference API ({HF_MODEL_ID})")

    def _ensure_collection(self):
        """Creates the collection if it doesn't exist."""
        if not self.client:
            return

        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == COLLECTION_NAME for c in collections)

            if not exists:
                logger.info(f"Creating Qdrant collection: {COLLECTION_NAME}")
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=qdrant_models.VectorParams(
                        size=VECTOR_SIZE,
                        distance=DISTANCE,
                    ),
                )
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")

    def init_collection(self):
        """Alias for _ensure_collection to match standard API."""
        self._ensure_collection()

    # -----------------------------------------------------------------------
    # Ingestion Logic
    # -----------------------------------------------------------------------

    def ingest_text(self, text: str, source: str = "manual_upload", metadata: Optional[Dict] = None) -> int:
        """Chunks text, embeds via API, and stores in Qdrant."""
        if not self.client:
            logger.error("Qdrant client not initialized.")
            return 0

        # Chunking: 400 words with 50 overlap
        chunks = self._chunk_text(text, chunk_size=400, overlap=50)
        points = []

        logger.info(f"Processing {len(chunks)} chunks for {source} via HF API...")

        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            
            # Use API instead of local model
            embedding = get_embedding(chunk_text)

            # Ensure metadata matches requirements
            payload = {
                "text": chunk_text,
                "source": source,
                "chunk_id": i,
                "type": metadata.get("type", "unknown") if metadata else "unknown",
                **(metadata or {})
            }

            points.append(
                qdrant_models.PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload=payload
                )
            )

        # Batch upsert
        if points:
            for i in range(0, len(points), 100):
                batch = points[i:i + 100]
                self.client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=batch
                )
            logger.info(f"Ingested {len(points)} chunks from {source}")
        
        return len(points)

    def ingest_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Ingests a list of documents."""
        total = 0
        for doc in documents:
            text = doc.get("text")
            source = doc.get("source", "unknown")
            meta = doc.get("metadata", {})
            if text:
                total += self.ingest_text(text, source, meta)
        return total

    def _chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """Splits text into chunks."""
        text = re.sub(r'\s+', ' ', text).strip()
        words = text.split()
        if not words: return []

        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk = " ".join(chunk_words).strip()
            if chunk: chunks.append(chunk)
            if i + chunk_size >= len(words): break
        return chunks

    # -----------------------------------------------------------------------
    # Retrieval Logic
    # -----------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs semantic search via API embedding."""
        if not self.client:
            return []

        # Get query embedding via API
        query_vector = get_embedding(query)

        try:
            results = self.client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True
            )
            
            return [
                {
                    "text": hit.payload.get("text"),
                    "source": hit.payload.get("source"),
                    "score": hit.score,
                    "metadata": hit.payload
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def status(self) -> Dict[str, Any]:
        """Returns statistics about the vector store."""
        if not self.client:
            return {"status": "unavailable"}
        
        try:
            collection_info = self.client.get_collection(collection_name=COLLECTION_NAME)
            return {
                "status": "ok",
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "indexed_vectors": collection_info.indexed_vectors_count
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"status": "error", "detail": str(e)}

    def delete_by_source(self, source: str):
        """Deletes all points associated with a specific source."""
        if not self.client: return
        
        try:
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="source",
                                match=qdrant_models.MatchValue(value=source)
                            )
                        ]
                    )
                )
            )
            logger.info(f"Deleted points for source: {source}")
        except Exception as e:
            logger.error(f"Error deleting by source: {e}")

# ---------------------------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------------------------

_rag_engine = None

def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine

