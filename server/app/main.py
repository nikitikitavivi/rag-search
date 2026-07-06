import logging

from fastapi import FastAPI

from app.api.v1 import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Search API",
        version="1.0.0",
        description=(
            "WealthTech search API across clients and documents. "
            "v1: client full-text search, document CRUD + embedding, LLM summaries."
        ),
    )

    @app.get("/health", tags=["health"], summary="Health check")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()
