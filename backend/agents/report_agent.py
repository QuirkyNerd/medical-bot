"""
backend/agents/report_agent.py
================================
Agent 5 — Medical Report Analysis Agent

Responsibilities:
  1. Structured Report Extraction
       Extract structured clinical information from raw report text using Gemini.
       Returns a JSON object with: symptoms, lab_results, possible_conditions,
       important_findings, abnormal_values.

  2. Report Question Answering
       Answer patient questions grounded in the extracted report context using Gemini.

  3. Report Hash Caching
       Avoid redundant Gemini API calls by caching extraction results keyed on a hash
       of the report text.

Usage:
    from agents.report_agent import extract_report, answer_report_question
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import google.generativeai as genai

logger = logging.getLogger("medai.report_agent")

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

_EXTRACTION_MODEL  = "models/gemini-2.0-flash-001"
_QA_MODEL          = "models/gemini-2.5-flash"
_FALLBACK_MODEL    = "models/gemini-2.0-flash-001"

_EXTRACTION_CONFIG = {
    "temperature": 0.05,   # near-deterministic for structured extraction
    "top_p": 0.90,
    "top_k": 32,
    "max_output_tokens": 1200,
}

_QA_CONFIG = {
    "temperature": 0.20,
    "top_p": 0.85,
    "top_k": 40,
    "max_output_tokens": 1600,
}

_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]

MAX_REPORT_CHARS = 6000   # Trim very long reports before sending to Gemini


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ReportExtractionResult:
    """Structured clinical data extracted from a medical report."""
    symptoms:             List[str] = field(default_factory=list)
    lab_results:          List[str] = field(default_factory=list)
    possible_conditions:  List[str] = field(default_factory=list)
    important_findings:   List[str] = field(default_factory=list)
    abnormal_values:      List[str] = field(default_factory=list)
    raw_json:             Dict[str, Any] = field(default_factory=dict)
    extraction_error:     Optional[str] = None

    def to_context_string(self) -> str:
        """Format extracted data into a compact text block for the LLM Q&A prompt."""
        lines = []
        if self.symptoms:
            lines.append(f"Symptoms: {', '.join(self.symptoms)}")
        if self.lab_results:
            lines.append(f"Lab Results: {', '.join(self.lab_results)}")
        if self.abnormal_values:
            lines.append(f"Abnormal Values: {', '.join(self.abnormal_values)}")
        if self.possible_conditions:
            lines.append(f"Possible Conditions: {', '.join(self.possible_conditions)}")
        if self.important_findings:
            lines.append(f"Important Findings: {', '.join(self.important_findings)}")
        return "\n".join(lines) if lines else "No structured data could be extracted."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symptoms":             self.symptoms,
            "lab_results":          self.lab_results,
            "possible_conditions":  self.possible_conditions,
            "important_findings":   self.important_findings,
            "abnormal_values":      self.abnormal_values,
        }


@dataclass
class ReportAnswerResult:
    """Answer generated from the report context."""
    answer: str
    model_used: str
    extraction_used: bool = True     # True when extraction context was available
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Report Agent
# ---------------------------------------------------------------------------

class ReportAgent:
    """
    Processes medical reports in two stages:
      1. extract_structured_info()  — Gemini extracts clinical JSON
      2. answer_from_report()       — Gemini reasons over extracted context
    """

    def __init__(self) -> None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY is not set — ReportAgent cannot initialise.")

        genai.configure(api_key=api_key)
        self._extractor = genai.GenerativeModel(_EXTRACTION_MODEL)
        self._qa_model  = genai.GenerativeModel(_QA_MODEL)
        self._fallback  = genai.GenerativeModel(_FALLBACK_MODEL)

        # Simple in-memory cache: report_hash -> ReportExtractionResult
        self._extraction_cache: Dict[str, ReportExtractionResult] = {}

    # ------------------------------------------------------------------
    # Stage 1 — Structured Extraction
    # ------------------------------------------------------------------

    def extract_structured_info(self, report_text: str) -> ReportExtractionResult:
        """
        Extract structured clinical information from raw report text.

        Returns a `ReportExtractionResult`. Caches results by report hash
        to avoid redundant Gemini API calls for identical reports.
        """
        if not report_text or not report_text.strip():
            logger.warning("ReportAgent: empty report_text supplied")
            return ReportExtractionResult(extraction_error="Empty report text provided.")

        # ---- Cache lookup --------------------------------------------------
        report_hash = self._hash_report(report_text)
        if report_hash in self._extraction_cache:
            logger.info("ReportAgent: cache hit for report_hash=%s", report_hash[:8])
            return self._extraction_cache[report_hash]

        # ---- Build extraction prompt ----------------------------------------
        trimmed = report_text.strip()[:MAX_REPORT_CHARS]
        prompt = self._build_extraction_prompt(trimmed)

        # ---- Call Gemini ---------------------------------------------------
        try:
            response = self._extractor.generate_content(
                prompt,
                generation_config=_EXTRACTION_CONFIG,
                safety_settings=_SAFETY_SETTINGS,
            )
            raw_text = response.text.strip()
            result = self._parse_extraction_response(raw_text)
        except Exception as exc:
            logger.error("ReportAgent: extraction failed: %s", exc)
            result = ReportExtractionResult(extraction_error=str(exc))

        # ---- Cache and return -----------------------------------------------
        self._extraction_cache[report_hash] = result
        logger.info(
            "ReportAgent: extracted report | symptoms=%d, labs=%d, findings=%d",
            len(result.symptoms),
            len(result.lab_results),
            len(result.important_findings),
        )
        return result

    # ------------------------------------------------------------------
    # Stage 2 — Q&A from Report
    # ------------------------------------------------------------------

    def answer_from_report(
        self,
        question: str,
        extracted_report: ReportExtractionResult,
        original_report_text: Optional[str] = None,
    ) -> ReportAnswerResult:
        """
        Answer a patient question grounded in the structured report context.

        Falls back to the original report text when extraction produced no
        structured data (e.g., extraction error).
        """
        # Build context — prefer structured extraction, fall back to raw text
        if extracted_report.extraction_error or not any([
            extracted_report.symptoms,
            extracted_report.lab_results,
            extracted_report.important_findings,
            extracted_report.abnormal_values,
            extracted_report.possible_conditions,
        ]):
            context = (original_report_text or "").strip()[:MAX_REPORT_CHARS]
            extraction_used = False
            logger.warning("ReportAgent: using raw report text for Q&A (extraction unavailable)")
        else:
            context = extracted_report.to_context_string()
            extraction_used = True

        if not context:
            return ReportAnswerResult(
                answer="I could not find any report content to answer from.",
                model_used=_QA_MODEL,
                extraction_used=False,
                error="No report context available.",
            )

        prompt = self._build_qa_prompt(question=question, report_context=context)

        try:
            result = self._call_gemini_stream(self._qa_model, prompt, _QA_MODEL)
            return ReportAnswerResult(
                answer=result,
                model_used=_QA_MODEL,
                extraction_used=extraction_used,
            )
        except Exception as primary_err:
            logger.warning("ReportAgent: primary QA model failed: %s", primary_err)
            try:
                result = self._call_gemini_stream(self._fallback, prompt, _FALLBACK_MODEL)
                return ReportAnswerResult(
                    answer=result,
                    model_used=_FALLBACK_MODEL,
                    extraction_used=extraction_used,
                )
            except Exception as fallback_err:
                logger.error("ReportAgent: fallback QA also failed: %s", fallback_err)
                return ReportAnswerResult(
                    answer="I was unable to process your report at this time.",
                    model_used=_FALLBACK_MODEL,
                    extraction_used=False,
                    error=str(fallback_err),
                )

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_extraction_prompt(report_text: str) -> str:
        return f"""You are a clinical data extraction AI. Your job is to parse a raw medical report
and extract structured clinical information as valid JSON.

## Medical Report
{report_text}

## Instructions
Extract the following fields from the report above. Be concise and accurate.
Return ONLY a valid JSON object with these exact keys (arrays of strings):

{{
  "symptoms": [],
  "lab_results": [],
  "possible_conditions": [],
  "important_findings": [],
  "abnormal_values": []
}}

Guidelines:
- "symptoms" — patient-reported or observed clinical symptoms (e.g., "fatigue", "chest pain")
- "lab_results" — test results with values (e.g., "HbA1c: 8.2%", "WBC: 11,000/uL")
- "possible_conditions" — physician-noted diagnoses or differential findings
- "important_findings" — key findings worth attention (e.g., "bilateral infiltrates on CXR")
- "abnormal_values" — lab or vital values outside normal range (e.g., "HbA1c > 7% (elevated)")
- Return empty arrays [] for fields with no information in the report.
- Do NOT include explanation outside the JSON object.

JSON:"""

    @staticmethod
    def _build_qa_prompt(question: str, report_context: str) -> str:
        return f"""You are a compassionate and knowledgeable medical AI assistant.
You are answering a patient's question about their medical report.

## Extracted Report Context
{report_context}

## Instructions
- Answer ONLY based on the report context above.
- Do NOT introduce medical facts not present in the report.
- Explain findings clearly in plain language the patient can understand.
- If an abnormal value is present, explain what it may indicate and suggest consulting a doctor.
- Use bullet points and clear headings.
- End with a recommendation to consult the patient's physician for personalized advice.

## Patient Question
{question}

## Answer (Markdown format):"""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_report(report_text: str) -> str:
        return hashlib.sha256(report_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_extraction_response(raw_text: str) -> ReportExtractionResult:
        """Parse Gemini's JSON response into a ReportExtractionResult."""
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            raw_text = "\n".join(lines[start:end])

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error("ReportAgent: JSON parse error: %s | raw=%r", exc, raw_text[:200])
            return ReportExtractionResult(extraction_error=f"JSON parse error: {exc}")

        def _to_list(val: Any) -> List[str]:
            if isinstance(val, list):
                return [str(v).strip() for v in val if v]
            return []

        return ReportExtractionResult(
            symptoms=            _to_list(data.get("symptoms")),
            lab_results=         _to_list(data.get("lab_results")),
            possible_conditions= _to_list(data.get("possible_conditions")),
            important_findings=  _to_list(data.get("important_findings")),
            abnormal_values=     _to_list(data.get("abnormal_values")),
            raw_json=            data,
        )

    @staticmethod
    def _call_gemini_stream(model, prompt: str, model_name: str) -> str:
        """Stream from Gemini and accumulate the full response text."""
        stream = model.generate_content(
            prompt,
            generation_config=_QA_CONFIG,
            safety_settings=_SAFETY_SETTINGS,
            stream=True,
        )
        text = ""
        for chunk in stream:
            if chunk.text:
                text += chunk.text
        if not text.strip():
            raise ValueError(f"Empty Gemini response from {model_name}")
        return text.strip()


# ---------------------------------------------------------------------------
# Singleton + module-level convenience functions
# ---------------------------------------------------------------------------

_report_agent: Optional[ReportAgent] = None


def _get_report_agent() -> ReportAgent:
    global _report_agent
    if _report_agent is None:
        _report_agent = ReportAgent()
    return _report_agent


def extract_report(report_text: str) -> ReportExtractionResult:
    """
    Module-level shortcut — extract structured clinical info from a report.
    Results are cached by report hash.
    """
    return _get_report_agent().extract_structured_info(report_text)


def answer_report_question(
    question: str,
    extracted_report: ReportExtractionResult,
    original_report_text: Optional[str] = None,
) -> ReportAnswerResult:
    """Module-level shortcut — answer a question grounded in the extracted report."""
    return _get_report_agent().answer_from_report(
        question=question,
        extracted_report=extracted_report,
        original_report_text=original_report_text,
    )
