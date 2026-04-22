"""
backend/core/ingestion.py
==========================
Offline ingestion pipeline for medical documents.

Responsibilities:
  - Read PDF files (using PyMuPDF) or raw text strings
  - Chunk with sliding window (500 tokens, 100 token overlap)
  - Tag each chunk with structured metadata
  - Embed chunks using the singleton Embedder
  - Upsert into Qdrant via VectorStore

Metadata schema per chunk:
  {
    "source":       str,   # filename or URL
    "doc_type":     str,   # "textbook" | "report" | "guideline" | "web"
    "page":         int,   # page number in PDF (0 if N/A)
    "chunk_index":  int,   # sequential chunk number within source
    "disease":      str,   # optional, from caller
    "organ_system": str,   # optional, from caller
  }

Usage:
    from core.ingestion import Ingestion
    ing = Ingestion()
    count = ing.ingest_pdf("path/to/book.pdf", "global_knowledge", {"doc_type": "textbook"})
    count = ing.ingest_text("Patient has diabetes...", "patient_specific", {"doc_type": "report"})
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

from core.embedder import get_embedder
from core.vectorstore import Chunk, get_vectorstore

logger = logging.getLogger("medai.ingestion")

# ---------------------------------------------------------------------------
# Chunking parameters
# ---------------------------------------------------------------------------
CHUNK_SIZE_CHARS = 2000          # ~500 tokens at ~4 chars/token
CHUNK_OVERLAP_CHARS = 400        # ~100 token overlap for context continuity


# ---------------------------------------------------------------------------
# Ingestion class
# ---------------------------------------------------------------------------

class Ingestion:
    """
    Orchestrates the document ingestion pipeline:
      PDF/text → chunks → embeddings → Qdrant upsert
    """

    def __init__(self) -> None:
        self._embedder = get_embedder()
        self._vs = get_vectorstore()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_pdf(
        self,
        pdf_path: str,
        collection: str,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback=None,
    ) -> int:
        """
        Ingest a PDF file into a Qdrant collection.

        Args:
            pdf_path:          Absolute or relative path to the PDF file.
            collection:        Target Qdrant collection ("global_knowledge" or "patient_specific").
            metadata:          Extra metadata tags applied to all chunks from this file.
            progress_callback: Optional callable(current, total) for progress updates.

        Returns:
            Number of chunks ingested.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info("Ingesting PDF: %s → '%s'", path.name, collection)

        base_meta = {
            "source": path.name,
            "doc_type": "textbook",
            "page": 0,
            **(metadata or {}),
        }

        doc = fitz.open(str(path))
        all_chunks: List[Chunk] = []

        page_count = len(doc)
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if not text.strip():
                continue

            page_chunks = self._chunk_text(text)
            for idx, chunk_text in enumerate(page_chunks):
                chunk_meta = {
                    **base_meta,
                    "page": page_num + 1,
                    "chunk_index": idx,
                }
                all_chunks.append(
                    Chunk(
                        text=chunk_text,
                        vector=[],       # filled after batch embedding
                        metadata=chunk_meta,
                    )
                )

            if progress_callback:
                progress_callback(page_num + 1, page_count)

        doc.close()

        total = self._embed_and_upsert(all_chunks, collection)
        logger.info("PDF ingestion complete: %d chunks from %s", total, path.name)
        return total

    def ingest_text(
        self,
        text: str,
        collection: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Ingest a raw text string into a Qdrant collection.

        Args:
            text:       Raw text content.
            collection: Target Qdrant collection.
            metadata:   Extra metadata tags applied to all chunks.

        Returns:
            Number of chunks ingested.
        """
        if not text or not text.strip():
            logger.warning("ingest_text called with empty text; skipping.")
            return 0

        base_meta = {
            "source": "inline_text",
            "doc_type": "report",
            "page": 0,
            **(metadata or {}),
        }

        text_chunks = self._chunk_text(text)
        chunks = [
            Chunk(
                text=chunk_text,
                vector=[],
                metadata={**base_meta, "chunk_index": idx},
            )
            for idx, chunk_text in enumerate(text_chunks)
        ]

        total = self._embed_and_upsert(chunks, collection)
        logger.info("Text ingestion complete: %d chunks → '%s'", total, collection)
        return total

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping character-level chunks.

        Strategy:
          1. Normalise whitespace
          2. Split into chunks of CHUNK_SIZE_CHARS with CHUNK_OVERLAP_CHARS overlap
          3. Prefer splitting on sentence boundaries ('. ', '\\n') when possible

        Returns:
            List of non-empty text chunks.
        """
        # Normalise: collapse multiple blank lines, strip leading/trailing whitespace
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        if len(text) <= CHUNK_SIZE_CHARS:
            return [text] if text else []

        chunks: List[str] = []
        start = 0

        while start < len(text):
            end = start + CHUNK_SIZE_CHARS

            if end < len(text):
                # Try to end at a sentence boundary near the chunk end
                boundary = self._find_boundary(text, end)
                end = boundary

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move forward by (CHUNK_SIZE - OVERLAP) to create overlap
            start = end - CHUNK_OVERLAP_CHARS
            if start <= 0 or start >= len(text):
                break

        return chunks

    @staticmethod
    def _find_boundary(text: str, end: int, search_window: int = 200) -> int:
        """
        Look backwards from `end` to find a good sentence/paragraph break.
        Falls back to the original `end` if no boundary is found.
        """
        search_start = max(0, end - search_window)
        segment = text[search_start:end]

        # Prefer paragraph break
        para_pos = segment.rfind("\n\n")
        if para_pos != -1:
            return search_start + para_pos + 2

        # Then sentence end
        for sep in (". ", "! ", "? ", "\n"):
            pos = segment.rfind(sep)
            if pos != -1:
                return search_start + pos + len(sep)

        return end

    def _embed_and_upsert(self, chunks: List[Chunk], collection: str) -> int:
        """Batch-embed all chunks then upsert into Qdrant."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        vectors = self._embedder.embed_batch(texts)

        for chunk, vector in zip(chunks, vectors):
            chunk.vector = vector

        return self._vs.upsert_chunks(collection, chunks)
