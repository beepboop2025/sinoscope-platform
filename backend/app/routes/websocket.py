import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/market-data")
async def market_data_ws(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            categories = msg.get("categories", [])

            if msg_type == "subscribe" and isinstance(categories, list):
                ws_manager.subscribe(websocket, categories)
                await websocket.send_text(json.dumps({
                    "type": "subscribed",
                    "categories": categories,
                }))
            elif msg_type == "unsubscribe" and isinstance(categories, list):
                ws_manager.unsubscribe(websocket, categories)
                await websocket.send_text(json.dumps({
                    "type": "unsubscribed",
                    "categories": categories,
                }))

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
