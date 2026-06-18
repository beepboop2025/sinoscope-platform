"""
DragonScope Enterprise - WebSocket Client Example
=================================================

Example client demonstrating how to connect to the WebSocket gateway,
authenticate, subscribe to channels, and handle messages.

Supports both binary (MessagePack) and JSON protocols.
"""

import asyncio
import json
import time
import uuid
from typing import Optional, Callable

import websockets
import msgpack

from protocol import (
    ProtocolHandler, MessageBuilder, JSONProtocolHandler,
    MessageType, ChannelType, SubscribeMessage
)


class DragonScopeClient:
    """
    WebSocket client for DragonScope Enterprise Gateway.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Binary (MessagePack) and JSON protocol support
    - Heartbeat/ping-pong handling
    - Channel subscription management
    """
    
    def __init__(
        self,
        uri: str = "ws://localhost:8000/ws",
        token: Optional[str] = None,
        use_binary: bool = True,
        auto_reconnect: bool = True,
        max_reconnect_delay: float = 30.0
    ):
        self.uri = uri
        self.token = token or f"demo_token_{uuid.uuid4().hex}"
        self.use_binary = use_binary
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_delay = max_reconnect_delay
        
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._authenticated = False
        self._reconnect_delay = 1.0
        self._should_stop = False
        
        self._protocol = ProtocolHandler()
        self._json_protocol = JSONProtocolHandler()
        self._message_builder = MessageBuilder(self._protocol)
        
        # Callbacks
        self._message_handlers: dict[MessageType, list[Callable]] = {}
        self._channel_handlers: dict[str, list[Callable]] = {}
        
        # Tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        # Stats
        self._messages_received = 0
        self._messages_sent = 0
        self._connection_start_time: Optional[float] = None
    
    # ========================
    # Connection Management
    # ========================
    
    async def connect(self):
        """Connect to the WebSocket server."""
        while not self._should_stop:
            try:
                logger.info(f"Connecting to {self.uri}...")
                
                self._ws = await websockets.connect(
                    self.uri,
                    ping_interval=None,  # We handle heartbeats manually
                    max_size=10 * 1024 * 1024,  # 10MB
                )
                
                self._connected = True
                self._connection_start_time = time.time()
                logger.info("Connected to server")
                
                # Authenticate
                await self._authenticate()
                
                # Start background tasks
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                self._receive_task = asyncio.create_task(self._receive_loop())
                
                # Reset reconnect delay
                self._reconnect_delay = 1.0
                
                # Wait for disconnect
                await self._receive_task
                
            except Exception as e:
                logger.error(f"Connection error: {e}")
            
            finally:
                self._connected = False
                self._authenticated = False
                
                # Cancel tasks
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                
                # Close websocket
                if self._ws:
                    await self._ws.close()
                
                if not self.auto_reconnect or self._should_stop:
                    break
                
                # Reconnect with backoff
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self.max_reconnect_delay
                )
    
    async def disconnect(self):
        """Disconnect from the server."""
        self._should_stop = True
        if self._ws:
            await self._ws.close()
    
    async def _authenticate(self):
        """Send authentication message."""
        auth_msg = self._message_builder.auth(self.token)
        await self._send_raw(auth_msg)
        logger.info("Authentication sent")
    
    # ========================
    # Message Handling
    # ========================
    
    async def _send_raw(self, data: bytes):
        """Send raw bytes to server."""
        if not self._ws:
            raise ConnectionError("Not connected")
        
        if self.use_binary:
            await self._ws.send(data)
        else:
            # Convert to JSON
            msg_type, payload = self._protocol.decode(data)
            json_data = self._json_protocol.encode(msg_type, payload)
            await self._ws.send(json_data)
        
        self._messages_sent += 1
    
    async def _receive_loop(self):
        """Main receive loop."""
        try:
            async for message in self._ws:
                self._messages_received += 1
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receive error: {e}")
    
    async def _handle_message(self, data):
        """Handle incoming message."""
        try:
            if isinstance(data, bytes):
                msg_type, payload = self._protocol.decode(data)
            else:
                msg_type, payload = self._json_protocol.decode(data)
            
            # Handle authentication response
            if msg_type == MessageType.AUTH:
                if isinstance(payload, dict) and payload.get('success'):
                    self._authenticated = True
                    logger.info(f"Authenticated as {payload.get('user_id')}")
                else:
                    logger.error("Authentication failed")
            
            # Handle heartbeat
            elif msg_type == MessageType.HEARTBEAT:
                # Heartbeat received, already tracked
                pass
            
            # Handle errors
            elif msg_type == MessageType.ERROR:
                logger.error(f"Server error: {payload}")
            
            # Handle data messages
            elif msg_type in (MessageType.SNAPSHOT, MessageType.UPDATE):
                channel = payload.channel if hasattr(payload, 'channel') else payload.get('channel')
                await self._dispatch_channel_message(channel, payload)
            
            # Dispatch to handlers
            await self._dispatch_message(msg_type, payload)
        
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _dispatch_message(self, msg_type: MessageType, payload):
        """Dispatch message to registered handlers."""
        handlers = self._message_handlers.get(msg_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(msg_type, payload)
                else:
                    handler(msg_type, payload)
            except Exception as e:
                logger.error(f"Handler error: {e}")
    
    async def _dispatch_channel_message(self, channel: str, payload):
        """Dispatch message to channel handlers."""
        handlers = self._channel_handlers.get(channel, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(channel, payload)
                else:
                    handler(channel, payload)
            except Exception as e:
                logger.error(f"Channel handler error: {e}")
    
    # ========================
    # Public API
    # ========================
    
    def on(self, msg_type: MessageType, handler: Callable):
        """Register a message type handler."""
        if msg_type not in self._message_handlers:
            self._message_handlers[msg_type] = []
        self._message_handlers[msg_type].append(handler)
    
    def on_channel(self, channel: str, handler: Callable):
        """Register a channel handler."""
        if channel not in self._channel_handlers:
            self._channel_handlers[channel] = []
        self._channel_handlers[channel].append(handler)
    
    async def subscribe(
        self,
        channel: str,
        channel_type: ChannelType = ChannelType.CUSTOM,
        params: Optional[dict] = None,
        snapshot: bool = True
    ):
        """Subscribe to a channel."""
        sub_msg = self._message_builder.subscribe(
            channel, channel_type, params, snapshot
        )
        await self._send_raw(sub_msg)
        logger.info(f"Subscribed to {channel}")
    
    async def unsubscribe(self, channel: str):
        """Unsubscribe from a channel."""
        unsub_msg = self._message_builder.unsubscribe(channel)
        await self._send_raw(unsub_msg)
        logger.info(f"Unsubscribed from {channel}")
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        seq = 0
        while self._connected:
            try:
                hb_msg = self._protocol.encode_heartbeat(seq=seq)
                await self._send_raw(hb_msg)
                seq += 1
                await asyncio.sleep(30)  # Send every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)
    
    @property
    def stats(self) -> dict:
        """Get client statistics."""
        return {
            'connected': self._connected,
            'authenticated': self._authenticated,
            'messages_sent': self._messages_sent,
            'messages_received': self._messages_received,
            'connection_duration': (
                time.time() - self._connection_start_time
                if self._connection_start_time else 0
            )
        }


# ========================
# Example Usage
# ========================

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Example client usage."""
    
    client = DragonScopeClient(
        uri="ws://localhost:8000/ws",
        use_binary=True,
        auto_reconnect=True
    )
    
    # Handle ticker updates
    def on_ticker(channel, payload):
        data = payload.data if hasattr(payload, 'data') else payload.get('data', {})
        print(f"\n📈 Ticker [{channel}]: ${data.get('price', 'N/A')}")
    
    # Handle orderbook updates
    def on_orderbook(channel, payload):
        data = payload.data if hasattr(payload, 'data') else payload.get('data', {})
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        print(f"\n📊 OrderBook [{channel}]: {len(bids)} bids, {len(asks)} asks")
    
    # Handle errors
    def on_error(msg_type, payload):
        print(f"\n❌ Error: {payload}")
    
    # Register handlers
    client.on_channel("ticker:BTC-USD", on_ticker)
    client.on_channel("orderbook:BTC-USD", on_orderbook)
    client.on(MessageType.ERROR, on_error)
    
    # Connect and subscribe (runs in background)
    connect_task = asyncio.create_task(client.connect())
    
    # Wait for connection and authentication
    await asyncio.sleep(1)
    
    if client._authenticated:
        # Subscribe to channels
        await client.subscribe("BTC-USD", ChannelType.TICKER)
        await client.subscribe("BTC-USD", ChannelType.ORDERBOOK)
        
        print("\n✅ Subscribed to channels. Press Ctrl+C to exit.\n")
        
        # Run for a while
        try:
            while True:
                await asyncio.sleep(1)
                stats = client.stats
                print(f"\r📊 Sent: {stats['messages_sent']} | "
                      f"Received: {stats['messages_received']} | "
                      f"Duration: {int(stats['connection_duration'])}s", end='')
        except KeyboardInterrupt:
            pass
    
    await client.disconnect()
    await connect_task


if __name__ == "__main__":
    asyncio.run(main())
