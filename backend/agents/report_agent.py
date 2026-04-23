"""
backend/agents/report_agent.py
================================
Medical Report Analysis Agent using Groq.
"""

import logging
from typing import Optional, List, Dict, Any
from agents.llm_agent import get_llm_agent

logger = logging.getLogger("medai.report_agent")

class ReportAgent:
    def __init__(self) -> None:
        self.llm = get_llm_agent()

    def analyze_report(self, report_text: str, question: Optional[str] = None) -> str:
        """
        Analyzes a medical report and answers a specific question if provided.
        """
        if not report_text or not report_text.strip():
            return "No report text provided for analysis."

        user_query = question or "Please provide a comprehensive summary of this medical report."
        
        # Construct a prompt for Groq to handle both extraction and reasoning in one go
        # as Groq models are powerful enough for this.
        prompt = f"""
You are a clinical diagnostician. Analyze the following medical report and answer the user's question accurately.

MEDICAL REPORT:
{report_text}

USER QUESTION:
{user_query}

INSTRUCTIONS:
1. Extract key findings, lab values, and symptoms.
2. Interpret the results in plain language.
3. Highlight any abnormal values.
4. Recommend next steps or specialist consultations if needed.
5. Provide a professional, structured response.
"""
        return self.llm.generate_response(prompt)

# Singleton
_report_agent = None

def get_report_agent() -> ReportAgent:
    global _report_agent
    if _report_agent is None:
        _report_agent = ReportAgent()
    return _report_agent

def analyze_report(report_text: str, question: Optional[str] = None) -> str:
    return get_report_agent().analyze_report(report_text, question)
