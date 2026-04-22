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

from database import init_db, engine
from sqlalchemy import text


# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("medai.main")


# -------------------------------------------------------------------
# Lifespan (startup + shutdown)
# -------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Medical AI Backend")

    try:
        # ✅ Initialize DB
        init_db()
        logger.info("✅ Database initialized")

        # ✅ FIXED: SQLAlchemy 2.x requires text()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        logger.info("✅ Database connection successful")

    except Exception as exc:
        logger.exception("❌ Startup failed")
        raise exc

    yield

    logger.info("🛑 Backend shutdown complete")


# -------------------------------------------------------------------
# App factory
# -------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Medical AI Backend",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ✅ CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # restrict later in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----------------------------------------------------------------
    # Routers
    # ----------------------------------------------------------------
    app.include_router(agent_router, prefix="/api/agent")
    app.include_router(medical_query_router, prefix="/api/medical-query")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(conversations_router, prefix="/api/conversations")
    app.include_router(schedule_router, prefix="/api/schedule")
    app.include_router(export_router, prefix="/api/export-report")
    app.include_router(health_router, prefix="/api/health")

    # ----------------------------------------------------------------
    # Routes
    # ----------------------------------------------------------------

    @app.get("/")
    async def root():
        return {"status": "ok", "service": "medical-ai-backend"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/db-test")
    async def db_test():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "database connected"}
        except Exception as e:
            return {"status": "database error", "error": str(e)}

    # ----------------------------------------------------------------
    # Global error handler
    # ----------------------------------------------------------------

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    return app


# -------------------------------------------------------------------
# App instance
# -------------------------------------------------------------------

app = create_app()


# -------------------------------------------------------------------
# Local run
# -------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )