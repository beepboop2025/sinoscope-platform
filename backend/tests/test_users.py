import pytest


@pytest.mark.asyncio
async def test_sync_user_creates_new(client):
    resp = await client.post(
        "/api/users/sync",
        json={"email": "test@example.com", "display_name": "Test User"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_me(client):
    # Sync first to create user
    await client.post("/api/users/sync", json={"email": "test@example.com"})

    resp = await client.get("/api/users/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_update_preferences(client, seed_user):
    resp = await client.patch(
        "/api/users/preferences",
        json={"theme": "light", "refresh_interval": 60},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["theme"] == "light"
    assert data["refresh_interval"] == 60
