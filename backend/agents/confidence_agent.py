"""
backend/agents/confidence_agent.py
====================================
Agent 5 — Confidence Evaluator

Responsibilities:
  - Receive the RAG retrieval confidence score
  - Decide if the confidence is sufficient to return directly, OR
  - Trigger one of two fallback strategies:
      A. Web-based evidence retrieval from authoritative sources (PubMed, WHO, CDC)
      B. LLM-only response with explicit disclaimer (when web also fails)
  - Attach confidence badge metadata to the final response

Thresholds:
  HIGH     (≥ 0.65) — RAG answer returned as-is
  MODERATE (0.45–0.65) — RAG answer returned with moderate-confidence badge
  LOW      (< 0.45) — trigger web fallback or LLM-only disclaimer

This agent does NOT modify the answer content; it only wraps the response
with evaluation metadata and may enrich it with web search snippets.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import httpx

logger = logging.getLogger("medai.confidence")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HIGH_THRESHOLD     = 0.65
MODERATE_THRESHOLD = 0.45

PUBMED_SEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
WHO_SEARCH_URL     = "https://www.who.int/api/v1/search"

HTTP_TIMEOUT = 8.0   # seconds


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ConfidenceLevel(str, Enum):
    HIGH     = "HIGH"
    MODERATE = "MODERATE"
    LOW      = "LOW"


@dataclass
class WebSnippet:
    source: str
    title: str
    text: str
    url: str


@dataclass
class ConfidenceResult:
    """Metadata produced by the Confidence Evaluator."""
    level: ConfidenceLevel
    score: float                                # from RAGAgent [0.0, 1.0]
    badge_color: str                            # "green" | "yellow" | "red"
    web_snippets: List[WebSnippet] = field(default_factory=list)
    disclaimer: str = ""
    fallback_used: bool = False                 # True if web/LLM fallback was triggered
    fallback_type: str = ""                     # "web" | "llm_only" | ""

    @property
    def badge_label(self) -> str:
        labels = {
            ConfidenceLevel.HIGH:     "✅ High Confidence",
            ConfidenceLevel.MODERATE: "🟡 Moderate Confidence",
            ConfidenceLevel.LOW:      "🔴 Low Confidence",
        }
        return labels[self.level]

    def to_disclaimer_block(self) -> str:
        """Format a human-readable disclaimer block for appending to the answer."""
        lines = [
            f"\n\n---",
            f"**Confidence Assessment:** {self.badge_label} (score: {self.score:.2f})",
        ]
        if self.disclaimer:
            lines.append(f"_{self.disclaimer}_")
        if self.web_snippets:
            lines.append("\n**Additional Web Sources Retrieved:**")
            for s in self.web_snippets[:2]:
                lines.append(f"- [{s.source}] {s.title}")
        lines.append(
            "\n⚕️ *This information is for educational purposes only. "
            "Always consult a qualified healthcare professional for medical advice.*"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ConfidenceAgent class
# ---------------------------------------------------------------------------

class ConfidenceAgent:
    """
    Evaluates retrieval confidence and optionally enriches the response
    with web-sourced evidence from authoritative medical sources.
    """

    def evaluate(
        self,
        rag_confidence: float,
        query: str,
        current_answer: str,
    ) -> ConfidenceResult:
        """
        Evaluate confidence and optionally trigger fallbacks.

        Args:
            rag_confidence: Confidence score from RAGAgent [0.0, 1.0].
            query:          Original user query (used for web search if needed).
            current_answer: The LLM-generated answer so far.

        Returns:
            ConfidenceResult with badge metadata and optional enrichment.
        """
        level, color = self._classify_confidence(rag_confidence)

        if level == ConfidenceLevel.HIGH:
            return ConfidenceResult(
                level=level,
                score=rag_confidence,
                badge_color=color,
                disclaimer="High-quality medical knowledge retrieved from corpus.",
            )

        if level == ConfidenceLevel.MODERATE:
            return ConfidenceResult(
                level=level,
                score=rag_confidence,
                badge_color=color,
                disclaimer=(
                    "Moderate confidence — answer is grounded in retrieved evidence "
                    "but may not cover all aspects of the query."
                ),
            )

        # LOW confidence — trigger web fallback
        logger.info(
            "Low RAG confidence (%.3f) for query: %.60s — attempting web fallback",
            rag_confidence, query,
        )
        snippets = self._web_search(query)

        if snippets:
            return ConfidenceResult(
                level=level,
                score=rag_confidence,
                badge_color=color,
                web_snippets=snippets,
                fallback_used=True,
                fallback_type="web",
                disclaimer=(
                    "Low corpus confidence. Answer supplemented with snippets "
                    "from PubMed/WHO. Validate with primary clinical sources."
                ),
            )
        else:
            # Web also failed — LLM-only disclaimer
            return ConfidenceResult(
                level=level,
                score=rag_confidence,
                badge_color=color,
                fallback_used=True,
                fallback_type="llm_only",
                disclaimer=(
                    "⚠️ Low retrieval confidence and web search unavailable. "
                    "The answer above is based on general Groq medical knowledge "
                    "without specific source retrieval. Treat with caution."
                ),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_confidence(score: float):
        if score >= HIGH_THRESHOLD:
            return ConfidenceLevel.HIGH, "green"
        elif score >= MODERATE_THRESHOLD:
            return ConfidenceLevel.MODERATE, "yellow"
        else:
            return ConfidenceLevel.LOW, "red"

    def _web_search(self, query: str) -> List[WebSnippet]:
        """
        Attempt to retrieve relevant snippets from PubMed via NCBI E-utilities.
        Falls back silently if the request fails (network error, timeout, etc.).
        """
        try:
            return self._search_pubmed(query)
        except Exception as exc:
            logger.warning("PubMed web search failed: %s", exc)
            return []

    @staticmethod
    def _search_pubmed(query: str) -> List[WebSnippet]:
        """
        Search PubMed for the top 3 relevant article abstracts.
        Uses NCBI E-utilities API (no API key required for basic use).
        """
        # Sanitise query: keep only alphanumeric and spaces
        clean_query = re.sub(r"[^\w\s]", " ", query)[:200]

        # Step 1: Search for article IDs
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            search_resp = client.get(
                PUBMED_SEARCH_URL,
                params={
                    "db": "pubmed",
                    "term": clean_query,
                    "retmax": 3,
                    "retmode": "json",
                    "sort": "relevance",
                },
            )
            search_resp.raise_for_status()
            ids: List[str] = search_resp.json().get("esearchresult", {}).get("idlist", [])

        if not ids:
            return []

        # Step 2: Fetch abstracts
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            fetch_resp = client.get(
                PUBMED_FETCH_URL,
                params={
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "rettype": "abstract",
                    "retmode": "text",
                },
            )
            fetch_resp.raise_for_status()
            raw_text = fetch_resp.text

        # Parse into rough snippets (raw text from NCBI is structured)
        snippets: List[WebSnippet] = []
        # Split on the numbered article sections (1. PMID xxx, 2. PMID xxx, ...)
        articles = re.split(r"\n\d+\.", raw_text)[1:]  # skip preamble

        for i, article_text in enumerate(articles[:3]):
            lines = [ln.strip() for ln in article_text.strip().splitlines() if ln.strip()]
            title = lines[0] if lines else "PubMed Article"
            body  = " ".join(lines[1:4])[:500] if len(lines) > 1 else ""
            pmid  = ids[i] if i < len(ids) else ""
            snippets.append(WebSnippet(
                source="PubMed",
                title=title[:200],
                text=body,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            ))

        logger.info("Retrieved %d PubMed snippets", len(snippets))
        return snippets


# ---------------------------------------------------------------------------
# Module-level convenience instance
# ---------------------------------------------------------------------------

_confidence_agent = ConfidenceAgent()


def evaluate(
    rag_confidence: float,
    query: str,
    current_answer: str,
) -> ConfidenceResult:
    """Module-level shortcut for confidence evaluation."""
    return _confidence_agent.evaluate(rag_confidence, query, current_answer)
