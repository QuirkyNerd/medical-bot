"""
backend/api/intent_detector.py
================================
Rule-based intent classifier for medical queries.

Classifies a raw user query into one of four intents:
  • GREETING   — casual salutations, social openers
  • EMERGENCY  — life-threatening keywords requiring urgent action
  • MEDICAL    — symptom/disease/treatment queries → RAG + Groq pipeline
  • GENERAL    — everything else

Design decisions
----------------
- Pure Python, zero external dependencies — runs synchronously before any I/O.
- Signal matching is case-insensitive substring search (no regex overhead for
  the common fast-path; regex used only for the word-boundary EMERGENCY tier).
- Emergency signals are checked FIRST so they can never be misclassified as
  greetings even when both signal sets partially overlap.
- Returns a typed dataclass so callers can pattern-match on .intent string.

Usage::

    from api.intent_detector import detect_intent, QueryIntent

    result = detect_intent("I have chest pain and can't breathe")
    print(result.intent)   # "emergency"
    print(result.label)    # "Emergency"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Intent enum
# ---------------------------------------------------------------------------

class QueryIntent(str, Enum):
    GREETING  = "greeting"
    EMERGENCY = "emergency"
    MEDICAL   = "medical"
    GENERAL   = "general"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IntentResult:
    intent: QueryIntent
    label: str                  # Human-readable label ("Emergency", "Medical", …)
    matched_signals: list[str]  # The signals that triggered classification


# ---------------------------------------------------------------------------
# Signal sets
# (ordered: Emergency > Greeting > Medical > General)
# ---------------------------------------------------------------------------

# Patterns that indicate a genuine medical emergency.
# Using word-boundary-aware patterns to avoid false positives
# (e.g. "chest" in "chest-cold" vs "chest pain").
_EMERGENCY_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bchest\s+pain\b",          re.I),
    re.compile(r"\bheart\s+attack\b",         re.I),
    re.compile(r"\bstroke\b",                 re.I),
    re.compile(r"\bunconscious\b",            re.I),
    re.compile(r"\bnot\s+breathing\b",        re.I),
    re.compile(r"\bcan(?:'t|not)\s+breathe\b",re.I),
    re.compile(r"\bsevere\s+bleeding\b",      re.I),
    re.compile(r"\bheavy\s+bleeding\b",       re.I),
    re.compile(r"\bseizure\b",                re.I),
    re.compile(r"\bfainted\b",                re.I),
    re.compile(r"\boverdose\b",               re.I),
    re.compile(r"\bsuicid",                   re.I),   # suicide / suicidal
    re.compile(r"\bpoisoning\b",              re.I),
    re.compile(r"\banaphylaxis\b",            re.I),
    re.compile(r"\bchok(?:e|ing)\b",          re.I),
    re.compile(r"\bdrowned?\b",               re.I),
    re.compile(r"\bburned?\s+severe\b",       re.I),
    re.compile(r"\bsevere\s+allergic\b",      re.I),
    re.compile(r"\bparalys",                  re.I),   # paralysis / paralyzed
    re.compile(r"\bsevere\s+head\s+injury\b", re.I),
    re.compile(r"\bspinal\s+injury\b",        re.I),
    re.compile(r"\bemergency\b",              re.I),
    re.compile(r"\b911\b|\b108\b|\bambulance\b", re.I),
]

# Simple greeting signals — substring match is fine here.
_GREETING_SIGNALS: frozenset[str] = frozenset({
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "good night", "how are you", "how r you", "what's up", "whats up",
    "sup ", "greetings", "howdy", "hiya", "yo ", "namaste", "salaam",
    "helo", "hii", "heya", "howdy",
})

# Medical intent signals — covers symptoms, conditions, drugs, procedures.
_MEDICAL_SIGNALS: frozenset[str] = frozenset({
    # Symptoms / conditions
    "symptom", "diagnosis", "disease", "disorder", "syndrome", "condition",
    "pain", "ache", "fever", "cough", "cold", "headache", "nausea",
    "vomiting", "diarrhea", "diarrhoea", "fatigue", "tiredness", "rash",
    "swelling", "inflammation", "infection", "allergy", "allergic",
    "bleeding", "bruise", "fracture", "injury", "wound",
    "shortness of breath", "breathe", "breathing", "throat",
    "stomach", "abdomen", "chest", "back pain", "joint", "muscle",
    "dizzy", "dizziness", "fainting", "weakness", "numbness", "tingling",
    "vision", "hearing", "skin", "eye", "ear", "nose",
    # Investigations
    "blood test", "scan", "xray", "x-ray", "mri", "ct scan", "ultrasound",
    "biopsy", "ecg", "ekg", "laboratory", "lab result", "report",
    "cholesterol", "glucose", "sugar", "hemoglobin", "haemoglobin",
    "creatinine", "platelet", "white blood", "red blood",
    # Diseases (common)
    "diabetes", "hypertension", "blood pressure", "cancer", "tumor",
    "thyroid", "asthma", "arthritis", "depression", "anxiety",
    "malaria", "dengue", "tuberculosis", "hepatitis", "hiv", "aids",
    "covid", "corona", "flu", "influenza", "pneumonia", "bronchitis",
    "kidney", "liver", "heart", "cardiac", "lungs", "bone",
    # Drugs / treatment
    "medicine", "medication", "drug", "tablet", "capsule", "injection",
    "antibiotic", "painkiller", "prescription", "dosage", "dose", "side effect",
    "treatment", "therapy", "surgery", "operation", "vaccine", "vaccination",
    "remedy", "cure", "supplement", "vitamin", "mineral",
    # Lifestyle/clinical
    "diet", "nutrition", "weight", "obesity", "bmi", "exercise",
    "pregnancy", "pregnant", "period", "menstrual", "ovulation",
    "baby", "infant", "pediatric", "elderly", "chronic", "acute",
    "consult", "doctor", "hospital", "clinic", "specialist",
})


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def detect_intent(query: str) -> IntentResult:
    """
    Classify a user query into one of four intents.

    Priority order: EMERGENCY > GREETING > MEDICAL > GENERAL

    Args:
        query: Raw user input string.

    Returns:
        IntentResult with .intent (QueryIntent), .label, and .matched_signals.
    """
    if not query or not query.strip():
        return IntentResult(
            intent=QueryIntent.GENERAL,
            label="General",
            matched_signals=[],
        )

    q = query.strip()

    # ── 1. EMERGENCY — check first, highest priority ────────────────────────
    emergency_hits = [p.pattern for p in _EMERGENCY_PATTERNS if p.search(q)]
    if emergency_hits:
        return IntentResult(
            intent=QueryIntent.EMERGENCY,
            label="Emergency",
            matched_signals=emergency_hits,
        )

    q_lower = q.lower()

    medical_hits = [sig for sig in _MEDICAL_SIGNALS if sig in q_lower]

    greeting_hits = [sig for sig in _GREETING_SIGNALS if sig in q_lower]
    if greeting_hits and len(q) < 60:
        return IntentResult(
            intent=QueryIntent.GREETING,
            label="Greeting",
            matched_signals=greeting_hits,
        )

    word_count = len(q.split())
    if not medical_hits and word_count <= 3:
        return IntentResult(
            intent=QueryIntent.GREETING,
            label="Greeting",
            matched_signals=["short_input_fallback"],
        )

    # ── 3. MEDICAL ───────────────────────────────────────────────────────────
    if medical_hits:
        return IntentResult(
            intent=QueryIntent.MEDICAL,
            label="Medical",
            matched_signals=medical_hits[:5],  # cap for logging
        )

    # ── 4. GENERAL (default) ────────────────────────────────────────────────
    return IntentResult(
        intent=QueryIntent.GENERAL,
        label="General",
        matched_signals=[],
    )


# ---------------------------------------------------------------------------
# Confidence → label mapping
# ---------------------------------------------------------------------------

def confidence_label(score: float) -> str:
    """
    Convert a numeric RAG confidence score (0–1) into a human-readable label.

    Thresholds:
      ≥ 0.75 → "High Confidence"
      ≥ 0.50 → "Moderate Confidence"
      < 0.50 → "Low Confidence"
    """
    if score >= 0.75:
        return "High Confidence"
    if score >= 0.50:
        return "Moderate Confidence"
    return "Low Confidence"


# ---------------------------------------------------------------------------
# Safety disclaimer
# ---------------------------------------------------------------------------

LOW_CONFIDENCE_DISCLAIMER = (
    "\n\n---\n"
    "> ⚠️ **Disclaimer:** This response may be uncertain due to limited "
    "medical evidence retrieved. Please consult a qualified healthcare "
    "professional before making any health decisions."
)

EMERGENCY_PREFIX = (
    "🚨 **This may be a medical emergency.**\n"
    "**Call 108 (India) or your local emergency number immediately.**\n\n"
    "---\n\n"
)
