import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pypdf import PdfReader
import io

from core.rag_engine import get_rag_engine

logger = logging.getLogger("medai.rag_router")
router = APIRouter()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    text: Optional[str] = None
    source: Optional[str] = "api_upload"

class SearchResponse(BaseModel):
    query: str
    results: List[dict]

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/ingest", summary="Ingest raw text or PDF into knowledge base")
async def ingest_data(
    text: Optional[str] = Form(None),
    source: Optional[str] = Form("api_upload"),
    file: Optional[UploadFile] = File(None)
):
    rag = get_rag_engine()
    total_chunks = 0
    
    try:
        # 1. Handle PDF File
        if file and file.filename.endswith(".pdf"):
            content = await file.read()
            pdf_reader = PdfReader(io.BytesIO(content))
            extracted_text = ""
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
            
            if extracted_text.strip():
                total_chunks += rag.ingest_text(extracted_text, source=file.filename)
                logger.info(f"Ingested PDF {file.filename}")

        # 2. Handle Raw Text
        if text and text.strip():
            total_chunks += rag.ingest_text(text, source=source)
            logger.info("Ingested raw text from form.")

        if total_chunks == 0:
            return JSONResponse(
                status_code=400,
                content={"error": "No valid text found to ingest. Provide 'text' or a '.pdf' file."}
            )

        return {"message": "Ingestion successful", "chunks": total_chunks}

    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=SearchResponse, summary="Search the knowledge base (Debug)")
async def search_knowledge(q: str, top_k: int = 5):
    rag = get_rag_engine()
    results = rag.search(q, top_k=top_k)
    return {"query": q, "results": results}

@router.delete("/clear-knowledge", summary="Wipe the vector database")
async def clear_knowledge():
    rag = get_rag_engine()
    rag.delete_all()
    return {"message": "Knowledge base cleared successfully."}
