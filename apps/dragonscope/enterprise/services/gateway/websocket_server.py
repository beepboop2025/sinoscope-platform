"""
DragonScope Enterprise - WebSocket Gateway Server
=================================================
High-performance WebSocket server supporting 100k+ concurrent connections
with channel-based pub/sub, authentication, heartbeat handling, and
message batching.

Features:
- FastAPI + native websockets for high performance
- Connection pooling and management
- Channel-based pub/sub (tickers, orderbooks, portfolios)
- Authentication over WebSocket
- Heartbeat/ping-pong handling
- Message batching for efficiency
- Automatic reconnection support
- Comprehensive metrics and monitoring
"""

import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, Set, List, Callable, Any
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import websockets
from starlette.middleware.cors import CORSMiddleware

# Import local modules
from protocol import (
    ProtocolHandler, MessageBuilder, JSONProtocolHandler,
    MessageType, ChannelType, ErrorCode,
    SubscribeMessage, UnsubscribeMessage, AuthMessage, HeartbeatMessage
)
from pubsub import RedisPubSub, LocalPubSub


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class GatewayConfig:
    """Gateway configuration."""
    # Connection limits
    MAX_CONNECTIONS = 100000
    CONNECTIONS_PER_IP = 100
    
    # Timeouts
    CONNECTION_TIMEOUT = 60.0  # seconds
    HEARTBEAT_INTERVAL = 30.0  # seconds
    HEARTBEAT_TIMEOUT = 60.0   # seconds
    AUTH_TIMEOUT = 10.0        # seconds
    
    # Message limits
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    MESSAGES_PER_SECOND = 100
    BATCH_SIZE = 100
    BATCH_INTERVAL_MS = 10
    
    # Features
    ENABLE_COMPRESSION = True
    ENABLE_METRICS = True
    REQUIRE_AUTH = True
    
    # Redis
    REDIS_URL = "redis://localhost:6379"
    USE_REDIS = True


# ============================================================================
# Connection State Management
# ============================================================================

class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class ConnectionMetrics:
    """Per-connection metrics."""
    connected_at: float = field(default_factory=time.time)
    messages_received: int = 0
    messages_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    last_heartbeat_at: float = field(default_factory=time.time)
    last_message_at: float = field(default_factory=time.time)
    heartbeats_sent: int = 0
    heartbeats_received: int = 0
    errors: int = 0
    subscriptions: Set[str] = field(default_factory=set)


@dataclass
class Connection:
    """WebSocket connection wrapper."""
    id: str
    websocket: WebSocket
    state: ConnectionState = ConnectionState.CONNECTING
    remote_addr: str = ""
    user_id: Optional[str] = None
    api_key: Optional[str] = None
    authenticated_at: Optional[float] = None
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    
    # Protocol handling
    use_binary: bool = True
    protocol_handler: ProtocolHandler = field(default_factory=ProtocolHandler)
    json_handler: JSONProtocolHandler = field(default_factory=JSONProtocolHandler)
    message_builder: MessageBuilder = field(default_factory=MessageBuilder)
    
    # Batching
    _outgoing_buffer: List[bytes] = field(default_factory=list)
    _batch_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _batch_task: Optional[asyncio.Task] = None
    
    async def send(self, message: bytes, is_binary: bool = True):
        """Send a message to the client."""
        try:
            if is_binary and self.use_binary:
                await self.websocket.send_bytes(message)
            else:
                # Convert to JSON for text clients
                msg_type, payload = self.protocol_handler.decode(message)
                json_msg = self.json_handler.encode(msg_type, payload)
                await self.websocket.send_text(json_msg)
            
            self.metrics.messages_sent += 1
            self.metrics.bytes_sent += len(message)
        except Exception as e:
            logger.error(f"Failed to send message to {self.id}: {e}")
            raise
    
    async def send_batch(self, messages: List[bytes]):
        """Send multiple messages efficiently."""
        if not messages:
            return
        
        if len(messages) == 1:
            await self.send(messages[0])
            return
        
        # For binary protocol, use batch message type
        if self.use_binary:
            batch_msg = self.protocol_handler.encode_batch(messages)
            await self.send(batch_msg)
        else:
            # Send individually for JSON
            for msg in messages:
                await self.send(msg, is_binary=False)
    
    async def send_error(
        self,
        code: ErrorCode,
        message: str,
        channel: Optional[str] = None
    ):
        """Send an error message."""
        error_msg = self.protocol_handler.encode_error(code, message, channel)
        await self.send(error_msg)
    
    async def queue_message(self, message: bytes):
        """Queue a message for batch sending."""
        async with self._batch_lock:
            self._outgoing_buffer.append(message)
    
    async def flush_messages(self):
        """Flush queued messages."""
        async with self._batch_lock:
            if self._outgoing_buffer:
                messages = self._outgoing_buffer[:]
                self._outgoing_buffer.clear()
                await self.send_batch(messages)
    
    async def start_batching(self):
        """Start background batching task."""
        async def batch_loop():
            while self.state == ConnectionState.OPEN:
                await asyncio.sleep(GatewayConfig.BATCH_INTERVAL_MS / 1000)
                await self.flush_messages()
        
        self._batch_task = asyncio.create_task(batch_loop())
    
    async def stop_batching(self):
        """Stop batching and flush remaining messages."""
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        await self.flush_messages()
    
    def record_heartbeat(self, received: bool = False):
        """Record heartbeat activity."""
        self.metrics.last_heartbeat_at = time.time()
        if received:
            self.metrics.heartbeats_received += 1
        else:
            self.metrics.heartbeats_sent += 1
    
    def is_heartbeat_overdue(self) -> bool:
        """Check if heartbeat is overdue."""
        return (
            time.time() - self.metrics.last_heartbeat_at > GatewayConfig.HEARTBEAT_TIMEOUT
        )


# ============================================================================
# Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections with support for 100k+ concurrent clients."""
    
    def __init__(self):
        # Connection ID -> Connection
        self._connections: Dict[str, Connection] = {}
        # User ID -> Set of connection IDs
        self._user_connections: Dict[str, Set[str]] = {}
        # IP address -> Set of connection IDs (for rate limiting)
        self._ip_connections: Dict[str, Set[str]] = {}
        
        # Global metrics
        self._total_connections = 0
        self._peak_connections = 0
        self._total_messages_received = 0
        self._total_messages_sent = 0
        
        self._lock = asyncio.RLock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the connection manager."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Connection manager started")
    
    async def stop(self):
        """Stop the connection manager and close all connections."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Close all connections
        close_tasks = [
            self.disconnect(conn_id, "Server shutting down")
            for conn_id in list(self._connections.keys())
        ]
        await asyncio.gather(*close_tasks, return_exceptions=True)
        
        logger.info("Connection manager stopped")
    
    async def connect(
        self,
        websocket: WebSocket,
        remote_addr: str
    ) -> Optional[Connection]:
        """
        Accept a new WebSocket connection.
        
        Returns the Connection object or None if connection limit reached.
        """
        async with self._lock:
            # Check global connection limit
            if len(self._connections) >= GatewayConfig.MAX_CONNECTIONS:
                logger.warning("Max connections reached, rejecting connection")
                return None
            
            # Check per-IP limit
            ip_count = len(self._ip_connections.get(remote_addr, set()))
            if ip_count >= GatewayConfig.CONNECTIONS_PER_IP:
                logger.warning(f"Max connections per IP reached for {remote_addr}")
                return None
        
        # Accept the connection
        await websocket.accept()
        
        # Create connection object
        conn = Connection(
            id=str(uuid.uuid4()),
            websocket=websocket,
            state=ConnectionState.CONNECTING,
            remote_addr=remote_addr
        )
        
        async with self._lock:
            self._connections[conn.id] = conn
            self._ip_connections.setdefault(remote_addr, set()).add(conn.id)
            self._total_connections += 1
            self._peak_connections = max(self._peak_connections, len(self._connections))
        
        logger.info(f"New connection: {conn.id} from {remote_addr}")
        return conn
    
    async def authenticate(
        self,
        conn_id: str,
        user_id: str,
        api_key: Optional[str] = None
    ) -> bool:
        """Mark a connection as authenticated."""
        async with self._lock:
            conn = self._connections.get(conn_id)
            if not conn:
                return False
            
            conn.state = ConnectionState.OPEN
            conn.user_id = user_id
            conn.api_key = api_key
            conn.authenticated_at = time.time()
            
            self._user_connections.setdefault(user_id, set()).add(conn_id)
            
            # Start batching for this connection
            await conn.start_batching()
        
        logger.info(f"Connection {conn_id} authenticated as user {user_id}")
        return True
    
    async def disconnect(self, conn_id: str, reason: str = "Unknown"):
        """Disconnect a client."""
        async with self._lock:
            conn = self._connections.pop(conn_id, None)
            if not conn:
                return
            
            conn.state = ConnectionState.CLOSING
            
            # Remove from user connections
            if conn.user_id:
                self._user_connections.get(conn.user_id, set()).discard(conn_id)
            
            # Remove from IP connections
            self._ip_connections.get(conn.remote_addr, set()).discard(conn_id)
        
        try:
            # Stop batching
            await conn.stop_batching()
            
            # Close WebSocket
            await conn.websocket.close()
        except Exception as e:
            logger.debug(f"Error closing connection {conn_id}: {e}")
        
        conn.state = ConnectionState.CLOSED
        logger.info(f"Connection {conn_id} disconnected: {reason}")
    
    def get_connection(self, conn_id: str) -> Optional[Connection]:
        """Get a connection by ID."""
        return self._connections.get(conn_id)
    
    def get_user_connections(self, user_id: str) -> List[Connection]:
        """Get all connections for a user."""
        conn_ids = self._user_connections.get(user_id, set())
        return [self._connections[cid] for cid in conn_ids if cid in self._connections]
    
    def get_all_connections(self) -> List[Connection]:
        """Get all active connections."""
        return list(self._connections.values())
    
    def update_metrics(self, conn_id: str, received: bool = False, bytes_count: int = 0):
        """Update global metrics."""
        if received:
            self._total_messages_received += 1
        else:
            self._total_messages_sent += 1
    
    async def _cleanup_loop(self):
        """Periodic cleanup of dead connections."""
        while True:
            await asyncio.sleep(30)
            
            now = time.time()
            stale_connections = []
            
            for conn in self.get_all_connections():
                # Check heartbeat timeout
                if conn.is_heartbeat_overdue():
                    stale_connections.append((conn.id, "Heartbeat timeout"))
                # Check connection timeout
                elif now - conn.metrics.connected_at > GatewayConfig.CONNECTION_TIMEOUT:
                    if conn.state != ConnectionState.OPEN:
                        stale_connections.append((conn.id, "Auth timeout"))
            
            for conn_id, reason in stale_connections:
                await self.disconnect(conn_id, reason)
    
    @property
    def metrics(self) -> dict:
        """Get connection metrics."""
        return {
            'active_connections': len(self._connections),
            'total_connections': self._total_connections,
            'peak_connections': self._peak_connections,
            'authenticated_users': len(self._user_connections),
            'total_messages_received': self._total_messages_received,
            'total_messages_sent': self._total_messages_sent,
        }


# ============================================================================
# Authentication
# ============================================================================

class Authenticator:
    """Handles WebSocket authentication."""
    
    def __init__(self, require_auth: bool = True):
        self.require_auth = require_auth
        # Simple in-memory token storage (replace with proper JWT/auth service)
        self._valid_tokens: Dict[str, str] = {}  # token -> user_id
        self._rate_limits: Dict[str, List[float]] = {}  # token -> timestamps
    
    def add_token(self, token: str, user_id: str):
        """Add a valid token (for testing/demo)."""
        self._valid_tokens[token] = user_id
    
    async def authenticate(self, auth_msg: AuthMessage) -> tuple[bool, Optional[str]]:
        """
        Authenticate a client.
        
        Returns (success, user_id).
        """
        if not self.require_auth:
            return True, f"anon_{uuid.uuid4().hex[:8]}"
        
        # Check token
        user_id = self._valid_tokens.get(auth_msg.token)
        if not user_id:
            # Demo: accept any token that looks valid
            if len(auth_msg.token) >= 20:
                user_id = f"user_{auth_msg.token[:16]}"
                self._valid_tokens[auth_msg.token] = user_id
            else:
                return False, None
        
        # Check rate limit
        now = time.time()
        timestamps = self._rate_limits.get(auth_msg.token, [])
        timestamps = [t for t in timestamps if now - t < 60]  # Keep last minute
        
        if len(timestamps) > 10:  # Max 10 auth attempts per minute
            return False, None
        
        timestamps.append(now)
        self._rate_limits[auth_msg.token] = timestamps
        
        return True, user_id


# ============================================================================
# Message Handler
# ============================================================================

class MessageHandler:
    """Handles incoming WebSocket messages."""
    
    def __init__(
        self,
        connection_manager: ConnectionManager,
        pubsub: Any,  # RedisPubSub or LocalPubSub
        authenticator: Authenticator
    ):
        self.connection_manager = connection_manager
        self.pubsub = pubsub
        self.authenticator = authenticator
        self._protocol = ProtocolHandler()
    
    async def handle_message(self, conn: Connection, data: Any):
        """Handle an incoming message."""
        conn.metrics.messages_received += 1
        conn.metrics.last_message_at = time.time()
        
        try:
            # Determine if binary or text
            if isinstance(data, bytes):
                msg_type, payload = self._protocol.decode(data)
                conn.use_binary = True
            else:
                msg_type, payload = conn.json_handler.decode(data)
                conn.use_binary = False
            
            # Route to appropriate handler
            if msg_type == MessageType.AUTH:
                await self._handle_auth(conn, payload)
            elif msg_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(conn, payload)
            elif msg_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(conn, payload)
            elif msg_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(conn, payload)
            else:
                await conn.send_error(
                    ErrorCode.INVALID_MESSAGE,
                    f"Unexpected message type: {msg_type.name}"
                )
        
        except Exception as e:
            logger.error(f"Error handling message from {conn.id}: {e}")
            conn.metrics.errors += 1
            await conn.send_error(ErrorCode.INVALID_MESSAGE, str(e))
    
    async def _handle_auth(self, conn: Connection, auth_msg: AuthMessage):
        """Handle authentication request."""
        if conn.state == ConnectionState.OPEN:
            await conn.send_error(
                ErrorCode.AUTH_FAILED,
                "Already authenticated"
            )
            return
        
        success, user_id = await self.authenticator.authenticate(auth_msg)
        
        if not success:
            await conn.send_error(
                ErrorCode.AUTH_FAILED,
                "Invalid authentication credentials"
            )
            await self.connection_manager.disconnect(conn.id, "Auth failed")
            return
        
        await self.connection_manager.authenticate(
            conn.id, user_id, auth_msg.api_key
        )
        
        # Register with pubsub
        await self.pubsub.register_subscriber(
            conn.id,
            self._create_delivery_callback(conn.id)
        )
        
        # Send success response
        response = self._protocol.encode(MessageType.AUTH, {
            'success': True,
            'user_id': user_id,
            'connection_id': conn.id
        })
        await conn.send(response)
    
    async def _handle_subscribe(self, conn: Connection, sub_msg: SubscribeMessage):
        """Handle subscribe request."""
        if GatewayConfig.REQUIRE_AUTH and conn.state != ConnectionState.OPEN:
            await conn.send_error(
                ErrorCode.AUTH_FAILED,
                "Authentication required"
            )
            return
        
        # Map channel type to prefix
        channel_prefix = {
            ChannelType.TICKER: "ticker",
            ChannelType.ORDERBOOK: "orderbook",
            ChannelType.TRADE: "trade",
            ChannelType.PORTFOLIO: "portfolio",
            ChannelType.SYSTEM: "system",
            ChannelType.CUSTOM: "custom"
        }.get(sub_msg.channel_type, "custom")
        
        full_channel = f"{channel_prefix}:{sub_msg.channel}"
        
        # Check permissions for portfolio channels
        if sub_msg.channel_type == ChannelType.PORTFOLIO:
            if not conn.user_id or sub_msg.channel != conn.user_id:
                await conn.send_error(
                    ErrorCode.PERMISSION_DENIED,
                    "Cannot subscribe to another user's portfolio",
                    sub_msg.channel
                )
                return
        
        success = await self.pubsub.subscribe(conn.id, full_channel)
        
        if success:
            conn.metrics.subscriptions.add(full_channel)
            
            # Send acknowledgment
            ack = self._protocol.encode_ack(0)
            await conn.send(ack)
            
            logger.debug(f"Connection {conn.id} subscribed to {full_channel}")
        else:
            await conn.send_error(
                ErrorCode.ALREADY_SUBSCRIBED,
                "Already subscribed to channel",
                sub_msg.channel
            )
    
    async def _handle_unsubscribe(self, conn: Connection, unsub_msg: UnsubscribeMessage):
        """Handle unsubscribe request."""
        # Try to find the full channel name
        full_channel = None
        for sub in conn.metrics.subscriptions:
            if sub.endswith(f":{unsub_msg.channel}"):
                full_channel = sub
                break
        
        if not full_channel:
            await conn.send_error(
                ErrorCode.NOT_SUBSCRIBED,
                "Not subscribed to channel",
                unsub_msg.channel
            )
            return
        
        success = await self.pubsub.unsubscribe(conn.id, full_channel)
        
        if success:
            conn.metrics.subscriptions.discard(full_channel)
            ack = self._protocol.encode_ack(0)
            await conn.send(ack)
        else:
            await conn.send_error(
                ErrorCode.NOT_SUBSCRIBED,
                "Failed to unsubscribe",
                unsub_msg.channel
            )
    
    async def _handle_heartbeat(self, conn: Connection, hb_msg: HeartbeatMessage):
        """Handle heartbeat/ping."""
        conn.record_heartbeat(received=True)
        
        # Calculate latency if client sent timestamp
        latency_ms = None
        if hb_msg.timestamp:
            latency_ms = int(time.time() * 1000) - hb_msg.timestamp
        
        # Send pong
        pong = self._protocol.encode_heartbeat(
            seq=hb_msg.seq,
            latency_ms=latency_ms
        )
        await conn.send(pong)
        conn.record_heartbeat()
    
    def _create_delivery_callback(self, conn_id: str) -> Callable:
        """Create a callback for pubsub message delivery."""
        async def deliver(subscriber_id: str, messages: List[bytes]):
            conn = self.connection_manager.get_connection(conn_id)
            if not conn or conn.state != ConnectionState.OPEN:
                return
            
            # Queue messages for batching
            for msg in messages:
                await conn.queue_message(msg)
        
        return deliver


# ============================================================================
# Heartbeat Manager
# ============================================================================

class HeartbeatManager:
    """Manages heartbeats for all connections."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._protocol = ProtocolHandler()
    
    async def start(self):
        """Start the heartbeat manager."""
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat manager started")
    
    async def stop(self):
        """Stop the heartbeat manager."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat manager stopped")
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to all connections."""
        while self._running:
            await asyncio.sleep(GatewayConfig.HEARTBEAT_INTERVAL)
            
            connections = self.connection_manager.get_all_connections()
            heartbeat_msg = self._protocol.encode_heartbeat()
            
            for conn in connections:
                if conn.state == ConnectionState.OPEN:
                    try:
                        await conn.send(heartbeat_msg)
                        conn.record_heartbeat()
                    except Exception as e:
                        logger.debug(f"Failed to send heartbeat to {conn.id}: {e}")


# ============================================================================
# WebSocket Server
# ============================================================================

class WebSocketServer:
    """
    High-performance WebSocket server for DragonScope Enterprise.
    
    Supports 100k+ concurrent connections with:
    - Channel-based pub/sub
    - Authentication
    - Heartbeat handling
    - Message batching
    - Automatic reconnection support
    """  # noqa: D205
    
    def __init__(
        self,
        redis_url: str = GatewayConfig.REDIS_URL,
        use_redis: bool = GatewayConfig.USE_REDIS,
        require_auth: bool = GatewayConfig.REQUIRE_AUTH
    ):
        self.connection_manager = ConnectionManager()
        self.authenticator = Authenticator(require_auth=require_auth)
        self.heartbeat_manager = HeartbeatManager(self.connection_manager)
        
        # Choose pubsub implementation
        if use_redis:
            self.pubsub = RedisPubSub(redis_url=redis_url)
        else:
            self.pubsub = LocalPubSub()
        
        self.message_handler = MessageHandler(
            self.connection_manager,
            self.pubsub,
            self.authenticator
        )
        
        self._running = False
        self._app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application."""
        app = FastAPI(
            title="DragonScope Enterprise WebSocket Gateway",
            description="Real-time WebSocket gateway for financial data streaming",
            version="1.0.0"
        )
        
        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # WebSocket endpoint
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
        
        # Health check
        @app.get("/health")
        async def health():
            return {
                "status": "healthy" if self._running else "starting",
                "connections": self.connection_manager.metrics,
                "pubsub": self.pubsub.get_metrics()
            }
        
        # Metrics endpoint
        @app.get("/metrics")
        async def metrics():
            return {
                "connections": self.connection_manager.metrics,
                "pubsub": self.pubsub.get_metrics()
            }
        
        # Channel info
        @app.get("/channels")
        async def channels():
            return self.pubsub.get_metrics().get('channels', {})
        
        return app
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle a WebSocket connection."""
        # Get remote address
        remote_addr = websocket.client.host if websocket.client else "unknown"
        
        # Accept connection
        conn = await self.connection_manager.connect(websocket, remote_addr)
        if not conn:
            await websocket.close(code=1008, reason="Connection limit reached")
            return
        
        # Set initial state
        conn.state = ConnectionState.AUTHENTICATING
        
        # Handle messages
        try:
            while conn.state in (ConnectionState.AUTHENTICATING, ConnectionState.OPEN):
                # Receive message with timeout
                try:
                    data = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=GatewayConfig.HEARTBEAT_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    if conn.is_heartbeat_overdue():
                        raise WebSocketDisconnect(code=1001, reason="Heartbeat timeout")
                    continue
                
                # Handle different message types
                if "bytes" in data:
                    await self.message_handler.handle_message(conn, data["bytes"])
                elif "text" in data:
                    await self.message_handler.handle_message(conn, data["text"])
                elif data.get("type") == "websocket.disconnect":
                    raise WebSocketDisconnect(
                        code=data.get("code", 1000),
                        reason="Client disconnected"
                    )
        
        except WebSocketDisconnect as e:
            logger.info(f"Connection {conn.id} disconnected: {e.reason}")
        except Exception as e:
            logger.error(f"Error in WebSocket handler for {conn.id}: {e}")
        finally:
            # Cleanup
            await self.pubsub.unregister_subscriber(conn.id)
            await self.connection_manager.disconnect(conn.id, "Connection closed")
    
    async def start(self):
        """Start the WebSocket server."""
        if self._running:
            return
        
        self._running = True
        
        # Start components
        await self.connection_manager.start()
        await self.pubsub.start()
        await self.heartbeat_manager.start()
        
        logger.info("WebSocket server started")
    
    async def stop(self):
        """Stop the WebSocket server."""
        if not self._running:
            return
        
        self._running = False
        
        # Stop components
        await self.heartbeat_manager.stop()
        await self.connection_manager.stop()
        await self.pubsub.stop()
        
        logger.info("WebSocket server stopped")
    
    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self._app
    
    # Convenience methods for publishing
    
    async def publish_ticker(
        self,
        symbol: str,
        price: float,
        change: float,
        volume: float
    ):
        """Publish a ticker update."""
        builder = MessageBuilder()
        msg = builder.ticker_update(symbol, price, change, volume)
        await self.pubsub.publish(f"ticker:{symbol}", msg)
    
    async def publish_orderbook(
        self,
        symbol: str,
        bids: List[tuple],
        asks: List[tuple],
        sequence: int = 0,
        is_snapshot: bool = False
    ):
        """Publish an orderbook update."""
        builder = MessageBuilder()
        msg = builder.orderbook_update(symbol, bids, asks, sequence, is_snapshot)
        await self.pubsub.publish(f"orderbook:{symbol}", msg)
    
    async def publish_portfolio(
        self,
        user_id: str,
        balances: dict,
        positions: dict,
        pnl: Optional[dict] = None
    ):
        """Publish a portfolio update."""
        builder = MessageBuilder()
        msg = builder.portfolio_update(user_id, balances, positions, pnl)
        await self.pubsub.publish(f"portfolio:{user_id}", msg)


# ============================================================================
# Factory function for easy setup
# ============================================================================

def create_server(
    redis_url: str = GatewayConfig.REDIS_URL,
    use_redis: bool = True,
    require_auth: bool = True
) -> WebSocketServer:
    """Create and configure a WebSocket server."""
    return WebSocketServer(
        redis_url=redis_url,
        use_redis=use_redis,
        require_auth=require_auth
    )


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Create server
    server = create_server(
        redis_url="redis://localhost:6379",
        use_redis=False,  # Use local pub/sub for standalone testing
        require_auth=False  # Disable auth for testing
    )
    
    # Start server components
    async def startup():
        await server.start()
    
    # Run startup
    asyncio.get_event_loop().run_until_complete(startup())
    
    # Run uvicorn
    uvicorn.run(
        server.app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        lifespan="on"
    )
