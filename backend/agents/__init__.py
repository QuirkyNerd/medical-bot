# backend/agents/__init__.py
# Agent package — minimal init, agents are imported lazily on demand.
# This prevents sentence_transformers / torch from being loaded at import time.
