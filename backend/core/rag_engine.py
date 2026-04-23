import os
import logging
import uuid
import re
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("medai.rag_engine")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTION_NAME = "medical_knowledge"
VECTOR_SIZE = 384  # Matches all-MiniLM-L6-v2
DISTANCE = qdrant_models.Distance.COSINE

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# ---------------------------------------------------------------------------
# RAG Engine Class
# ---------------------------------------------------------------------------

class RAGEngine:
    def __init__(self):
        # Initialize Qdrant Client
        if not QDRANT_URL:
            logger.warning("QDRANT_URL not set. RAG features will be unavailable.")
            self.client = None
        else:
            self.client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
            )
            self._ensure_collection()

        # Initialize Embedding Model (Singleton-like behavior via class instance)
        logger.info("Loading embedding model: all-MiniLM-L6-v2")
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.info("Embedding model loaded successfully.")

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
        """Chunks text, embeds, and stores in Qdrant."""
        if not self.client:
            logger.error("Qdrant client not initialized.")
            return 0

        # Refined chunking: 400 "tokens" (words) with 50 overlap
        chunks = self._chunk_text(text, chunk_size=400, overlap=50)
        points = []

        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            # Load model once and encode
            embedding = self.model.encode(chunk_text).tolist()

            # Ensure metadata matches user requirements
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

        # Batch upsert in chunks of 100 to avoid request size limits
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
        """Ingests a list of documents, each being a dict with 'text' and 'source'."""
        total = 0
        for doc in documents:
            text = doc.get("text")
            source = doc.get("source", "unknown")
            meta = doc.get("metadata", {})
            if text:
                total += self.ingest_text(text, source, meta)
        return total

    def _chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """
        Splits text into chunks of chunk_size words with overlap.
        """
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        words = text.split()
        
        if not words:
            return []

        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk = " ".join(chunk_words).strip()
            if chunk:
                chunks.append(chunk)
            
            # Stop if we've reached the end
            if i + chunk_size >= len(words):
                break
                
        return chunks

    # -----------------------------------------------------------------------
    # Retrieval Logic
    # -----------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs semantic search and returns relevant chunks."""
        if not self.client:
            return []

        query_vector = self.model.encode(query).tolist()

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

    def delete_all(self):
        """Clears the collection."""
        if not self.client:
            return
        
        try:
            self.client.delete_collection(collection_name=COLLECTION_NAME)
            self._ensure_collection()
            logger.info(f"Collection {COLLECTION_NAME} cleared.")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")

# ---------------------------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------------------------

_rag_engine = None

def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
