import os
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ragsearch:ragsearch@localhost:5433/ragsearch")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OPENAI_MODEL", "gpt-4.1-nano")

from app.core.config import settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.services.embeddings import EmbeddingService  # noqa: E402
from app.services.llm import LLMService  # noqa: E402

TEST_DATABASE_URL = os.environ.get("DATABASE_URL", settings.database_url)

test_engine = create_async_engine(
    TEST_DATABASE_URL, pool_pre_ping=True, echo=False, poolclass=NullPool
)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


def _fake_embedding_service() -> MagicMock:
    import numpy as np

    svc = MagicMock(spec=EmbeddingService)
    svc.embed.return_value = np.zeros(1536, dtype=np.float32)
    svc.is_available = True
    svc.dim = 1536
    return svc


def _fake_llm_service() -> MagicMock:
    svc = MagicMock(spec=LLMService)
    svc.is_available = True
    svc.model_name = "gpt-4.1-nano"
    svc.summarize.return_value = "This is a mocked document summary."
    return svc


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_db() -> AsyncIterator[None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("ALTER TABLE clients DROP COLUMN IF EXISTS search_doc"))
        await conn.execute(
            text(
                """
                ALTER TABLE clients ADD COLUMN search_doc tsvector
                GENERATED ALWAYS AS (
                    setweight(to_tsvector('simple', coalesce(first_name, '')), 'A') ||
                    setweight(to_tsvector('simple', coalesce(last_name,  '')), 'A') ||
                    setweight(to_tsvector('simple', coalesce(regexp_replace(email, '[@.]', ' ', 'g'), '')), 'A') ||
                    setweight(to_tsvector('simple', coalesce(description, '')), 'C') ||
                    setweight(to_tsvector('simple', coalesce(regexp_replace(regexp_replace(regexp_replace(social_links::text, '[\[\]\"]', '', 'g'), ',', ' ', 'g'), '[:/.]', ' ', 'g'), '')), 'D')
                ) STORED
                """
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS clients_search_doc_gin "
                "ON clients USING gin (search_doc)"
            )
        )
        await conn.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_doc"))
        await conn.execute(
            text(
                """
                ALTER TABLE document_chunks ADD COLUMN search_doc tsvector
                GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, ''))) STORED
                """
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS document_chunks_search_doc_gin "
                "ON document_chunks USING gin (search_doc)"
            )
        )
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, clients CASCADE"
            )
        )
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    # Patch the service factories where they're *imported* (in the route modules),
    # not just where they're defined — `from app.services.llm import get_llm_service`
    # binds a local reference that won't see a patch on the source module.
    import app.api.v1.documents as doc_mod

    fake_emb = _fake_embedding_service()
    fake_llm = _fake_llm_service()

    original_get_emb = doc_mod.get_embedding_service
    doc_mod.get_embedding_service = lambda: fake_emb

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    doc_mod.get_embedding_service = original_get_emb
