import asyncio
import json
import logging
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manage WebSocket connections and broadcast market data updates."""

    def __init__(self):
        # {websocket: set_of_subscribed_categories}
        self._connections: dict[WebSocket, set[str]] = {}
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[websocket] = set()
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    def subscribe(self, websocket: WebSocket, categories: list[str]) -> None:
        if websocket in self._connections:
            self._connections[websocket].update(categories)

    def unsubscribe(self, websocket: WebSocket, categories: list[str]) -> None:
        if websocket in self._connections:
            self._connections[websocket].difference_update(categories)

    async def broadcast(self, category: str, data: dict) -> None:
        """Broadcast data to all clients subscribed to this category."""
        message = json.dumps({
            "type": "update",
            "category": category,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        disconnected = []
        for ws, subs in self._connections.items():
            if category in subs:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_heartbeat(self) -> None:
        """Send heartbeat to all connected clients."""
        message = json.dumps({"type": "heartbeat"})
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def start_heartbeat(self) -> None:
        """Start periodic heartbeat every 30 seconds."""
        async def _heartbeat_loop():
            while True:
                await asyncio.sleep(30)
                await self.send_heartbeat()

        self._heartbeat_task = asyncio.create_task(_heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Global singleton
ws_manager = WebSocketManager()
