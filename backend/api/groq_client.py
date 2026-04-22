"""
backend/api/groq_client.py
==========================
Reusable Groq LLM client — OpenAI-compatible interface.

Models:
  • Primary  : llama-3.3-70b-versatile
  • Fallback : llama-3.1-8b-instant

Usage::

    from api.groq_client import groq_complete

    answer = groq_complete(
        query="What causes hypertension?",
        context_chunks=["chunk1 text ...", "chunk2 text ..."],
    )
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

logger = logging.getLogger("medai.groq_client")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
PRIMARY_MODEL  = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"

MEDICAL_SYSTEM_PROMPT = (
    "You are an advanced Medical AI Assistant. "
    "Provide responses in the following structured format:\n\n"
    "## 1. Possible Causes\n"
    "## 2. Symptoms Explanation\n"
    "## 3. Recommended Actions\n"
    "## 4. When to Consult a Doctor\n\n"
    "Ensure responses are medically accurate and professional. "
    "Always use clear headings, bullet points, and proper spacing. "
    "DO NOT cut off your response mid-sentence. Ensure you finish your final thought completely. "
    "Always remind users to seek professional medical advice for personal health concerns."
)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GroqResult:
    answer: str
    model_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    sources: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Add it to backend/.env or your environment before starting the server."
        )
    return key


def _build_user_message(query: str, context_chunks: List[str]) -> str:
    """Assemble the user turn with RAG context + query."""
    if context_chunks:
        context_block = "\n\n---\n\n".join(
            f"[Source {i + 1}]\n{chunk.strip()}"
            for i, chunk in enumerate(context_chunks)
        )
        return (
            "## Retrieved Medical Context\n\n"
            f"{context_block}\n\n"
            "---\n\n"
            f"## Question\n{query}"
        )
    return f"## Question\n{query}"


def _call_groq(
    api_key: str,
    model: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 1800,
) -> dict:
    """Make a synchronous HTTP call to the Groq chat-completions endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Groq API returned {response.status_code}: {response.text}"
        )

    return response.json()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def groq_complete(
    query: str,
    context_chunks: Optional[List[str]] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2500,
) -> GroqResult:
    """
    Send a query (with optional RAG chunks) to Groq and return a GroqResult.

    Args:
        query:          The user's medical query.
        context_chunks: Retrieved RAG chunks to inject as context (optional).
        system_prompt:  Override the default medical system prompt (optional).
        temperature:    Sampling temperature.
        max_tokens:     Maximum output tokens.

    Returns:
        GroqResult with answer text, model used, and token usage.

    Raises:
        EnvironmentError: If GROQ_API_KEY is not set.
        RuntimeError:     If both primary and fallback models fail.
    """
    api_key = _get_api_key()
    chunks  = context_chunks or []

    messages = [
        {
            "role": "system",
            "content": system_prompt or MEDICAL_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": _build_user_message(query, chunks),
        },
    ]

    # Source labels for the response
    sources = [f"Source {i + 1}" for i in range(len(chunks))]

    # ── Try primary ──────────────────────────────────────────────────────────
    try:
        logger.info("Groq primary request | model=%s | chunks=%d", PRIMARY_MODEL, len(chunks))
        data = _call_groq(api_key, PRIMARY_MODEL, messages, temperature, max_tokens)
        usage = data.get("usage", {})
        answer = data["choices"][0]["message"]["content"]

        logger.info("Groq primary success | tokens=%d", usage.get("total_tokens", 0))

        return GroqResult(
            answer=answer,
            model_used=PRIMARY_MODEL,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            sources=sources,
        )

    except Exception as primary_err:
        logger.warning("Groq primary model failed: %s — trying fallback", primary_err)

    # ── Fallback ─────────────────────────────────────────────────────────────
    try:
        logger.info("Groq fallback request | model=%s", FALLBACK_MODEL)
        data = _call_groq(api_key, FALLBACK_MODEL, messages, temperature, max_tokens)
        usage = data.get("usage", {})
        answer = data["choices"][0]["message"]["content"]

        logger.info("Groq fallback success | tokens=%d", usage.get("total_tokens", 0))

        return GroqResult(
            answer=answer,
            model_used=FALLBACK_MODEL,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            sources=sources,
        )

    except Exception as fallback_err:
        raise RuntimeError(
            f"Both Groq models failed. "
            f"Primary: {primary_err}. "
            f"Fallback: {fallback_err}."
        ) from fallback_err
