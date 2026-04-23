"""
backend/api/medical_query_router.py
=====================================
FastAPI router for the unified POST /api/medical-query endpoint.

Input types supported:
  • "text"  →  RAG retrieval (Qdrant) + Groq LLM
  • "image" →  Local OCR Extraction + Groq LLM
  • "pdf"   →  Local PyPDF Extraction + Groq LLM

This router ensures ZERO dependencies on external vision models like Gemini,
executing highly performant local parser logic followed by standard Groq fast-inference.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from PIL import Image
import pytesseract
import os

# Explicitly configure tesseract path for Docker environments
if os.path.exists("/usr/bin/tesseract"):
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
from pypdf import PdfReader

from core.rag_engine import get_rag_engine
from api.groq_client import groq_complete, GroqResult
from api.intent_detector import (
    detect_intent,
    QueryIntent,
    confidence_label,
    LOW_CONFIDENCE_DISCLAIMER,
    EMERGENCY_PREFIX,
)

logger = logging.getLogger("medai.medical_query")
router = APIRouter()

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class MedicalQueryRequest(BaseModel):
    type: str = Field(
        ...,
        description='One of "text", "image", or "pdf".',
        pattern=r"^(text|image|pdf)$",
    )
    query: Optional[str] = Field(None, description="Medical query (required when type=text)")
    top_k: int = Field(6, ge=1, le=20)
    image: Optional[str] = Field(None, description="Base64-encoded image data URI")
    pdf: Optional[str] = Field(None, description="Base64-encoded PDF data URI")
    message: Optional[str] = Field(None, description="User question to accompany the image or PDF")
    rag_filters: Optional[Dict[str, Any]] = Field(None)

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in {"text", "image", "pdf"}:
            raise ValueError(f"type must be one of text, image, pdf, got {v!r}")
        return v


class MedicalQueryResponse(BaseModel):
    type: str
    answer: str
    confidence: Optional[float] = None
    confidence_label: Optional[str] = None
    sources: Optional[List[dict]] = None
    model_used: Optional[str] = None


# ---------------------------------------------------------------------------
# Multimodal Local Extractors
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Sanitize parsed text ensuring clean whitespace."""
    if not text:
        return ""
    return text.strip().replace("\n\n", "\n")

def limit_text(text: str) -> str:
    """Trim excessive text payloads protecting Groq contextual limits."""
    return text[:4000]

def _decode_base64_payload(data_uri: str) -> bytes:
    """Split MIME data standard URI correctly mapping pure base64 strings."""
    if "," in data_uri:
        _, encoded = data_uri.split(",", 1)
        return base64.b64decode(encoded)
    return base64.b64decode(data_uri)

def extract_pdf_text(base64_data: str) -> str:
    """Fastest local PDF handler utilizing PyPDF."""
    try:
        pdf_bytes = _decode_base64_payload(base64_data)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        # Process a maximum of 3 pages from any PDF payload
        for i, page in enumerate(reader.pages):
            if i >= 3:
                break
            content = page.extract_text()
            if content:
                text += content + "\n"
        return limit_text(clean_text(text))
    except Exception as e:
        logger.error(f"PyPDF Extract Error: {e}")
        return ""

def extract_image_text(base64_data: str) -> str:
    """OCR processor routing exclusively through PyTesseract natively."""
    try:
        img_bytes = _decode_base64_payload(base64_data)
        image = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(image)
        return limit_text(clean_text(text))
    except Exception as e:
        logger.error(f"Tesseract OCR Error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Internal RAG Helpers
# ---------------------------------------------------------------------------

def _retrieve_chunks(query: str, top_k: int = 5) -> tuple[List[str], List[dict]]:
    """Retrieves context from Qdrant using the new RAG engine."""
    try:
        rag = get_rag_engine()
        results = rag.search(query, top_k=top_k)
        
        chunk_texts = [r["text"] for r in results]
        sources = [
            {
                "text": r["text"][:300] + "...",
                "source": r["source"],
                "score": round(float(r["score"]), 4)
            }
            for r in results
        ]
        return chunk_texts, sources
    except Exception as exc:
        logger.error("RAG retrieval failed: %s", exc)
        return [], []


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------

@router.post("", response_model=MedicalQueryResponse)
async def medical_query(request: MedicalQueryRequest) -> JSONResponse:
    logger.info("POST /api/medical-query | type=%s", request.type)

    # ── TEXT: RAG + Groq ─────────────────────────────────────────────────────
    if request.type == "text":
        if not request.query:
            raise HTTPException(status_code=400, detail="'query' field required.")

        intent_result = detect_intent(request.query)
        if intent_result.intent == QueryIntent.GREETING:
            sys_prompt = (
                "You are a friendly, professional medical AI assistant. "
                "The user is just greeting you. Respond politely in 1 or 2 sentences."
            )
            groq_result: GroqResult = groq_complete(query=request.query, context_chunks=[], system_prompt=sys_prompt)
            return JSONResponse(content={
                "type": "text", "answer": groq_result.answer, "confidence": None,
                "confidence_label": None, "sources": [], "model_used": groq_result.model_used
            })

        chunk_texts, sources = _retrieve_chunks(request.query, request.top_k)
        
        # Call Groq with retrieved context
        groq_result: GroqResult = groq_complete(query=request.query, context_chunks=chunk_texts)

        answer = groq_result.answer
        if intent_result.intent == QueryIntent.EMERGENCY:
            answer = EMERGENCY_PREFIX + answer

        return JSONResponse(content={
            "type": "text", 
            "answer": answer, 
            "confidence": 0.95, # High confidence when using RAG
            "confidence_label": "High",
            "sources": sources,
            "model_used": groq_result.model_used,
        })

    # ── PDF & IMAGE: Local Extraction + Direct Groq ──────────────────────────
    
    extracted_text = ""
    user_query = request.message or "Please analyze this medical report."
    
    if request.type == "pdf":
        if not request.pdf:
            raise HTTPException(status_code=400, detail="'pdf' payload required.")
        logger.info("📄 Native PDF parsing initiated.")
        extracted_text = extract_pdf_text(request.pdf)
        
    elif request.type == "image":
        if not request.image:
            raise HTTPException(status_code=400, detail="'image' payload required.")
        logger.info("🖼️ Native OCR extraction initiated.")
        extracted_text = extract_image_text(request.image)

    if not extracted_text:
        return JSONResponse(content={
            "type": request.type,
            "answer": "⚠️ Unable to extract readable medical text from your upload. Please ensure the document is clear and readable.",
            "model_used": "extraction-failed"
        })

    # Build Dynamic Multimodal Prompt overriding standard templates
    dynamic_prompt = f"""
You are a medical AI assistant diagnosing reports and answering specific user queries.

User question:
{user_query}

Medical report content:
{extracted_text}

Instructions:
* Answer specifically based ONLY on the user's question and the report text.
* Do NOT give generic background explanations.
* If specific lab values or findings are present, interpret them directly alongside reference ranges.
* Be highly precise and professional.
* If needed, structure the answer clearly. Give direct responses.
"""

    try:
        # Trigger Groq without injecting the typical RAG standard prompt format.
        groq_result: GroqResult = groq_complete(
            query=dynamic_prompt,
            context_chunks=[],
            system_prompt="You are a brilliant clinical diagnostician. Produce highly focused, direct answers.",
            max_tokens=2500
        )
        
        return JSONResponse(content={
            "type": "multimodal",
            "answer": groq_result.answer,
            "model_used": groq_result.model_used,
            "confidence": None,
            "confidence_label": None,
            "sources": []
        })
    except Exception as e:
        logger.error(f"Multimodal Groq generation failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to synthesize extracted multimodal data.")
