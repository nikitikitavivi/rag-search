import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.db import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Search API",
        version="1.0.0",
        description=(
            "WealthTech search API across clients and documents. "
            "v1: client full-text search, document CRUD + embedding."
        ),
    )

    @app.get("/health", tags=["health"], summary="Health check")
    async def health() -> dict[str, str]:
        try:
            async with SessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            logger.exception("Health check: database unavailable")
            return {"status": "degraded", "database": "unavailable"}
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()
