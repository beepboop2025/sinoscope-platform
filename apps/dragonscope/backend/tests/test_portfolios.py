import pytest


@pytest.mark.asyncio
async def test_list_portfolios_empty(client, seed_user):
    resp = await client.get("/api/portfolios")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_portfolio(client, seed_user):
    resp = await client.post("/api/portfolios", json={"name": "My Portfolio", "description": "Test"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Portfolio"
    assert "id" in data


@pytest.mark.asyncio
async def test_update_portfolio(client, seed_user):
    create = await client.post("/api/portfolios", json={"name": "Old"})
    pid = create.json()["id"]

    resp = await client.patch(f"/api/portfolios/{pid}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


@pytest.mark.asyncio
async def test_delete_portfolio(client, seed_user):
    create = await client.post("/api/portfolios", json={"name": "Temp"})
    pid = create.json()["id"]

    resp = await client.delete(f"/api/portfolios/{pid}")
    assert resp.status_code == 204

    resp = await client.get("/api/portfolios")
    assert all(p["id"] != pid for p in resp.json())


@pytest.mark.asyncio
async def test_add_and_remove_holding(client, seed_user):
    create = await client.post("/api/portfolios", json={"name": "Stocks"})
    pid = create.json()["id"]

    holding = await client.post(
        f"/api/portfolios/{pid}/holdings",
        json={"symbol": "AAPL", "asset_type": "stock", "quantity": 10, "avg_cost": 150.0},
    )
    assert holding.status_code == 201
    hid = holding.json()["id"]

    resp = await client.delete(f"/api/portfolios/{pid}/holdings/{hid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_portfolio_not_found(client, seed_user):
    resp = await client.patch("/api/portfolios/nonexistent", json={"name": "X"})
    assert resp.status_code == 404
