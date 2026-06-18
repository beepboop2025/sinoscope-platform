import pytest


@pytest.mark.asyncio
async def test_list_alerts_empty(client, seed_user):
    resp = await client.get("/api/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_alert(client, seed_user):
    resp = await client.post(
        "/api/alerts",
        json={"symbol": "btc", "condition": "price_above", "threshold": 100000},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "BTC"
    assert data["condition"] == "price_above"
    assert data["threshold"] == 100000


@pytest.mark.asyncio
async def test_update_alert(client, seed_user):
    create = await client.post(
        "/api/alerts",
        json={"symbol": "ETH", "condition": "price_below", "threshold": 2000},
    )
    aid = create.json()["id"]

    resp = await client.patch(f"/api/alerts/{aid}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_alert(client, seed_user):
    create = await client.post(
        "/api/alerts",
        json={"symbol": "SOL", "condition": "pct_change_above", "threshold": 10},
    )
    aid = create.json()["id"]

    resp = await client.delete(f"/api/alerts/{aid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_alert_not_found(client, seed_user):
    resp = await client.patch("/api/alerts/nonexistent", json={"is_active": False})
    assert resp.status_code == 404
