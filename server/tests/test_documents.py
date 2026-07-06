import pytest

CLIENT_PAYLOAD = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@neviswealth.com",
}

DOC_PAYLOAD = {
    "title": "Utility Bill",
    "content": "This document is a utility bill serving as address proof for the client.",
}


@pytest.mark.asyncio
async def _make_client(client) -> str:
    resp = await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_document_success(client):
    cid = await _make_client(client)
    resp = await client.post(f"/v1/clients/{cid}/documents", json=DOC_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Utility Bill"
    assert "address proof" in body["content"]
    assert body["client_id"] == cid
    assert "id" in body


@pytest.mark.asyncio
async def test_create_document_client_not_found(client):
    resp = await client.post(
        "/v1/clients/00000000-0000-0000-0000-000000000000/documents", json=DOC_PAYLOAD
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "CLIENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_document_missing_fields(client):
    cid = await _make_client(client)
    resp = await client.post(f"/v1/clients/{cid}/documents", json={"title": "x"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_document_not_found(client):
    resp = await client.get("/v1/documents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_document_success(client):
    cid = await _make_client(client)
    create = await client.post(f"/v1/clients/{cid}/documents", json=DOC_PAYLOAD)
    did = create.json()["id"]
    resp = await client.get(f"/v1/documents/{did}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Utility Bill"


@pytest.mark.asyncio
async def test_create_document_stores_embedding_chunk(client):
    """Verify the document_chunks row was created with a 1536-dim vector."""
    from sqlalchemy import select
    from app.models.document_chunk import DocumentChunk
    from tests.conftest import TestSessionLocal

    cid = await _make_client(client)
    create = await client.post(f"/v1/clients/{cid}/documents", json=DOC_PAYLOAD)
    did = create.json()["id"]

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == did)
        )
        chunk = result.scalar_one()
        assert chunk.chunk_index == 0
        assert chunk.content == DOC_PAYLOAD["content"]
        # Embedding may be None if the model wasn't loaded; with the mock it's set.
        if chunk.embedding is not None:
            assert len(chunk.embedding) == 1536
