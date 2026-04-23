"""
backend/core/ingestion.py
==========================
Consolidated ingestion pipeline using the centralized RAGEngine.
"""

import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import fitz  # PyMuPDF
import xml.etree.ElementTree as ET
from core.rag_engine import get_rag_engine

logger = logging.getLogger("medai.ingestion")

class Ingestion:
    def __init__(self) -> None:
        self.rag = get_rag_engine()

    def ingest_pdf(self, pdf_path: str, metadata: Optional[Dict] = None) -> int:
        """
        Extracts text from PDF and ingests into Qdrant.
        """
        path = Path(pdf_path)
        if not path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return 0

        try:
            doc = fitz.open(str(path))
            full_text = ""
            for page in doc:
                full_text += page.get_text() + "\n"
            doc.close()

            # Merge metadata with required fields
            final_metadata = {
                "type": "pdf",
                **(metadata or {})
            }

            return self.rag.ingest_text(full_text, source=path.name, metadata=final_metadata)
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            return 0

    def ingest_xml(self, xml_path: str, metadata: Optional[Dict] = None) -> int:
        """
        Parses PubMed XML research papers and ingests into Qdrant.
        """
        path = Path(xml_path)
        if not path.exists():
            logger.error(f"XML not found: {xml_path}")
            return 0

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # PubMed XML typical fields
            title = ""
            abstract = ""
            body = ""

            # Extract Title
            title_node = root.find(".//ArticleTitle")
            if title_node is None:
                title_node = root.find(".//title-group/article-title") # PMC format
            
            if title_node is not None:
                title = "".join(title_node.itertext()).strip()

            # Extract Abstract
            abstract_nodes = root.findall(".//AbstractText")
            if not abstract_nodes:
                abstract_nodes = root.findall(".//abstract") # PMC format
            
            abstract = " ".join(["".join(node.itertext()).strip() for node in abstract_nodes])

            # Extract Body (if exists in full-text XML)
            body_nodes = root.findall(".//body") # Common in PMC full-text
            if not body_nodes:
                # Fallback to paragraphs if body tag is missing
                body_nodes = root.findall(".//p")
            
            body = " ".join(["".join(node.itertext()).strip() for node in body_nodes])

            # Combine as requested
            combined_text = f"TITLE: {title}\nABSTRACT: {abstract}\nBODY: {body}"

            # Merge metadata with required fields
            final_metadata = {
                "type": "research_paper",
                **(metadata or {})
            }

            return self.rag.ingest_text(combined_text, source=path.name, metadata=final_metadata)
        except Exception as e:
            logger.error(f"Error processing XML {xml_path}: {e}")
            return 0

    def ingest_text(self, text: str, source: str = "manual", metadata: Optional[Dict] = None) -> int:
        """
        Ingests raw text into Qdrant.
        """
        return self.rag.ingest_text(text, source=source, metadata=metadata)
