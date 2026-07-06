import pytest

CLIENT_PAYLOAD = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@neviswealth.com",
    "description": "Wealth management client at NevisWealth.",
    "social_links": ["https://linkedin.com/in/johndoe", "https://instagram.com/johndoe"],
}


@pytest.mark.asyncio
async def test_create_client_success(client):
    resp = await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["first_name"] == "John"
    assert body["last_name"] == "Doe"
    assert body["email"] == "john.doe@neviswealth.com"
    assert body["description"] == "Wealth management client at NevisWealth."
    assert body["social_links"] == ["https://linkedin.com/in/johndoe", "https://instagram.com/johndoe"]
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_client_minimal(client):
    payload = {"first_name": "Jane", "last_name": "Smith", "email": "jane@example.com"}
    resp = await client.post("/v1/clients", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] is None
    assert body["social_links"] is None


@pytest.mark.asyncio
async def test_create_client_duplicate_email(client):
    await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    resp = await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "CLIENT_EMAIL_CONFLICT"
    assert "already exists" in detail["message"].lower()


@pytest.mark.asyncio
async def test_create_client_missing_fields(client):
    resp = await client.post("/v1/clients", json={"first_name": "x"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_client_invalid_email(client):
    resp = await client.post(
        "/v1/clients",
        json={"first_name": "x", "last_name": "y", "email": "not-an-email"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_client_not_found(client):
    resp = await client.get("/v1/clients/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["code"] == "CLIENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_client_success(client):
    create = await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    cid = create.json()["id"]
    resp = await client.get(f"/v1/clients/{cid}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "john.doe@neviswealth.com"


@pytest.mark.asyncio
async def test_list_clients(client):
    await client.post("/v1/clients", json=CLIENT_PAYLOAD)
    await client.post(
        "/v1/clients",
        json={"first_name": "Alice", "last_name": "Lee", "email": "alice@example.com"},
    )
    resp = await client.get("/v1/clients")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["items"]) == 2
    assert body["has_more"] is False
