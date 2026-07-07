import pytest

CLIENT_PAYLOAD = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@neviswealth.com",
    "description": "Wealth management client at NevisWealth.",
}

SECOND_CLIENT = {
    "first_name": "Alice",
    "last_name": "Lee",
    "email": "alice@otherfirm.com",
    "description": "Tax planning specialist.",
}


@pytest.mark.asyncio
async def test_search_empty_query(client):
    resp = await client.get("/v1/search?q=")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "EMPTY_QUERY"


@pytest.mark.asyncio
async def test_search_no_results(client):
    resp = await client.get("/v1/search?q=nonexistentxyz")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_by_email_substring(client):
    """Golden case from TASK.md: 'NevisWealth' → client with john.doe@neviswealth.com."""
    await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    resp = await client.get("/v1/search?q=neviswealth")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    hit = body[0]
    assert hit["type"] == "client"
    assert hit["score"] > 0
    assert "neviswealth" in hit["client"]["email"].lower()
    assert hit["client"]["first_name"] == "John"


@pytest.mark.asyncio
async def test_search_by_name(client):
    await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    resp = await client.get("/v1/search?q=john")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["client"]["first_name"] == "John"


@pytest.mark.asyncio
async def test_search_by_description(client):
    await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    resp = await client.get("/v1/search?q=wealth+management")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "wealth" in body[0]["client"]["description"].lower()


@pytest.mark.asyncio
async def test_search_ranking_name_over_description(client):
    """Name (weight A) should rank higher than description (weight C)."""
    # Client A: match in name only
    await client.post(
        "/v1/clients",
        json={
            "first_name": "Wealth",
            "last_name": "Manager",
            "email": "a@example.com",
            "description": "unrelated text",
        },
    )
    # Client B: match in description only
    await client.post(
        "/v1/clients",
        json={
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "b@example.com",
            "description": "wealth management client",
        },
    )
    resp = await client.get("/v1/search?q=wealth")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # The name match (A weight) should rank first
    assert body[0]["client"]["first_name"] == "Wealth"
    assert body[1]["client"]["first_name"] == "Bob"


@pytest.mark.asyncio
async def test_search_multiple_clients(client):
    await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    await client.post("/v1/clients", json=SECOND_CLIENT)
    resp = await client.get("/v1/search?q=john")
    assert resp.status_code == 200
    body = resp.json()
    # Only John should match
    assert len(body) == 1
    assert body[0]["client"]["first_name"] == "John"


@pytest.mark.asyncio
async def test_search_limit(client):
    for i in range(5):
        await client.post(
            "/v1/clients",
            json={
                "first_name": "John",
                "last_name": f"Tester{i}",
                "email": f"john{i}@example.com",
            },
        )
    resp = await client.get("/v1/search?q=john&limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_search_phrase_query(client):
    """websearch_to_tsquery supports quoted phrases."""
    await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    resp = await client.get('/v1/search?q="john doe"')
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1


@pytest.mark.asyncio
async def test_search_documents_by_text(client):
    """FTS on document chunks returns matching documents."""
    resp = await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    cid = resp.json()["id"]
    await client.post(
        f"/v1/clients/{cid}/documents",
        json={
            "title": "Residential Statement",
            "content": "Monthly electricity and water service confirmation.",
        },
    )
    resp = await client.get("/v1/search?q=electricity&type=documents")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    assert body[0]["type"] == "document"
    assert body[0]["document"]["title"] == "Residential Statement"
