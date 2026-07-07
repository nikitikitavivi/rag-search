import hashlib
import os
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import httpx
import numpy as np
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
from app.services.embeddings import EmbeddingService, get_embedding_service  # noqa: E402
from app.services.llm import LLMService, get_llm_service  # noqa: E402

TEST_DATABASE_URL = os.environ.get("DATABASE_URL", settings.database_url)

test_engine = create_async_engine(
    TEST_DATABASE_URL, pool_pre_ping=True, echo=False, poolclass=NullPool
)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


def _deterministic_vector(text: str, dim: int = 1536) -> np.ndarray:
    """Return a deterministic non-zero vector seeded from text content.

    Cosine distance against a zero vector is undefined (pgvector returns NaN),
    so semantic search tests exercising zero-vector results are effectively
    untested.  Hash-seeded vectors give stable, assertable similarity orderings.
    """
    h = hashlib.sha256(text.encode()).digest()
    rng = np.random.Generator(np.random.PCG64(int.from_bytes(h[:8], "big")))
    vec = rng.normal(size=dim).astype(np.float32)
    vec /= np.linalg.norm(vec) + 1e-10
    return vec


def _fake_embedding_service() -> EmbeddingService:
    svc = MagicMock(spec=EmbeddingService)

    async def _embed(text: str) -> np.ndarray:
        return _deterministic_vector(text)

    async def _embed_batch(texts: list[str]) -> list[np.ndarray]:
        return [_deterministic_vector(t) for t in texts]

    svc.embed = _embed
    svc.embed_batch = _embed_batch
    svc.is_available = True
    svc.dim = 1536
    return svc


def _fake_llm_service() -> LLMService:
    svc = MagicMock(spec=LLMService)
    svc.is_available = True
    svc.model_name = "gpt-4.1-nano"

    async def _summarize(content: str) -> str:
        return f"Summary of: {content[:80]}"

    async def _document_context(title: str, content: str) -> str:
        return f"Document: {title}"

    async def _hypothetical_questions(chunk_text: str) -> list[str]:
        return [f"What is {chunk_text[:40]}?", f"Tell me about {chunk_text[:40]}"]

    async def _stream_chat(system: str, user: str, max_tokens: int = 500) -> AsyncIterator[str]:
        yield "This is a test response."
        yield ""

    svc.summarize = _summarize
    svc.document_context = _document_context
    svc.hypothetical_questions = _hypothetical_questions
    svc.stream_chat = _stream_chat
    return svc


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_db() -> AsyncIterator[None]:
    import subprocess
    import sys
    from pathlib import Path

    server_dir = str(Path(__file__).parent.parent.resolve())
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=server_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed ({result.returncode}):\n"
                           f"stdout:\n{result.stdout}\n"
                           f"stderr:\n{result.stderr}")

    yield
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
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

    fake_emb = _fake_embedding_service()
    fake_llm = _fake_llm_service()

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_embedding_service] = lambda: fake_emb
    app.dependency_overrides[get_llm_service] = lambda: fake_llm

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
