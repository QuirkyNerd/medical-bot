from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import router as agent_router
from api.medical_query_router import router as medical_query_router
from api.auth_router import router as auth_router
from api.conversations_router import router as conversations_router
from api.schedule_router import router as schedule_router
from api.export_router import router as export_router
from api.health_router import router as health_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("medai.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Medical AI Backend")
    try:
        logger.info("Backend started")
    except Exception as exc:
        logger.exception("Startup failed")
        raise exc
    yield
    logger.info("Backend shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Medical AI Backend",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agent_router, prefix="/api/agent")
    app.include_router(medical_query_router, prefix="/api/medical-query")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(conversations_router, prefix="/api/conversations")
    app.include_router(schedule_router, prefix="/api/schedule")
    app.include_router(export_router, prefix="/api/export-report")
    app.include_router(health_router, prefix="/api/health")

    @app.get("/")
    async def root():
        return {"status": "ok"}

    @app.get("/health")
    async def health():
        return "ok"

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )