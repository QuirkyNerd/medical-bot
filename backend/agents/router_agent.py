"""
backend/agents/router_agent.py
================================
Agent 1 — Intelligent Query Router

Enhancements:
  • Adds semantic tiering: FOUNDATIONAL vs RESEARCH
  • Enables metadata-aware RAG weighting
  • Maintains compatibility with existing orchestrator
  • Still rule-based (no extra LLM call)
  • Extended with canonical intents: MEDICAL_QUESTION, REPORT_ANALYSIS, IMAGE_DIAGNOSIS
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("medai.router")


# ---------------------------------------------------------------------------
# Intent enum (Backward Compatible)
# ---------------------------------------------------------------------------

class QueryIntent(str, Enum):
    # ---------------------------------------------------------------------------
    # Canonical intents (used by orchestrator routing branches)
    # ---------------------------------------------------------------------------
    MEDICAL_QUESTION  = "medical_question"   # text Q&A → RAG + LLM
    REPORT_ANALYSIS   = "report_analysis"    # uploaded report → ReportAgent
    IMAGE_DIAGNOSIS   = "image_diagnosis"    # uploaded image → ImageAgent + LLM

    # ---------------------------------------------------------------------------
    # Legacy intents (preserved for backward compatibility)
    # ---------------------------------------------------------------------------
    GENERAL_KNOWLEDGE = "general_knowledge"
    PATIENT_REPORT    = "patient_report"
    HYBRID            = "hybrid"

    # Semantic tiers (used for metadata boosting in RAG)
    FOUNDATIONAL      = "foundational"
    RESEARCH          = "research"


# ---------------------------------------------------------------------------
# Mapping: legacy intent → canonical intent
# ---------------------------------------------------------------------------

LEGACY_TO_CANONICAL: dict["QueryIntent", "QueryIntent"] = {
    QueryIntent.GENERAL_KNOWLEDGE: QueryIntent.MEDICAL_QUESTION,
    QueryIntent.FOUNDATIONAL:      QueryIntent.MEDICAL_QUESTION,
    QueryIntent.RESEARCH:          QueryIntent.MEDICAL_QUESTION,
    QueryIntent.PATIENT_REPORT:    QueryIntent.REPORT_ANALYSIS,
    QueryIntent.HYBRID:            QueryIntent.IMAGE_DIAGNOSIS,
    # Canonical intents map to themselves
    QueryIntent.MEDICAL_QUESTION:  QueryIntent.MEDICAL_QUESTION,
    QueryIntent.REPORT_ANALYSIS:   QueryIntent.REPORT_ANALYSIS,
    QueryIntent.IMAGE_DIAGNOSIS:   QueryIntent.IMAGE_DIAGNOSIS,
}


def to_canonical(intent: "QueryIntent") -> "QueryIntent":
    """Map any legacy intent to its canonical counterpart."""
    return LEGACY_TO_CANONICAL.get(intent, QueryIntent.MEDICAL_QUESTION)


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------

@dataclass
class RouterResult:
    intent: QueryIntent
    confidence: float
    reasoning: str


# ---------------------------------------------------------------------------
# Signal sets
# ---------------------------------------------------------------------------

_PATIENT_SIGNALS = {
    "my report", "my test", "my result", "my blood",
    "my scan", "patient report", "lab result",
    "according to my", "i was diagnosed",
    "my hemoglobin", "my sugar", "my creatinine",
    "attached report", "uploaded report",
}

_IMAGE_SIGNALS = {
    "x-ray", "xray", "x ray", "mri", "ct scan",
    "radiology", "radiograph", "brain scan",
    "image attached", "uploaded image",
}

_FOUNDATIONAL_SIGNALS = {
    "what is", "explain", "define", "physiology",
    "anatomy", "symptoms of", "treatment for",
    "difference between", "normal range",
}

_RESEARCH_SIGNALS = {
    "mechanism", "molecular", "pathway",
    "recent study", "clinical trial",
    "meta-analysis", "systematic review",
    "biomarker", "novel therapy",
    "randomized", "evidence-based",
    "glioblastoma", "oncogenic", "gene expression",
}


# ---------------------------------------------------------------------------
# RouterAgent
# ---------------------------------------------------------------------------

class RouterAgent:

    def classify(
        self,
        query: str,
        has_image: bool = False,
        has_report: bool = False,
    ) -> RouterResult:

        query_lower = query.lower().strip()

        image_score        = self._score(query_lower, _IMAGE_SIGNALS)
        patient_score      = self._score(query_lower, _PATIENT_SIGNALS)
        foundational_score = self._score(query_lower, _FOUNDATIONAL_SIGNALS)
        research_score     = self._score(query_lower, _RESEARCH_SIGNALS)

        # -------------------------------------------------------------
        # REPORT ANALYSIS — highest priority when report is attached
        # -------------------------------------------------------------
        if has_report:
            conf = min(0.95, 0.80 + patient_score * 0.05)
            return RouterResult(
                QueryIntent.REPORT_ANALYSIS,
                conf,
                "Medical report uploaded — routing to ReportAgent.",
            )

        # -------------------------------------------------------------
        # IMAGE DIAGNOSIS — when image is attached (or both)
        # -------------------------------------------------------------
        if has_image:
            # If both image and semantic patient signals exist → still image path
            # (orchestrator can optionally layer report context)
            return RouterResult(
                QueryIntent.IMAGE_DIAGNOSIS,
                0.92,
                "Medical image uploaded — routing to ImageAgent.",
            )

        # -------------------------------------------------------------
        # Text signal: image-related keywords without actual image
        # -------------------------------------------------------------
        if image_score >= 1:
            return RouterResult(
                QueryIntent.IMAGE_DIAGNOSIS,
                0.72,
                f"Image-related terms detected (score={image_score}) — routing to ImageAgent.",
            )

        # -------------------------------------------------------------
        # Text signal: patient / report keywords without actual report
        # -------------------------------------------------------------
        if patient_score >= 1:
            conf = min(0.90, 0.70 + patient_score * 0.05)
            return RouterResult(
                QueryIntent.REPORT_ANALYSIS,
                conf,
                f"Patient report signals in query (score={patient_score}) — routing to ReportAgent.",
            )

        # -------------------------------------------------------------
        # MEDICAL QUESTION — research-tier
        # -------------------------------------------------------------
        if research_score > foundational_score and research_score >= 1:
            conf = min(0.95, 0.75 + research_score * 0.05)
            return RouterResult(
                QueryIntent.MEDICAL_QUESTION,
                conf,
                f"Research-style query (score={research_score}) → MEDICAL_QUESTION.",
            )

        # -------------------------------------------------------------
        # MEDICAL QUESTION — foundational-tier
        # -------------------------------------------------------------
        if foundational_score >= 1:
            conf = min(0.92, 0.75 + foundational_score * 0.05)
            return RouterResult(
                QueryIntent.MEDICAL_QUESTION,
                conf,
                f"Foundational medical query (score={foundational_score}) → MEDICAL_QUESTION.",
            )

        # -------------------------------------------------------------
        # DEFAULT — general medical question
        # -------------------------------------------------------------
        return RouterResult(
            QueryIntent.MEDICAL_QUESTION,
            0.65,
            "Defaulted to general medical question.",
        )

    # -------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------
    @staticmethod
    def _score(text: str, signal_set: set[str]) -> int:
        return sum(1 for sig in signal_set if sig in text)


# ---------------------------------------------------------------------------
# Module shortcut
# ---------------------------------------------------------------------------

_router = RouterAgent()


def classify_query(
    query: str,
    has_image: bool = False,
    has_report: bool = False,
) -> RouterResult:
    result = _router.classify(query, has_image, has_report)
    logger.info(
        "Router: intent=%s conf=%.2f | %s",
        result.intent.value,
        result.confidence,
        result.reasoning,
    )
    return result