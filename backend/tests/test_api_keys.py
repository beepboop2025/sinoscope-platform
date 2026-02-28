import pytest


@pytest.mark.asyncio
async def test_list_api_keys_empty(client, seed_user):
    resp = await client.get("/api/api-keys")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_save_api_key(client, seed_user):
    resp = await client.post(
        "/api/api-keys",
        json={"provider": "alphavantage", "key": "my-secret-key", "label": "AV Key"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "alphavantage"
    assert data["label"] == "AV Key"
    # key_hash should not be the plain key
    assert "my-secret-key" not in data.get("key_hash", "")


@pytest.mark.asyncio
async def test_upsert_api_key(client, seed_user):
    await client.post(
        "/api/api-keys",
        json={"provider": "finnhub", "key": "key-v1"},
    )
    resp = await client.post(
        "/api/api-keys",
        json={"provider": "finnhub", "key": "key-v2", "label": "Updated"},
    )
    assert resp.status_code == 201
    assert resp.json()["label"] == "Updated"

    listing = await client.get("/api/api-keys")
    finnhub_keys = [k for k in listing.json() if k["provider"] == "finnhub"]
    assert len(finnhub_keys) == 1


@pytest.mark.asyncio
async def test_delete_api_key(client, seed_user):
    create = await client.post(
        "/api/api-keys",
        json={"provider": "fred", "key": "fred-key"},
    )
    kid = create.json()["id"]

    resp = await client.delete(f"/api/api-keys/{kid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_api_key_not_found(client, seed_user):
    resp = await client.delete("/api/api-keys/nonexistent")
    assert resp.status_code == 404
