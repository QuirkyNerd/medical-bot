import os
from dotenv import load_dotenv
import logging
import uuid
import re
import time
import requests
from typing import List, Dict, Any, Optional
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger("medai.rag_engine")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VECTOR_SIZE = 384  # Matches all-MiniLM-L6-v2
TABLE_NAME = "documents"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")
HF_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
HF_API_URL = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"

# ---------------------------------------------------------------------------
# Embedding Utility
# ---------------------------------------------------------------------------

def get_embedding(text: str, retries: int = 3, delay: int = 2) -> List[float]:
    """
    Calls HuggingFace Router Inference API to get embeddings for a single text string.
    """
    if not HF_API_KEY:
        logger.error("HF_API_KEY not set. Embedding failed.")
        return [0.0] * VECTOR_SIZE

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for attempt in range(retries):
        try:
            response = requests.post(
                HF_API_URL,
                headers=headers,
                json={"inputs": text},
                timeout=15
            )
            
            if response.status_code == 200:
                embedding = response.json()
                
                # Router API returns nested list: [[0.1, 0.2, ...]]
                if isinstance(embedding, list) and len(embedding) > 0 and isinstance(embedding[0], list):
                    embedding = embedding[0]
                
                if isinstance(embedding, list) and len(embedding) == VECTOR_SIZE:
                    return embedding
                
                logger.error(f"Unexpected embedding dimension: {len(embedding) if isinstance(embedding, list) else type(embedding)}")
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
        # Initialize Supabase Client
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("SUPABASE_URL or SUPABASE_KEY not set.")
            raise ValueError("Supabase configuration missing.")

        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info(f"RAG Engine initialized using Supabase and HF API ({HF_MODEL_ID})")

    # -----------------------------------------------------------------------
    # Ingestion Logic
    # -----------------------------------------------------------------------

    def ingest_text(self, text: str, source: str = "manual_upload", metadata: Optional[Dict] = None) -> int:
        """Chunks text, embeds via API, and stores in Supabase."""
        # Chunking: 400 words with 50 overlap
        chunks = self._chunk_text(text, chunk_size=400, overlap=50)
        data_to_insert = []

        logger.info(f"Processing {len(chunks)} chunks for {source} via HF API...")

        for i, chunk_text in enumerate(chunks):
            # Use API instead of local model
            embedding = get_embedding(chunk_text)

            # Prepare record for Supabase
            payload = {
                "content": chunk_text,
                "embedding": embedding,
                "metadata": {
                    "source": source,
                    "chunk_id": i,
                    "type": metadata.get("type", "unknown") if metadata else "unknown",
                    **(metadata or {})
                }
            }
            data_to_insert.append(payload)

        # Batch insert into Supabase
        if data_to_insert:
            try:
                # Supabase handles batch insert natively with lists
                self.supabase.table(TABLE_NAME).insert(data_to_insert).execute()
                logger.info(f"Ingested {len(data_to_insert)} chunks from {source} into Supabase")
            except Exception as e:
                logger.error(f"Supabase ingestion failed: {e}")
                return 0
        
        return len(data_to_insert)

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
        """Performs semantic search via Supabase RPC."""
        # Get query embedding via API
        query_vector = get_embedding(query)

        try:
            # Call the match_documents RPC function in Supabase
            response = self.supabase.rpc("match_documents", {
                "query_embedding": query_vector,
                "match_count": top_k
            }).execute()
            
            results = response.data
            
            return [
                {
                    "text": item.get("content"),
                    "source": item.get("metadata", {}).get("source"),
                    "score": item.get("similarity"), # pgvector returns similarity
                    "metadata": item.get("metadata", {})
                }
                for item in results
            ]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def status(self) -> Dict[str, Any]:
        """Returns statistics about the vector store."""
        try:
            # Simple count query
            response = self.supabase.table(TABLE_NAME).select("id", count="exact").execute()
            count = response.count if response.count is not None else 0
            return {
                "status": "ok",
                "database": "Supabase (PostgreSQL + pgvector)",
                "total_documents": count
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"status": "error", "detail": str(e)}

    def delete_by_source(self, source: str):
        """Deletes all points associated with a specific source."""
        try:
            # Note: metadata is jsonb, so we use arrow operator for filtering
            self.supabase.table(TABLE_NAME).delete().filter("metadata->>source", "eq", source).execute()
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

