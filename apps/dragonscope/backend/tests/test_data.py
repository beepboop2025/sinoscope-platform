import json

import pytest

from tests.conftest import _redis_store


@pytest.mark.asyncio
async def test_get_data_from_redis(client):
    payload = json.dumps({"_updated": "2024-01-01", "data": [{"symbol": "BTC"}]})
    _redis_store["market:crypto"] = payload

    resp = await client.get("/api/data/crypto")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"][0]["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_get_data_invalid_category(client):
    resp = await client.get("/api/data/foo.bar")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_data_not_found(client):
    resp = await client.get("/api/data/nonexistent_category")
    assert resp.status_code == 404
