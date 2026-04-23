"""
backend/core/orchestrator.py
==============================
Unified Orchestrator for Medical AI.
Routes queries through RAG, Image Analysis, or Report Analysis.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.confidence_agent import evaluate as eval_confidence
from agents.image_agent import analyze_image
from agents.llm_agent import get_llm_agent
from agents.rag_agent import RagAgent, RagResult
from agents.report_agent import analyze_report
from agents.router_agent import QueryIntent, RouterResult, classify_query

logger = logging.getLogger("medai.orchestrator")

@dataclass
class AgentResponse:
    answer: str
    confidence_score: float
    confidence_level: str
    badge_color: str
    badge_label: str
    sources: List[Dict[str, Any]]
    model_used: str
    intent: str
    total_latency_ms: int = 0

class Orchestrator:
    def __init__(self):
        self.llm = get_llm_agent()
        self.rag = RagAgent()

    def run(self, query: str, image_data: Optional[bytes | str] = None, report_text: Optional[str] = None) -> AgentResponse:
        t_start = time.perf_counter()
        
        # 1. Classify Intent
        router_result: RouterResult = classify_query(
            query=query,
            has_image=image_data is not None,
            has_report=report_text is not None
        )
        
        intent = router_result.intent
        answer = ""
        sources = []
        rag_conf = 0.0

        # 2. Route Execution
        if intent == QueryIntent.REPORT_ANALYSIS:
            answer = analyze_report(report_text, question=query)
        elif intent == QueryIntent.IMAGE_DIAGNOSIS:
            img_result = analyze_image(image_data)
            answer = self.llm.generate_response(f"IMAGE ANALYSIS SUMMARY: {img_result.structured_summary}\n\nUSER QUERY: {query}")
        else:
            # RAG flow
            rag_result: RagResult = self.rag.retrieve(query)
            context = [c.text for c in rag_result.chunks]
            answer = self.llm.generate_response(query, context=context)
            sources = [{"text": c.text, "source": c.source, "score": c.score} for c in rag_result.chunks]
            rag_conf = rag_result.confidence

        # 3. Evaluate Confidence
        conf_result = eval_confidence(rag_conf, query, answer)
        
        total_latency = int((time.perf_counter() - t_start) * 1000)

        return AgentResponse(
            answer=answer + conf_result.to_disclaimer_block(),
            confidence_score=conf_result.score,
            confidence_level=conf_result.level.value,
            badge_color=conf_result.badge_color,
            badge_label=conf_result.badge_label,
            sources=sources,
            model_used="llama3-70b-8192",
            intent=intent.value,
            total_latency_ms=total_latency
        )

# Singleton
_orchestrator = Orchestrator()

def orchestrate(query: str, image_data: Optional[bytes | str] = None, report_text: Optional[str] = None) -> AgentResponse:
    return _orchestrator.run(query, image_data, report_text)