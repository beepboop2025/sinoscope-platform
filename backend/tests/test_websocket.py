import json

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_websocket_subscribe(client):
    """Test WebSocket connect + subscribe via the starlette test client."""
    from app.main import app

    from starlette.testclient import TestClient

    # WebSocket tests need the sync TestClient
    with TestClient(app) as sync_client:
        with sync_client.websocket_connect("/ws/market-data") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "categories": ["crypto", "forex"]}))
            resp = ws.receive_text()
            data = json.loads(resp)
            assert data["type"] == "subscribed"
            assert "crypto" in data["categories"]
            assert "forex" in data["categories"]


@pytest.mark.asyncio
async def test_websocket_unsubscribe(client):
    from app.main import app
    from starlette.testclient import TestClient

    with TestClient(app) as sync_client:
        with sync_client.websocket_connect("/ws/market-data") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "categories": ["news"]}))
            ws.receive_text()  # subscribed ack

            ws.send_text(json.dumps({"type": "unsubscribe", "categories": ["news"]}))
            resp = ws.receive_text()
            data = json.loads(resp)
            assert data["type"] == "unsubscribed"
