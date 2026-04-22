"""
Minimal router_agent test — zero third-party dependencies.
router_agent.py only imports stdlib (logging, re, dataclasses, enum).
"""
import sys
sys.path.insert(0, ".")

# router_agent.py has ONLY stdlib imports — safe to import directly
from agents.router_agent import QueryIntent, classify_query, to_canonical, RouterAgent

print("=" * 55)
print("ROUTER AGENT SMOKE TESTS")
print("=" * 55)

tests_passed = 0
tests_failed = 0

def check(label, condition, details=""):
    global tests_passed, tests_failed
    if condition:
        print(f"[PASS] {label}" + (f" | {details}" if details else ""))
        tests_passed += 1
    else:
        print(f"[FAIL] {label}" + (f" | {details}" if details else ""))
        tests_failed += 1

# --- New canonical intents exist ---
check("MEDICAL_QUESTION enum value",  QueryIntent.MEDICAL_QUESTION == "medical_question")
check("REPORT_ANALYSIS enum value",   QueryIntent.REPORT_ANALYSIS  == "report_analysis")
check("IMAGE_DIAGNOSIS enum value",   QueryIntent.IMAGE_DIAGNOSIS  == "image_diagnosis")

# --- Legacy intents still exist ---
check("GENERAL_KNOWLEDGE still present", hasattr(QueryIntent, "GENERAL_KNOWLEDGE"))
check("PATIENT_REPORT still present",    hasattr(QueryIntent, "PATIENT_REPORT"))
check("FOUNDATIONAL still present",      hasattr(QueryIntent, "FOUNDATIONAL"))
check("RESEARCH still present",          hasattr(QueryIntent, "RESEARCH"))

# --- Routing: has_report ---
r = classify_query("What does my blood test show?", has_report=True)
check("has_report=True → REPORT_ANALYSIS", r.intent == QueryIntent.REPORT_ANALYSIS,
      f"intent={r.intent.value} conf={r.confidence:.2f}")

# --- Routing: has_image ---
r2 = classify_query("Please analyze this", has_image=True)
check("has_image=True → IMAGE_DIAGNOSIS", r2.intent == QueryIntent.IMAGE_DIAGNOSIS,
      f"intent={r2.intent.value} conf={r2.confidence:.2f}")

# --- Routing: text + foundational signals ---
r3 = classify_query("What are the symptoms of diabetes?")
check("foundational text → MEDICAL_QUESTION", r3.intent == QueryIntent.MEDICAL_QUESTION,
      f"intent={r3.intent.value} conf={r3.confidence:.2f}")

# --- Routing: default ---
r4 = classify_query("Tell me about health")
check("generic text → MEDICAL_QUESTION", r4.intent == QueryIntent.MEDICAL_QUESTION,
      f"intent={r4.intent.value} conf={r4.confidence:.2f}")

# --- Routing: text image signals without actual image ---
r5 = classify_query("Can you read this ct scan result?")
check("'ct scan' text → IMAGE_DIAGNOSIS or MEDICAL", 
      r5.intent in (QueryIntent.IMAGE_DIAGNOSIS, QueryIntent.MEDICAL_QUESTION),
      f"intent={r5.intent.value}")

# --- Routing: patient signals without report ---
r6 = classify_query("my blood test shows high sugar")
check("patient signal text → REPORT_ANALYSIS or MEDICAL",
      r6.intent in (QueryIntent.REPORT_ANALYSIS, QueryIntent.MEDICAL_QUESTION),
      f"intent={r6.intent.value}")

# --- to_canonical mapping ---
check("GENERAL_KNOWLEDGE → MEDICAL_QUESTION", to_canonical(QueryIntent.GENERAL_KNOWLEDGE) == QueryIntent.MEDICAL_QUESTION)
check("FOUNDATIONAL → MEDICAL_QUESTION",      to_canonical(QueryIntent.FOUNDATIONAL)      == QueryIntent.MEDICAL_QUESTION)
check("RESEARCH → MEDICAL_QUESTION",          to_canonical(QueryIntent.RESEARCH)          == QueryIntent.MEDICAL_QUESTION)
check("PATIENT_REPORT → REPORT_ANALYSIS",     to_canonical(QueryIntent.PATIENT_REPORT)    == QueryIntent.REPORT_ANALYSIS)
check("HYBRID → IMAGE_DIAGNOSIS",             to_canonical(QueryIntent.HYBRID)            == QueryIntent.IMAGE_DIAGNOSIS)
check("MEDICAL_QUESTION → MEDICAL_QUESTION",  to_canonical(QueryIntent.MEDICAL_QUESTION)  == QueryIntent.MEDICAL_QUESTION)
check("REPORT_ANALYSIS → REPORT_ANALYSIS",    to_canonical(QueryIntent.REPORT_ANALYSIS)   == QueryIntent.REPORT_ANALYSIS)
check("IMAGE_DIAGNOSIS → IMAGE_DIAGNOSIS",    to_canonical(QueryIntent.IMAGE_DIAGNOSIS)   == QueryIntent.IMAGE_DIAGNOSIS)

print("\n" + "=" * 55)
print(f"Results: {tests_passed} passed, {tests_failed} failed")
if tests_failed == 0:
    print("ALL ROUTER TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
