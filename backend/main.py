"""
backend/main.py
================
FastAPI application entry point for the Advanced Multi-Agent Medical AI System.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Ensure backend root is importable (Removed manual hack)
# ---------------------------------------------------------------------------
# Python will now correctly resolve paths using PYTHONPATH=/app from Docker.

# ---------------------------------------------------------------------------
# Local imports (DO NOT execute heavy logic here)
# ---------------------------------------------------------------------------
from core.embedder import get_embedder          # noqa: E402
from core.vectorstore import get_vectorstore    # noqa: E402
from api.routes import router as agent_router                              # noqa: E402
from api.medical_query_router import router as medical_query_router       # noqa: E402
from api.auth_router import router as auth_router                         # noqa: E402
from api.conversations_router import router as conversations_router       # noqa: E402
from api.schedule_router import router as schedule_router                 # noqa: E402
from api.export_router import router as export_router                     # noqa: E402
from api.health_router import router as health_router                     # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("medai.main")

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Multi-Agent Medical AI Backend")

    try:
        # 1. Load embedding model
        logger.info("📦 Loading embedding model …")
        embedder = get_embedder()
        logger.info("✅ Embedding model ready (dim=%d)", embedder.dim)

        # 2. Initialize vector store
        logger.info("🗄️ Initialising Qdrant vector store …")
        vectorstore = get_vectorstore()
        info = vectorstore.status()
        logger.info("✅ Qdrant ready — collections: %s", list(info.keys()))

        logger.info("🎯 Backend startup complete")

    except Exception as exc:
        # 🔥 CRITICAL: log and re-raise so Docker shows real reason
        logger.exception("❌ Startup failed — backend will not start")
        raise exc

    yield

    logger.info("🛑 Backend shutdown complete")

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Advanced Multi-Agent Medical AI System",
        description=(
            "Production-grade multi-agent backend integrating RAG (Qdrant), "
            "LLM reasoning, and medical decision support."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # CORS
    # -----------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    app.include_router(
        agent_router,
        prefix="/api/agent",
        tags=["Agent Pipeline"],
    )

    app.include_router(
        medical_query_router,
        prefix="/api/medical-query",
        tags=["Unified Medical Query"],
    )

    app.include_router(
        auth_router,
        prefix="/api/auth",
        tags=["Authentication"],
    )

    app.include_router(
        conversations_router,
        prefix="/api/conversations",
        tags=["Chat History"],
    )

    app.include_router(
        schedule_router,
        prefix="/api/schedule",
        tags=["Medication Schedule"],
    )

    app.include_router(
        export_router,
        prefix="/api/export-report",
        tags=["Export"],
    )

    app.include_router(
        health_router,
        prefix="/api/health",
        tags=["Health Data"],
    )

    # -----------------------------------------------------------------------
    # Health check
    # -----------------------------------------------------------------------
    @app.get("/", summary="Root status check")
    async def root():
        return {
            "status": "ok",
            "service": "Multi-Agent Medical AI Backend",
            "version": "1.0.0",
        }

    @app.get("/health", summary="Simple health check")
    async def health():
        return "ok"

    # -----------------------------------------------------------------------
    # Global exception handler
    # -----------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", request.url)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "detail": str(exc),
                "path": str(request.url),
            },
        )

    return app


# ---------------------------------------------------------------------------
# App instance (used by Uvicorn in Docker)
# ---------------------------------------------------------------------------
app = create_app()