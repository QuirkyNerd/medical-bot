"""
backend/api/routes.py
======================
FastAPI route definitions for the Multi-Agent Medical AI System.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agents.image_agent import analyze_image
from core.ingestion import Ingestion
from core.orchestrator import orchestrate
from core.vectorstore import get_vectorstore

logger = logging.getLogger("medai.routes")
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    image_b64: Optional[str] = None
    image_modality: str = "auto"
    report_text: Optional[str] = None
    top_k: int = Field(6, ge=1, le=20)
    rag_filters: Optional[dict] = None


class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=10)
    source: str = "patient_upload"
    doc_type: str = "report"
    disease: Optional[str] = None
    organ_system: Optional[str] = None


class ImageAnalyzeRequest(BaseModel):
    image_b64: str
    modality: str = "auto"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status")
async def status():
    try:
        vs = get_vectorstore()
        stats = vs.status()

        return {
            "success": True,
            "status": "ok",
            "service": "Multi-Agent Medical AI Backend",
            "version": "1.0.0",
            "qdrant_stats": {
                "global_knowledge": stats.get("global_knowledge", 0),
                "patient_specific": stats.get("patient_specific", 0),
            },
        }
    except Exception as exc:
        logger.exception("Status check failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/query")
async def query_endpoint(request: QueryRequest):
    logger.info("POST /query | query=%.60s | has_image=%s",
                request.query, bool(request.image_b64))

    try:
        result = orchestrate(
            query=request.query,
            image_data=request.image_b64,
            image_modality=request.image_modality,
            report_text=request.report_text,
            rag_filters=request.rag_filters,
            top_k=request.top_k,
        )

        trace = result.agent_trace

        return JSONResponse(content={
            "success": True,   # 🔥 REQUIRED FOR FRONTEND
            "intent":  result.intent,
            "answer":  result.answer,
            "confidence_score": result.confidence_score,
            "confidence_level": result.confidence_level,
            "badge_color":  result.badge_color,
            "badge_label":  result.badge_label,
            "sources":      result.sources,
            "report_extraction": result.report_extraction,  # structured JSON or None
            "agent_trace": {
                "router":     trace.router,
                "rag":        trace.rag,
                "image":      trace.image,
                "report":     trace.report,
                "llm":        trace.llm,
                "confidence": trace.confidence,
                "latency_ms": trace.latency_ms,
            },
            "model_used":        result.model_used,
            "disclaimer":        result.disclaimer,
            "has_image_analysis": result.has_image_analysis,
            "image_label":       result.image_label,
            "image_confidence":  result.image_confidence,
            "web_fallback_used": result.web_fallback_used,
            "total_latency_ms":  result.total_latency_ms,
        })

    except Exception as exc:
        logger.exception("Query pipeline failed")

        # 🔥 Even error responses follow same structure
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc)
            }
        )


@router.post("/image-analyze")
async def image_analyze_endpoint(request: ImageAnalyzeRequest):
    try:
        result = analyze_image(
            image_data=request.image_b64,
            modality_hint=request.modality,
        )

        return {
            "success": True,
            "modality": result.modality.value,
            "top_label": result.top_label,
            "top_confidence": result.top_confidence,
            "top_predictions": [
                {"label": label, "confidence": conf}
                for label, conf in result.top_predictions
            ],
            "structured_summary": result.structured_summary,
            "disclaimer": result.disclaimer,
        }

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc)
            }
        )


@router.post("/ingest")
async def ingest_pdf(
    file: UploadFile = File(...),
    doc_type: str = Form("textbook"),
    disease: Optional[str] = Form(None),
    organ_system: Optional[str] = Form(None),
    source_label: Optional[str] = Form(None),
):
    try:
        import tempfile, os
        content = await file.read()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        metadata = {
            "doc_type": doc_type,
            "disease": disease or "",
            "organ_system": organ_system or "",
            "source": source_label or file.filename,
        }

        ing = Ingestion()
        count = ing.ingest_pdf(tmp_path, "global_knowledge", metadata)
        os.unlink(tmp_path)

        return {
            "success": True,
            "filename": file.filename,
            "chunks_ingested": count,
            "collection": "global_knowledge",
        }

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc)
            }
        )


@router.post("/ingest-patient")
async def ingest_patient_report(request: IngestTextRequest):
    try:
        vs = get_vectorstore()

        try:
            vs.delete_by_source("patient_specific", request.source)
        except Exception:
            pass

        metadata = {
            "source": request.source,
            "doc_type": request.doc_type,
            "disease": request.disease or "",
            "organ_system": request.organ_system or "",
        }

        ing = Ingestion()
        count = ing.ingest_text(request.text, "patient_specific", metadata)

        return {
            "success": True,
            "source": request.source,
            "chunks_ingested": count,
            "collection": "patient_specific",
        }

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc)
            }
        )