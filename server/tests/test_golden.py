"""Golden tests — full end-to-end flows with expected input/output pairs.

These tests exercise the complete API surface in sequence to verify the
behaviour specified in TASK.md and ARCHITECTURE.md.
"""

import pytest

# ---------------------------------------------------------------------------
# Golden flow 1: client creation → search by email substring (TASK.md example)
# ---------------------------------------------------------------------------

GOLDEN_CLIENT = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@neviswealth.com",
    "description": "Wealth management client at NevisWealth.",
    "social_links": ["https://linkedin.com/in/johndoe"],
}


@pytest.mark.asyncio
async def test_golden_client_search_by_email(client):
    """'NevisWealth' → client with john.doe@neviswealth.com (TASK.md example)."""
    resp = await client.post("/v1/clients", json=GOLDEN_CLIENT)
    assert resp.status_code == 201

    resp = await client.get("/v1/search?q=NevisWealth")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["type"] == "client"
    assert body[0]["score"] > 0
    assert body[0]["client"]["email"] == "john.doe@neviswealth.com"


# ---------------------------------------------------------------------------
# Golden flow 2: document creation with embedding → get
# ---------------------------------------------------------------------------

GOLDEN_DOC = {
    "title": "Address Proof",
    "content": "This utility bill confirms the client's residential address.",
}


@pytest.mark.asyncio
async def test_golden_document_flow(client):
    # 1. Create client
    cresp = await client.post("/v1/clients", json=GOLDEN_CLIENT)
    assert cresp.status_code == 201
    cid = cresp.json()["id"]

    # 2. Create document (embedding mocked)
    dresp = await client.post(f"/v1/clients/{cid}/documents", json=GOLDEN_DOC)
    assert dresp.status_code == 201
    did = dresp.json()["id"]
    assert dresp.json()["title"] == "Address Proof"

    # 3. Get document back
    gresp = await client.get(f"/v1/documents/{did}")
    assert gresp.status_code == 200
    assert gresp.json()["content"] == GOLDEN_DOC["content"]


# ---------------------------------------------------------------------------
# Golden flow 3: error coverage (404, 409, 422, 400)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_golden_error_coverage(client):
    # 404 — client not found
    resp = await client.get("/v1/clients/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "CLIENT_NOT_FOUND"

    # 409 — duplicate email
    await client.post("/v1/clients", json=GOLDEN_CLIENT)
    resp = await client.post("/v1/clients", json=GOLDEN_CLIENT)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "CLIENT_EMAIL_CONFLICT"

    # 422 — missing required fields
    resp = await client.post("/v1/clients", json={"first_name": "x"})
    assert resp.status_code == 422

    # 400 — empty search query
    resp = await client.get("/v1/search?q=")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "EMPTY_QUERY"

    # 404 — document not found
    resp = await client.get("/v1/documents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "DOCUMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Golden flow 4: search ranking — name/email (A) > description (C)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_golden_ranking_weights(client):
    # Client with "nevis" in name (weight A)
    await client.post(
        "/v1/clients",
        json={
            "first_name": "Nevis",
            "last_name": "Advisor",
            "email": "nevis-advisor@example.com",
            "description": "generic text without keywords",
        },
    )
    # Client with "nevis" in description only (weight C)
    await client.post(
        "/v1/clients",
        json={
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@example.com",
            "description": "works at nevis sometimes",
        },
    )
    resp = await client.get("/v1/search?q=nevis")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # Name match (A) should rank above description match (C)
    assert body[0]["client"]["first_name"] == "Nevis"
    assert body[0]["score"] >= body[1]["score"]
