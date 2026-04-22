"""
backend/agents/llm_agent.py
Optimized LLM Reasoning Agent (Gemini)

Improvements:
- Context window trimming
- Token reduction
- Lower latency
- Safer grounding
- Streaming support for faster UX
- reason_direct() for LLM-only answers when RAG confidence is too low
- Intent role mapping extended for canonical intents
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from agents.rag_agent import RagResult
from agents.router_agent import QueryIntent

logger = logging.getLogger("medai.llm")

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

PRIMARY_MODEL  = "models/gemini-2.5-flash"
FALLBACK_MODEL = "models/gemini-2.0-flash-001"

GENERATION_CONFIG = {
    "temperature": 0.15,
    "top_p": 0.85,
    "top_k": 40,
    "max_output_tokens": 1800,
}

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]

# ---------------------------------------------------------------------------
# Context Limits (Token Optimization)
# ---------------------------------------------------------------------------

MAX_CHARS_PER_CHUNK = 1200
MAX_TOTAL_CONTEXT_CHARS = 4000
MAX_REPORT_CHARS = 2000


# ---------------------------------------------------------------------------
# Result Dataclass
# ---------------------------------------------------------------------------

@dataclass
class LLMResult:
    answer: str
    model_used: str
    cited_source_indices: List[int] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# LLM Agent
# ---------------------------------------------------------------------------

class LLMAgent:

    def __init__(self) -> None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY is not set.")
        genai.configure(api_key=api_key)
        self._primary  = genai.GenerativeModel(PRIMARY_MODEL)
        self._fallback = genai.GenerativeModel(FALLBACK_MODEL)

    # ------------------------------------------------------------------

    def reason(
        self,
        query: str,
        rag_result: RagResult,
        intent: QueryIntent,
        image_summary: Optional[str] = None,
        report_text: Optional[str] = None,
    ) -> LLMResult:

        prompt = self._build_prompt(
            query=query,
            rag_result=rag_result,
            intent=intent,
            image_summary=image_summary,
            report_text=report_text,
        )

        try:
            return self._call_gemini_stream(self._primary, prompt, PRIMARY_MODEL)
        except Exception as e:
            logger.warning("Primary model failed: %s", e)
            return self._call_gemini_stream(self._fallback, prompt, FALLBACK_MODEL)

    def reason_direct(
        self,
        query: str,
        intent: QueryIntent = QueryIntent.MEDICAL_QUESTION,
        image_summary: Optional[str] = None,
    ) -> LLMResult:
        """
        Answer the query using Gemini's built-in medical knowledge WITHOUT
        injecting RAG context.

        Used when rag_result.is_relevant is False (confidence < RAG_RELEVANCE_THRESHOLD),
        to avoid polluting the prompt with low-quality retrieved chunks.
        """
        role = self._intent_role(intent)

        image_section = ""
        if image_summary:
            image_section = f"""
## 🔬 Image Analysis Summary
{image_summary}
"""

        prompt = f"""# Medical AI Assistant — {role}

{image_section}## 📝 Instructions
- Answer the question using your medical knowledge.
- Provide a clear, accurate, and evidence-based response.
- Use clear headings and bullet points.
- State any important caveats or limitations.
- Recommend consulting a healthcare professional for personal medical advice.

## ❓ User Question
{query}

## 🩺 Response (Markdown format):
"""

        try:
            return self._call_gemini_stream(self._primary, prompt, PRIMARY_MODEL)
        except Exception as e:
            logger.warning("Primary model failed in reason_direct: %s", e)
            return self._call_gemini_stream(self._fallback, prompt, FALLBACK_MODEL)

    # ------------------------------------------------------------------
    # Prompt Builder
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        query: str,
        rag_result: RagResult,
        intent: QueryIntent,
        image_summary: Optional[str],
        report_text: Optional[str],
    ) -> str:

        role = self._intent_role(intent)

        # ---------------- Patient Report ----------------
        report_section = ""
        if report_text and report_text.strip():
            trimmed_report = report_text.strip()[:MAX_REPORT_CHARS]
            report_section = f"""
## 📋 Patient Report
{trimmed_report}
"""
        # ---------------- Retrieved Chunks ----------------
        rag_section = "## 📚 Retrieved Medical Evidence\n\n"
        total_chars = 0
        entries = []

        for i, chunk in enumerate(rag_result.chunks, start=1):

            trimmed_text = chunk.text.strip()[:MAX_CHARS_PER_CHUNK]

            entry = (
                f"**[Source {i}]** "
                f"(similarity: {chunk.score:.2f})\n"
                f"{trimmed_text}"
            )

            if total_chars + len(entry) > MAX_TOTAL_CONTEXT_CHARS:
                break

            entries.append(entry)
            total_chars += len(entry)

        if entries:
            rag_section += "\n\n---\n\n".join(entries)
        else:
            rag_section += "_No high-confidence evidence retrieved._"

        # ---------------- Image Section ----------------
        image_section = ""
        if image_summary:
            image_section = f"""
## 🔬 Image Analysis Summary
{image_summary}
"""

        # ---------------- Instructions ----------------
        conf = rag_result.confidence
        conf_label = "HIGH" if conf >= 0.65 else "MODERATE" if conf >= 0.45 else "LOW"

        instructions = f"""
## 📝 Instructions
- Cite evidence as [Source 1], [Source 2], etc.
- Do NOT introduce medical facts outside provided evidence.
- If evidence is insufficient, clearly state limitations.
- Use clear headings and bullet points.
- Provide medical information, not diagnosis.

## ❓ User Question
{query}

## 📊 Retrieval Confidence: {conf:.1%} ({conf_label})

## 🩺 Response (Markdown format):
"""

        prompt = (
            f"# Medical AI Assistant — {role}\n\n"
            f"{report_section}"
            f"{image_section}"
            f"{rag_section}\n\n"
            f"{instructions}"
        )

        return prompt

    # ------------------------------------------------------------------

    @staticmethod
    def _intent_role(intent: QueryIntent) -> str:
        roles = {
            # Canonical intents
            QueryIntent.MEDICAL_QUESTION:  "General Medical Knowledge Q&A",
            QueryIntent.REPORT_ANALYSIS:   "Patient Report Analysis",
            QueryIntent.IMAGE_DIAGNOSIS:   "Medical Image Interpretation",
            # Legacy intents (backward compatibility)
            QueryIntent.GENERAL_KNOWLEDGE: "General Medical Knowledge Q&A",
            QueryIntent.PATIENT_REPORT:    "Patient Report Analysis",
            QueryIntent.HYBRID:            "Integrated Patient + Image Analysis",
        }
        return roles.get(intent, "Medical Consultation")

    # ------------------------------------------------------------------
    # Streaming Gemini call (STEP 3 - Streaming Implementation)
    # ------------------------------------------------------------------

    @staticmethod
    def _call_gemini_stream(model, prompt: str, model_name: str) -> LLMResult:
        """Execute a streaming Gemini generate call and accumulate the response."""
        
        # Use streaming for faster UX perception
        response_stream = model.generate_content(
            prompt,
            generation_config=GENERATION_CONFIG,
            safety_settings=SAFETY_SETTINGS,
            stream=True  # Enable streaming
        )

        # Accumulate all chunks
        full_text = ""
        for chunk in response_stream:
            if chunk.text:
                full_text += chunk.text

        if not full_text.strip():
            raise ValueError("Empty Gemini response")

        # Note: Token usage metadata is not available in streaming mode
        # Will be empty, which is acceptable trade-off for speed

        logger.info("Gemini streaming response accumulated: %d chars", len(full_text))

        return LLMResult(
            answer=full_text.strip(),
            model_used=model_name,
            prompt_tokens=0,  # Not available in streaming
            completion_tokens=0,  # Not available in streaming
            total_tokens=0,  # Not available in streaming
            raw_metadata={},  # No metadata in streaming
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_llm_agent: LLMAgent | None = None


def get_llm_agent() -> LLMAgent:
    global _llm_agent
    if _llm_agent is None:
        _llm_agent = LLMAgent()
    return _llm_agent


def reason(
    query: str,
    rag_result: RagResult,
    intent: QueryIntent,
    image_summary: Optional[str] = None,
    report_text: Optional[str] = None,
) -> LLMResult:

    return get_llm_agent().reason(
        query=query,
        rag_result=rag_result,
        intent=intent,
        image_summary=image_summary,
        report_text=report_text,
    )