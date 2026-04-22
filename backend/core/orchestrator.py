"""
backend/core/orchestrator.py
==============================
Central agent orchestration loop.

Extended routing flow:
  MEDICAL_QUESTION  → RAG retrieval → threshold check → LLM(context|direct)
  REPORT_ANALYSIS   → ReportAgent.extract() → ReportAgent.answer()
  IMAGE_DIAGNOSIS   → ImageAgent → optional RAG context → LLM explanation

All original capabilities preserved:
  - RAG pipeline  (Qdrant)
  - Image analysis (CNN classifiers)
  - Gemini LLM integration
  - Confidence scoring / web fallback
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.confidence_agent import ConfidenceResult, evaluate as eval_confidence
from agents.image_agent import ImageResult, analyze_image
from agents.llm_agent import LLMResult, get_llm_agent
from agents.rag_agent import RagAgent, RagResult
from core.vectorstore import get_vectorstore
from agents.report_agent import (
    ReportAnswerResult,
    ReportExtractionResult,
    answer_report_question,
    extract_report,
)
from agents.router_agent import QueryIntent, RouterResult, classify_query

logger = logging.getLogger("medai.orchestrator")

# Empty RAG result sentinel — reused when RAG is skipped
_EMPTY_RAG = RagResult(chunks=[], confidence=0.0)


# ---------------------------------------------------------------------------
# Response Contract
# ---------------------------------------------------------------------------

@dataclass
class AgentTrace:
    router:     Dict[str, Any] = field(default_factory=dict)
    rag:        Dict[str, Any] = field(default_factory=dict)
    image:      Dict[str, Any] = field(default_factory=dict)
    report:     Dict[str, Any] = field(default_factory=dict)
    llm:        Dict[str, Any] = field(default_factory=dict)
    confidence: Dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0


@dataclass
class AgentResponse:
    answer: str
    confidence_score: float
    confidence_level: str
    badge_color: str
    badge_label: str
    sources: List[Dict[str, Any]]
    agent_trace: AgentTrace
    model_used: str
    disclaimer: str
    intent: str
    has_image_analysis: bool = False
    image_label: Optional[str] = None
    image_confidence: Optional[float] = None
    web_fallback_used: bool = False
    total_latency_ms: int = 0
    report_extraction: Optional[Dict[str, Any]] = None   # structured JSON from ReportAgent


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:

    def run(
        self,
        query: str,
        image_data: Optional[bytes | str] = None,
        image_modality: str = "auto",
        report_text: Optional[str] = None,
        rag_filters: Optional[Dict[str, Any]] = None,
        top_k: int = 6,
    ) -> AgentResponse:

        t_start = time.perf_counter()
        trace = AgentTrace()
        llm = get_llm_agent()

        # ---------------------------------------------------
        # 1️⃣ Router Agent
        # ---------------------------------------------------
        t0 = time.perf_counter()

        router_result: RouterResult = classify_query(
            query=query,
            has_image=image_data is not None,
            has_report=bool(report_text),
        )

        intent: QueryIntent = router_result.intent

        trace.router = {
            "intent":     intent.value,
            "confidence": router_result.confidence,
            "reasoning":  router_result.reasoning,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

        logger.info("ORCH | Router → intent=%s", intent.value)

        # ---------------------------------------------------
        # Route by canonical intent
        # ---------------------------------------------------

        if intent == QueryIntent.REPORT_ANALYSIS:
            return self._run_report_analysis(
                query=query,
                report_text=report_text,
                router_result=router_result,
                trace=trace,
                t_start=t_start,
            )

        if intent == QueryIntent.IMAGE_DIAGNOSIS:
            return self._run_image_diagnosis(
                query=query,
                image_data=image_data,
                image_modality=image_modality,
                rag_filters=rag_filters,
                top_k=top_k,
                router_result=router_result,
                trace=trace,
                t_start=t_start,
            )

        # Default: MEDICAL_QUESTION
        return self._run_medical_question(
            query=query,
            rag_filters=rag_filters,
            top_k=top_k,
            intent=intent,
            router_result=router_result,
            trace=trace,
            t_start=t_start,
        )

    # =========================================================
    # Pipeline: MEDICAL_QUESTION
    # =========================================================

    def _run_medical_question(
        self,
        query: str,
        rag_filters: Optional[Dict],
        top_k: int,
        intent: QueryIntent,
        router_result: RouterResult,
        trace: AgentTrace,
        t_start: float,
    ) -> AgentResponse:
        llm = get_llm_agent()

        # -- RAG retrieval with dynamic top_k ---
        t0 = time.perf_counter()
        vectorstore = get_vectorstore()

        probe: RagResult = RagAgent(vectorstore, top_k=3).retrieve(query=query, intent=intent, filters=rag_filters)

        if probe.confidence > 0.75:
            optimized_k = 3
        elif probe.confidence > 0.50:
            optimized_k = 5
        else:
            optimized_k = top_k

        rag_result: RagResult = RagAgent(vectorstore, top_k=optimized_k).retrieve(
            query=query, intent=intent, filters=rag_filters
        )

        rag_latency = int((time.perf_counter() - t0) * 1000)

        trace.rag = {
            "chunks_retrieved":  len(rag_result.chunks),
            "confidence":        rag_result.confidence,
            "is_relevant":       rag_result.is_relevant,
            "threshold":         0.60,
            "collections":       rag_result.collections_searched,
            "optimized_top_k":   optimized_k,
            "latency_ms":        rag_latency,
        }

        logger.info(
            "ORCH | RAG → %d chunks conf=%.3f is_relevant=%s",
            len(rag_result.chunks), rag_result.confidence, rag_result.is_relevant,
        )

        # -- LLM reasoning (threshold decision) ---
        t0 = time.perf_counter()

        if rag_result.is_relevant:
            logger.info("ORCH | RAG confidence %.3f >= 0.60 → grounded LLM reasoning", rag_result.confidence)
            llm_result: LLMResult = llm.reason(
                query=query,
                rag_result=rag_result,
                intent=intent,
            )
            rag_used = True
        else:
            logger.info("ORCH | RAG confidence %.3f < 0.60 → direct LLM reasoning (no context)", rag_result.confidence)
            llm_result = llm.reason_direct(query=query, intent=intent)
            rag_used = False

        trace.llm = {
            "model":        llm_result.model_used,
            "total_tokens": llm_result.total_tokens,
            "answer_length": len(llm_result.answer),
            "rag_used":     rag_used,
            "latency_ms":   int((time.perf_counter() - t0) * 1000),
        }

        # -- Confidence + assembly ---
        return self._assemble_response(
            query=query,
            llm_result=llm_result,
            rag_result=rag_result if rag_used else _EMPTY_RAG,
            intent=intent,
            trace=trace,
            t_start=t_start,
        )

    # =========================================================
    # Pipeline: REPORT_ANALYSIS
    # =========================================================

    def _run_report_analysis(
        self,
        query: str,
        report_text: Optional[str],
        router_result: RouterResult,
        trace: AgentTrace,
        t_start: float,
    ) -> AgentResponse:

        if not report_text or not report_text.strip():
            # No actual report text — fall back to medical question
            logger.warning("ORCH | REPORT_ANALYSIS intent but no report_text — falling back to MEDICAL_QUESTION")
            return self._run_medical_question(
                query=query,
                rag_filters=None,
                top_k=6,
                intent=QueryIntent.MEDICAL_QUESTION,
                router_result=router_result,
                trace=trace,
                t_start=t_start,
            )

        # Stage 1: Extraction
        t0 = time.perf_counter()
        extraction: ReportExtractionResult = extract_report(report_text)
        extract_ms = int((time.perf_counter() - t0) * 1000)

        trace.report = {
            "stage":               "extraction_complete",
            "symptoms_found":      len(extraction.symptoms),
            "lab_results_found":   len(extraction.lab_results),
            "findings_found":      len(extraction.important_findings),
            "extraction_error":    extraction.extraction_error,
            "latency_ms":          extract_ms,
        }

        logger.info(
            "ORCH | ReportAgent extraction → symptoms=%d labs=%d findings=%d",
            len(extraction.symptoms), len(extraction.lab_results), len(extraction.important_findings),
        )

        # Stage 2: Q&A
        t0 = time.perf_counter()
        qa_result: ReportAnswerResult = answer_report_question(
            question=query,
            extracted_report=extraction,
            original_report_text=report_text,
        )
        qa_ms = int((time.perf_counter() - t0) * 1000)

        trace.report["qa_latency_ms"] = qa_ms
        trace.report["model_used"] = qa_result.model_used
        trace.report["extraction_used"] = qa_result.extraction_used

        trace.llm = {
            "model":         qa_result.model_used,
            "answer_length": len(qa_result.answer),
            "rag_used":      False,
            "latency_ms":    qa_ms,
        }

        logger.info("ORCH | ReportAgent Q&A → model=%s chars=%d", qa_result.model_used, len(qa_result.answer))

        # Build a minimal ConfidenceResult for the report path
        t0 = time.perf_counter()
        conf_result: ConfidenceResult = eval_confidence(
            rag_confidence=router_result.confidence,  # use router confidence as proxy
            query=query,
            current_answer=qa_result.answer,
        )
        trace.confidence = {
            "level":          conf_result.level.value,
            "score":          conf_result.score,
            "fallback_used":  conf_result.fallback_used,
            "latency_ms":     int((time.perf_counter() - t0) * 1000),
        }

        final_answer = qa_result.answer + conf_result.to_disclaimer_block()
        total_ms = int((time.perf_counter() - t_start) * 1000)
        trace.latency_ms = total_ms

        return AgentResponse(
            answer=final_answer,
            confidence_score=conf_result.score,
            confidence_level=conf_result.level.value,
            badge_color=conf_result.badge_color,
            badge_label=conf_result.badge_label,
            sources=[{
                "index": 1,
                "source": "patient_report",
                "doc_type": "report",
                "score": round(router_result.confidence, 4),
                "text_preview": report_text[:250] + "…" if len(report_text) > 250 else report_text,
            }],
            agent_trace=trace,
            model_used=qa_result.model_used,
            disclaimer=conf_result.disclaimer,
            intent=QueryIntent.REPORT_ANALYSIS.value,
            total_latency_ms=total_ms,
            report_extraction=extraction.to_dict(),
        )

    # =========================================================
    # Pipeline: IMAGE_DIAGNOSIS
    # =========================================================

    def _run_image_diagnosis(
        self,
        query: str,
        image_data: Optional[bytes | str],
        image_modality: str,
        rag_filters: Optional[Dict],
        top_k: int,
        router_result: RouterResult,
        trace: AgentTrace,
        t_start: float,
    ) -> AgentResponse:
        llm = get_llm_agent()

        if image_data is None:
            # No actual image — text query about imaging, route to medical question
            logger.warning("ORCH | IMAGE_DIAGNOSIS intent but no image_data — falling back to MEDICAL_QUESTION")
            return self._run_medical_question(
                query=query,
                rag_filters=rag_filters,
                top_k=top_k,
                intent=QueryIntent.MEDICAL_QUESTION,
                router_result=router_result,
                trace=trace,
                t_start=t_start,
            )

        # -- Image analysis ---
        t0 = time.perf_counter()
        image_result: Optional[ImageResult] = None
        try:
            image_result = analyze_image(image_data, modality_hint=image_modality)
            trace.image = {
                "modality":       image_result.modality.value,
                "top_label":      image_result.top_label,
                "top_confidence": image_result.top_confidence,
                "latency_ms":     int((time.perf_counter() - t0) * 1000),
            }
            logger.info(
                "ORCH | ImageAgent → %s (%.1f%%)",
                image_result.top_label, image_result.top_confidence * 100,
            )
        except Exception as img_err:
            logger.error("ORCH | ImageAgent failed: %s", img_err)
            trace.image = {"error": str(img_err)}

        # -- Optional: RAG retrieval keyed on image prediction ---
        image_query = (
            f"{image_result.top_label} {image_modality}"
            if image_result else query
        )

        t0 = time.perf_counter()
        vectorstore = get_vectorstore()
        rag_result: RagResult = RagAgent(vectorstore, top_k=top_k).retrieve(
            query=image_query,
            intent=QueryIntent.IMAGE_DIAGNOSIS,
            filters=rag_filters,
        )

        trace.rag = {
            "chunks_retrieved": len(rag_result.chunks),
            "confidence":       rag_result.confidence,
            "is_relevant":      rag_result.is_relevant,
            "threshold":        0.60,
            "collections":      rag_result.collections_searched,
            "latency_ms":       int((time.perf_counter() - t0) * 1000),
        }

        # -- LLM reasoning over image + optional RAG ---
        t0 = time.perf_counter()
        image_summary = image_result.structured_summary if image_result else None

        if rag_result.is_relevant:
            logger.info("ORCH | IMAGE: RAG relevant (%.3f) → grounded LLM", rag_result.confidence)
            llm_result: LLMResult = llm.reason(
                query=query,
                rag_result=rag_result,
                intent=QueryIntent.IMAGE_DIAGNOSIS,
                image_summary=image_summary,
            )
            rag_used = True
        else:
            logger.info("ORCH | IMAGE: RAG low (%.3f) → direct LLM with image summary", rag_result.confidence)
            llm_result = llm.reason_direct(
                query=query,
                intent=QueryIntent.IMAGE_DIAGNOSIS,
                image_summary=image_summary,
            )
            rag_used = False

        trace.llm = {
            "model":         llm_result.model_used,
            "answer_length": len(llm_result.answer),
            "rag_used":      rag_used,
            "latency_ms":    int((time.perf_counter() - t0) * 1000),
        }

        return self._assemble_response(
            query=query,
            llm_result=llm_result,
            rag_result=rag_result if rag_used else _EMPTY_RAG,
            intent=QueryIntent.IMAGE_DIAGNOSIS,
            trace=trace,
            t_start=t_start,
            image_result=image_result,
        )

    # =========================================================
    # Shared: Confidence + Response assembly
    # =========================================================

    def _assemble_response(
        self,
        query: str,
        llm_result: LLMResult,
        rag_result: RagResult,
        intent: QueryIntent,
        trace: AgentTrace,
        t_start: float,
        image_result: Optional[ImageResult] = None,
    ) -> AgentResponse:

        t0 = time.perf_counter()
        conf_result: ConfidenceResult = eval_confidence(
            rag_confidence=rag_result.confidence,
            query=query,
            current_answer=llm_result.answer,
        )

        trace.confidence = {
            "level":        conf_result.level.value,
            "score":        conf_result.score,
            "fallback_used": conf_result.fallback_used,
            "fallback_type": conf_result.fallback_type,
            "latency_ms":   int((time.perf_counter() - t0) * 1000),
        }

        logger.info("ORCH | Confidence → %s (fallback=%s)", conf_result.level.value, conf_result.fallback_used)

        final_answer = llm_result.answer + conf_result.to_disclaimer_block()

        if conf_result.web_snippets:
            snippet_block = "\n\n**📡 Web-Retrieved Supplementary Evidence:**\n"
            snippet_block += "\n".join(
                f"- [{s.source}] [{s.title}]({s.url}): {s.text[:200]}…"
                for s in conf_result.web_snippets
            )
            final_answer += snippet_block

        # Build sources list
        sources = [
            {
                "index":        i + 1,
                "source":       c.metadata.get("source", "rag"),
                "page":         c.metadata.get("page", 0),
                "doc_type":     c.metadata.get("doc_type", ""),
                "score":        round(c.score, 4),
                "text_preview": (c.text[:250] + "…" if len(c.text) > 250 else c.text),
            }
            for i, c in enumerate(rag_result.chunks)
        ]

        # Append image_model source if image was analysed
        if image_result:
            sources.append({
                "index":        len(sources) + 1,
                "source":       "image_model",
                "doc_type":     "cnn_prediction",
                "modality":     image_result.modality.value,
                "top_label":    image_result.top_label,
                "score":        round(image_result.top_confidence, 4),
                "text_preview": image_result.structured_summary[:250],
            })

        total_ms = int((time.perf_counter() - t_start) * 1000)
        trace.latency_ms = total_ms

        return AgentResponse(
            answer=final_answer,
            confidence_score=conf_result.score,
            confidence_level=conf_result.level.value,
            badge_color=conf_result.badge_color,
            badge_label=conf_result.badge_label,
            sources=sources,
            agent_trace=trace,
            model_used=llm_result.model_used,
            disclaimer=conf_result.disclaimer,
            intent=intent.value,
            has_image_analysis=image_result is not None,
            image_label=image_result.top_label if image_result else None,
            image_confidence=image_result.top_confidence if image_result else None,
            web_fallback_used=conf_result.fallback_used,
            total_latency_ms=total_ms,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_orchestrator = Orchestrator()


def orchestrate(
    query: str,
    image_data: Optional[bytes | str] = None,
    image_modality: str = "auto",
    report_text: Optional[str] = None,
    rag_filters: Optional[Dict[str, Any]] = None,
    top_k: int = 6,
) -> AgentResponse:

    return _orchestrator.run(
        query=query,
        image_data=image_data,
        image_modality=image_modality,
        report_text=report_text,
        rag_filters=rag_filters,
        top_k=top_k,
    )