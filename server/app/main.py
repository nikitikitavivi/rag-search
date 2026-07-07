import contextlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.db import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    server_dir = Path(__file__).resolve().parent.parent
    alembic_ini = server_dir / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic.ini not found at %s, skipping migrations", alembic_ini)
        return

    from alembic import command
    from alembic.config import Config as AlembicConfig
    from app.core.config import settings

    alembic_cfg = AlembicConfig(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(server_dir / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    logger.info("Running alembic migrations...")
    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations complete.")


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    if os.environ.get("VERCEL"):
        import asyncio

        await asyncio.to_thread(_run_migrations)
        from app.fixtures import run_fixtures

        await run_fixtures()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Search API",
        version="1.0.0",
        description=(
            "WealthTech search API across clients and documents. "
            "v1: client full-text search, document CRUD + embedding."
        ),
        lifespan=_lifespan,
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
