"""Tests for cursor-based pagination on GET /v1/clients."""
import pytest

CLIENT_PAYLOAD = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@neviswealth.com",
}


@pytest.mark.asyncio
async def test_list_clients_first_page(client):
    """First page returns items, has_more, and next_cursor."""
    for i in range(5):
        await client.post("/v1/clients", json={
            "first_name": f"User{i}",
            "last_name": "Test",
            "email": f"user{i}@test.com",
        })
    resp = await client.get("/v1/clients", params={"limit": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    assert len(body["items"]) == 3
    assert body["has_more"] is True
    assert body["next_cursor"] is not None


@pytest.mark.asyncio
async def test_list_clients_second_page(client):
    """Second page uses cursor and returns remaining items."""
    for i in range(5):
        await client.post("/v1/clients", json={
            "first_name": f"User{i}",
            "last_name": "Test",
            "email": f"user{i}@test.com",
        })
    page1 = (await client.get("/v1/clients", params={"limit": 3})).json()
    assert page1["has_more"] is True

    page2 = (await client.get("/v1/clients", params={
        "limit": 3, "cursor": page1["next_cursor"]
    })).json()
    assert page2["count"] == 2
    assert page2["has_more"] is False
    assert page2["next_cursor"] is None

    # No overlap between pages
    page1_ids = {item["id"] for item in page1["items"]}
    page2_ids = {item["id"] for item in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)
    assert len(page1_ids | page2_ids) == 5


@pytest.mark.asyncio
async def test_list_clients_empty(client):
    """Empty DB returns empty page."""
    resp = await client.get("/v1/clients")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["has_more"] is False
    assert body["next_cursor"] is None
    assert body["count"] == 0


@pytest.mark.asyncio
async def test_list_clients_invalid_cursor(client):
    resp = await client.get("/v1/clients", params={"cursor": "not-a-valid-cursor"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_CURSOR"


@pytest.mark.asyncio
async def test_list_clients_page_size_enforcement(client):
    """limit=1 returns single-item pages."""
    for i in range(3):
        await client.post("/v1/clients", json={
            "first_name": f"U{i}", "last_name": "T", "email": f"u{i}@t.com",
        })
    resp = await client.get("/v1/clients", params={"limit": 1})
    body = resp.json()
    assert body["count"] == 1
    assert body["has_more"] is True


@pytest.mark.asyncio
async def test_list_clients_full_iteration(client):
    """Iterate all pages and collect all clients — should match total inserted."""
    total = 25
    for i in range(total):
        await client.post("/v1/clients", json={
            "first_name": f"Client{i}", "last_name": "Page", "email": f"cp{i}@t.com",
        })

    all_ids = set()
    cursor = None
    pages = 0
    while True:
        params = {"limit": 10}
        if cursor:
            params["cursor"] = cursor
        resp = await client.get("/v1/clients", params=params)
        body = resp.json()
        for item in body["items"]:
            all_ids.add(item["id"])
        pages += 1
        if not body["has_more"]:
            break
        cursor = body["next_cursor"]

    assert len(all_ids) == total
    assert pages == 3  # 10 + 10 + 5
