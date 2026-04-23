"""
backend/agents/llm_agent.py
==========================
Production-ready LLM Reasoning Agent using ONLY Groq.
"""

import os
import logging
from typing import List, Optional
from api.groq_client import groq_complete, GroqResult

logger = logging.getLogger("medai.llm_agent")

class LLMAgent:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. LLM features will be unavailable.")

    def generate_response(self, query: str, context: Optional[List[str]] = None) -> str:
        """
        Sends a query (and optional RAG context) to Groq.
        """
        logger.info(f"Generating Groq response for query: {query[:50]}...")
        
        try:
            result: GroqResult = groq_complete(
                query=query,
                context_chunks=context,
            )
            return result.answer
        except Exception as e:
            logger.error(f"Groq generation failed: {e}")
            return "I apologize, but I am currently unable to process your request. Please try again later."

# Singleton
_llm_agent = None

def get_llm_agent() -> LLMAgent:
    global _llm_agent
    if _llm_agent is None:
        _llm_agent = LLMAgent()
    return _llm_agent