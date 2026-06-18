import pytest


@pytest.mark.asyncio
async def test_list_watchlists_empty(client, seed_user):
    resp = await client.get("/api/watchlists")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_watchlist(client, seed_user):
    resp = await client.post("/api/watchlists", json={"name": "Tech Watchlist"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Tech Watchlist"
    assert "id" in data


@pytest.mark.asyncio
async def test_add_and_remove_item(client, seed_user):
    create = await client.post("/api/watchlists", json={"name": "Crypto"})
    wid = create.json()["id"]

    item = await client.post(
        f"/api/watchlists/{wid}/items",
        json={"symbol": "btc", "asset_type": "crypto"},
    )
    assert item.status_code == 201
    assert item.json()["symbol"] == "BTC"  # uppercased
    iid = item.json()["id"]

    resp = await client.delete(f"/api/watchlists/{wid}/items/{iid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_watchlist(client, seed_user):
    create = await client.post("/api/watchlists", json={"name": "Temp"})
    wid = create.json()["id"]

    resp = await client.delete(f"/api/watchlists/{wid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_watchlist_not_found(client, seed_user):
    resp = await client.delete("/api/watchlists/nonexistent")
    assert resp.status_code == 404
