from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.models.client import Client
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.search import MIN_SCORE, SearchService


def _unavailable_emb():
    svc = MagicMock()
    svc.is_available = False
    svc.dim = 1536
    return svc


def _available_emb(query_vec=None):
    svc = MagicMock()
    svc.is_available = True
    svc.dim = 1536
    if query_vec is not None:
        svc.embed = AsyncMock(return_value=query_vec)
    else:
        svc.embed = AsyncMock(return_value=np.ones(1536, dtype=np.float32))
    return svc


@pytest.mark.asyncio
async def test_search_clients_empty_query(db_session):
    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_clients("")
    assert results == []


@pytest.mark.asyncio
async def test_search_clients_whitespace_query(db_session):
    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_clients("   ")
    assert results == []


@pytest.mark.asyncio
async def test_search_clients_finds_by_name(db_session):
    client = Client(first_name="Alice", last_name="Smith", email="alice@example.com")
    db_session.add(client)
    await db_session.commit()

    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_clients("Alice")
    assert len(results) >= 1
    assert results[0]["first_name"] == "Alice"


@pytest.mark.asyncio
async def test_search_clients_finds_by_email(db_session):
    client = Client(
        first_name="Bob", last_name="Jones", email="bob@neviswealth.com"
    )
    db_session.add(client)
    await db_session.commit()

    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_clients("neviswealth")
    assert len(results) >= 1
    assert results[0]["email"] == "bob@neviswealth.com"


@pytest.mark.asyncio
async def test_search_clients_no_match(db_session):
    client = Client(first_name="Carol", last_name="Davis", email="carol@example.com")
    db_session.add(client)
    await db_session.commit()

    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_clients("xyznonexistent98765")
    assert results == []


@pytest.mark.asyncio
async def test_search_clients_respects_limit(db_session):
    for i in range(5):
        client = Client(
            first_name="Test", last_name=f"User{i}", email=f"test{i}@example.com"
        )
        db_session.add(client)
    await db_session.commit()

    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_clients("Test", limit=3)
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_search_documents_rrf_empty_query(db_session):
    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_documents_rrf("")
    assert results == []


@pytest.mark.asyncio
async def test_search_documents_rrf_whitespace_query(db_session):
    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_documents_rrf("   ")
    assert results == []


@pytest.mark.asyncio
async def test_search_documents_rrf_bm25_fallback_when_vector_unavailable(db_session):
    client = Client(first_name="Dan", last_name="Evans", email="dan@example.com")
    db_session.add(client)
    await db_session.flush()

    doc = Document(client_id=client.id, title="Passport", content="A passport document.")
    db_session.add(doc)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content="A passport document.",
        search_text="Passport\nA passport document.",
    )
    db_session.add(chunk)
    await db_session.commit()

    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_documents_rrf("passport")

    assert len(results) >= 1
    assert results[0]["title"] == "Passport"


@pytest.mark.asyncio
async def test_search_documents_rrf_vector_search_populates_hits(db_session):
    client = Client(first_name="Eve", last_name="Fox", email="eve@example.com")
    db_session.add(client)
    await db_session.flush()

    doc = Document(client_id=client.id, title="Utility Bill", content="Electric bill.")
    db_session.add(doc)
    await db_session.flush()

    query_vec = np.array([0.1] * 1536, dtype=np.float32)
    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content="Electric bill.",
        search_text="Utility Bill\nElectric bill.",
        embedding=[float(v) for v in query_vec],
    )
    db_session.add(chunk)
    await db_session.commit()

    mock_emb = _available_emb(query_vec=query_vec)
    service = SearchService(db_session, mock_emb)
    results = await service.search_documents_rrf("utility bill")

    assert len(results) >= 1
    assert results[0]["title"] == "Utility Bill"


@pytest.mark.asyncio
async def test_search_documents_rrf_vector_failure_continues_with_bm25(db_session):
    client = Client(first_name="Fay", last_name="Grey", email="fay@example.com")
    db_session.add(client)
    await db_session.flush()

    doc = Document(client_id=client.id, title="Tax Return", content="Annual tax return.")
    db_session.add(doc)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content="Annual tax return.",
        search_text="Tax Return\nAnnual tax return.",
    )
    db_session.add(chunk)
    await db_session.commit()

    mock_emb = MagicMock()
    mock_emb.is_available = True
    mock_emb.embed = AsyncMock(side_effect=RuntimeError("API error"))

    service = SearchService(db_session, mock_emb)
    results = await service.search_documents_rrf("tax return")

    assert len(results) >= 1
    assert results[0]["title"] == "Tax Return"


@pytest.mark.asyncio
async def test_search_documents_rrf_no_results(db_session):
    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_documents_rrf("xyznonexistent98765")
    assert results == []


@pytest.mark.asyncio
async def test_search_documents_rrf_respects_limit(db_session):
    client = Client(first_name="Gus", last_name="Hill", email="gus@example.com")
    db_session.add(client)
    await db_session.flush()

    doc = Document(client_id=client.id, title="Invoice", content="Invoice document.")
    db_session.add(doc)
    await db_session.flush()

    for i in range(3):
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            content=f"Invoice chunk {i}.",
            search_text=f"Invoice\nInvoice chunk {i}.",
        )
        db_session.add(chunk)
    await db_session.commit()

    service = SearchService(db_session, _unavailable_emb())
    results = await service.search_documents_rrf("Invoice", limit=2)
    assert len(results) <= 2


@pytest.mark.asyncio
async def test_search_documents_rrf_filters_below_min_score(db_session):
    """Results with score below MIN_SCORE are excluded."""
    client = Client(first_name="Hal", last_name="Ives", email="hal@example.com")
    db_session.add(client)
    await db_session.flush()

    doc = Document(client_id=client.id, title="Receipt", content="Store receipt.")
    db_session.add(doc)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content="Store receipt.",
        search_text="Receipt\nStore receipt.",
    )
    db_session.add(chunk)
    await db_session.commit()

    mock_emb = _available_emb(query_vec=np.ones(1536, dtype=np.float32))
    service = SearchService(db_session, mock_emb)
    results = await service.search_documents_rrf("totallyunrelatedquery", limit=10)

    for r in results:
        assert r["score"] >= MIN_SCORE
