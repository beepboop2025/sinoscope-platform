"""
DragonScope Enterprise - WebSocket Protocol
===========================================
Binary protocol using MessagePack with compression and schema validation.

Message Types:
- SUBSCRIBE: Subscribe to a channel
- UNSUBSCRIBE: Unsubscribe from a channel
- SNAPSHOT: Full state snapshot
- UPDATE: Incremental update
- ERROR: Error response
- HEARTBEAT: Keep-alive ping/pong
- AUTH: Authentication request/response
"""

import enum
import zlib
import struct
import time
from typing import Any, Optional, Union
from dataclasses import dataclass, field

import msgpack
import lz4.frame
from pydantic import BaseModel, Field, validator


class MessageType(enum.IntEnum):
    """WebSocket message type identifiers."""
    SUBSCRIBE = 1
    UNSUBSCRIBE = 2
    SNAPSHOT = 3
    UPDATE = 4
    ERROR = 5
    HEARTBEAT = 6
    AUTH = 7
    BATCH = 8
    ACK = 9


class ChannelType(enum.IntEnum):
    """Channel type identifiers."""
    TICKER = 1
    ORDERBOOK = 2
    TRADE = 3
    PORTFOLIO = 4
    SYSTEM = 5
    CUSTOM = 6


class CompressionType(enum.IntEnum):
    """Compression algorithm identifiers."""
    NONE = 0
    ZLIB = 1
    LZ4 = 2


class ErrorCode(enum.IntEnum):
    """Error code identifiers."""
    UNKNOWN = 0
    INVALID_MESSAGE = 1
    AUTH_FAILED = 2
    AUTH_EXPIRED = 3
    RATE_LIMITED = 4
    CHANNEL_NOT_FOUND = 5
    ALREADY_SUBSCRIBED = 6
    NOT_SUBSCRIBED = 7
    PERMISSION_DENIED = 8
    INTERNAL_ERROR = 9


# ============================================================================
# Pydantic Models for Validation
# ============================================================================

class SubscribeMessage(BaseModel):
    """Subscribe request message."""
    channel: str = Field(..., min_length=1, max_length=256)
    channel_type: ChannelType = ChannelType.CUSTOM
    params: dict = Field(default_factory=dict)
    snapshot: bool = True  # Request initial snapshot
    
    @validator('channel')
    def validate_channel(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Channel cannot be empty')
        return v.strip().lower()


class UnsubscribeMessage(BaseModel):
    """Unsubscribe request message."""
    channel: str = Field(..., min_length=1, max_length=256)


class AuthMessage(BaseModel):
    """Authentication message."""
    token: str = Field(..., min_length=10)
    api_key: Optional[str] = None
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    signature: Optional[str] = None


class HeartbeatMessage(BaseModel):
    """Heartbeat ping/pong message."""
    seq: int = 0
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    latency_ms: Optional[int] = None


class ErrorMessage(BaseModel):
    """Error response message."""
    code: ErrorCode = ErrorCode.UNKNOWN
    message: str = "Unknown error"
    channel: Optional[str] = None
    details: Optional[dict] = None


class DataMessage(BaseModel):
    """Data message (snapshot or update)."""
    channel: str
    channel_type: ChannelType
    data: Any
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    sequence: int = 0
    is_snapshot: bool = False


class BatchMessage(BaseModel):
    """Batched message containing multiple updates."""
    messages: list = Field(default_factory=list, max_length=100)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


# ============================================================================
# Protocol Handler
# ============================================================================

PROTOCOL_VERSION = 1
HEADER_SIZE = 8  # bytes: [version(1) | msg_type(1) | compression(1) | flags(1) | payload_len(4)]
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB max payload
COMPRESSION_THRESHOLD = 512  # Compress payloads larger than 512 bytes


class ProtocolError(Exception):
    """Protocol-related error."""
    pass


class ProtocolHandler:
    """Handles encoding/decoding of WebSocket messages."""
    
    def __init__(self, default_compression: CompressionType = CompressionType.ZLIB):
        self.default_compression = default_compression
        self._compression_stats = {
            'compressed': 0,
            'uncompressed': 0,
            'bytes_saved': 0
        }
    
    def encode(
        self,
        msg_type: MessageType,
        payload: Union[dict, BaseModel],
        compression: Optional[CompressionType] = None,
        flags: int = 0
    ) -> bytes:
        """
        Encode a message into binary format.
        
        Format:
        [version:1][msg_type:1][compression:1][flags:1][payload_len:4][payload:N]
        """
        # Convert pydantic model to dict if needed
        if isinstance(payload, BaseModel):
            payload = payload.dict()
        
        # Pack payload with msgpack
        packed = msgpack.packb(payload, use_bin_type=True)
        
        # Apply compression if needed
        if compression is None:
            compression = self.default_compression
        
        if compression != CompressionType.NONE and len(packed) > COMPRESSION_THRESHOLD:
            packed = self._compress(packed, compression)
            flags |= 0x01  # Set compressed flag
        else:
            compression = CompressionType.NONE
        
        if len(packed) > MAX_PAYLOAD_SIZE:
            raise ProtocolError(f"Payload too large: {len(packed)} bytes")
        
        # Build header
        header = struct.pack(
            '>BBBBI',
            PROTOCOL_VERSION,
            int(msg_type),
            int(compression),
            flags,
            len(packed)
        )
        
        return header + packed
    
    def decode(self, data: bytes) -> tuple[MessageType, Union[dict, BaseModel]]:
        """
        Decode a binary message.
        
        Returns: (message_type, payload)
        """
        if len(data) < HEADER_SIZE:
            raise ProtocolError(f"Message too short: {len(data)} bytes")
        
        # Parse header
        version, msg_type, compression, flags, payload_len = struct.unpack(
            '>BBBBI', data[:HEADER_SIZE]
        )
        
        if version != PROTOCOL_VERSION:
            raise ProtocolError(f"Unsupported protocol version: {version}")
        
        if len(data) < HEADER_SIZE + payload_len:
            raise ProtocolError("Incomplete message")
        
        payload = data[HEADER_SIZE:HEADER_SIZE + payload_len]
        
        # Decompress if needed
        if flags & 0x01:
            payload = self._decompress(payload, CompressionType(compression))
        
        # Unpack with msgpack
        try:
            unpacked = msgpack.unpackb(payload, raw=False)
        except Exception as e:
            raise ProtocolError(f"Failed to unpack message: {e}")
        
        # Validate based on message type
        msg_type_enum = MessageType(msg_type)
        validated = self._validate_payload(msg_type_enum, unpacked)
        
        return msg_type_enum, validated
    
    def _compress(self, data: bytes, compression: CompressionType) -> bytes:
        """Compress data using specified algorithm."""
        original_size = len(data)
        
        if compression == CompressionType.ZLIB:
            compressed = zlib.compress(data, level=6)
        elif compression == CompressionType.LZ4:
            compressed = lz4.frame.compress(data)
        else:
            return data
        
        # Update stats
        if len(compressed) < original_size:
            self._compression_stats['compressed'] += 1
            self._compression_stats['bytes_saved'] += (original_size - len(compressed))
        else:
            self._compression_stats['uncompressed'] += 1
        
        return compressed if len(compressed) < original_size else data
    
    def _decompress(self, data: bytes, compression: CompressionType) -> bytes:
        """Decompress data using specified algorithm."""
        try:
            if compression == CompressionType.ZLIB:
                return zlib.decompress(data)
            elif compression == CompressionType.LZ4:
                return lz4.frame.decompress(data)
            else:
                raise ProtocolError(f"Unknown compression type: {compression}")
        except Exception as e:
            raise ProtocolError(f"Decompression failed: {e}")
    
    def _validate_payload(
        self,
        msg_type: MessageType,
        payload: dict
    ) -> Union[dict, BaseModel]:
        """Validate payload based on message type."""
        try:
            if msg_type == MessageType.SUBSCRIBE:
                return SubscribeMessage(**payload)
            elif msg_type == MessageType.UNSUBSCRIBE:
                return UnsubscribeMessage(**payload)
            elif msg_type == MessageType.AUTH:
                return AuthMessage(**payload)
            elif msg_type == MessageType.HEARTBEAT:
                return HeartbeatMessage(**payload)
            elif msg_type == MessageType.ERROR:
                return ErrorMessage(**payload)
            elif msg_type in (MessageType.SNAPSHOT, MessageType.UPDATE):
                return DataMessage(**payload)
            elif msg_type == MessageType.BATCH:
                return BatchMessage(**payload)
            else:
                return payload
        except Exception as e:
            raise ProtocolError(f"Validation failed: {e}")
    
    def encode_error(
        self,
        code: ErrorCode,
        message: str,
        channel: Optional[str] = None,
        details: Optional[dict] = None
    ) -> bytes:
        """Encode an error message."""
        error = ErrorMessage(
            code=code,
            message=message,
            channel=channel,
            details=details
        )
        return self.encode(MessageType.ERROR, error)
    
    def encode_data(
        self,
        channel: str,
        channel_type: ChannelType,
        data: Any,
        is_snapshot: bool = False,
        sequence: int = 0
    ) -> bytes:
        """Encode a data message."""
        msg = DataMessage(
            channel=channel,
            channel_type=channel_type,
            data=data,
            is_snapshot=is_snapshot,
            sequence=sequence
        )
        msg_type = MessageType.SNAPSHOT if is_snapshot else MessageType.UPDATE
        return self.encode(msg_type, msg)
    
    def encode_batch(self, messages: list[bytes]) -> bytes:
        """
        Encode multiple messages into a batch.
        
        Each message in the list should already be encoded.
        """
        batch = BatchMessage(
            messages=[self.decode(m)[1].dict() if isinstance(m, bytes) else m for m in messages]
        )
        return self.encode(MessageType.BATCH, batch)
    
    def encode_heartbeat(self, seq: int = 0, latency_ms: Optional[int] = None) -> bytes:
        """Encode a heartbeat message."""
        hb = HeartbeatMessage(seq=seq, latency_ms=latency_ms)
        return self.encode(MessageType.HEARTBEAT, hb)
    
    def encode_ack(self, message_seq: int) -> bytes:
        """Encode an acknowledgment message."""
        return self.encode(MessageType.ACK, {'seq': message_seq})
    
    @property
    def compression_stats(self) -> dict:
        """Get compression statistics."""
        return self._compression_stats.copy()


# ============================================================================
# Message Builder Utilities
# ============================================================================

class MessageBuilder:
    """Utility class for building common message types."""
    
    def __init__(self, handler: Optional[ProtocolHandler] = None):
        self.handler = handler or ProtocolHandler()
    
    def subscribe(
        self,
        channel: str,
        channel_type: ChannelType = ChannelType.CUSTOM,
        params: Optional[dict] = None,
        snapshot: bool = True
    ) -> bytes:
        """Build a subscribe message."""
        msg = SubscribeMessage(
            channel=channel,
            channel_type=channel_type,
            params=params or {},
            snapshot=snapshot
        )
        return self.handler.encode(MessageType.SUBSCRIBE, msg)
    
    def unsubscribe(self, channel: str) -> bytes:
        """Build an unsubscribe message."""
        msg = UnsubscribeMessage(channel=channel)
        return self.handler.encode(MessageType.UNSUBSCRIBE, msg)
    
    def auth(
        self,
        token: str,
        api_key: Optional[str] = None,
        signature: Optional[str] = None
    ) -> bytes:
        """Build an authentication message."""
        msg = AuthMessage(
            token=token,
            api_key=api_key,
            signature=signature
        )
        return self.handler.encode(MessageType.AUTH, msg)
    
    def ticker_update(
        self,
        symbol: str,
        price: float,
        change: float,
        volume: float,
        timestamp: Optional[int] = None
    ) -> bytes:
        """Build a ticker update message."""
        data = {
            'symbol': symbol,
            'price': price,
            'change': change,
            'volume': volume,
            'timestamp': timestamp or int(time.time() * 1000)
        }
        return self.handler.encode_data(
            channel=f"ticker:{symbol}",
            channel_type=ChannelType.TICKER,
            data=data
        )
    
    def orderbook_update(
        self,
        symbol: str,
        bids: list[tuple[float, float]],
        asks: list[tuple[float, float]],
        sequence: int = 0,
        is_snapshot: bool = False
    ) -> bytes:
        """Build an orderbook update message."""
        data = {
            'symbol': symbol,
            'bids': bids,
            'asks': asks,
            'sequence': sequence
        }
        return self.handler.encode_data(
            channel=f"orderbook:{symbol}",
            channel_type=ChannelType.ORDERBOOK,
            data=data,
            is_snapshot=is_snapshot,
            sequence=sequence
        )
    
    def portfolio_update(
        self,
        user_id: str,
        balances: dict[str, dict],
        positions: dict[str, dict],
        pnl: Optional[dict] = None
    ) -> bytes:
        """Build a portfolio update message."""
        data = {
            'user_id': user_id,
            'balances': balances,
            'positions': positions,
            'pnl': pnl or {}
        }
        return self.handler.encode_data(
            channel=f"portfolio:{user_id}",
            channel_type=ChannelType.PORTFOLIO,
            data=data
        )


# ============================================================================
# JSON Fallback Protocol (for clients that don't support binary)
# ============================================================================

import json


class JSONProtocolHandler:
    """JSON-based protocol handler for text WebSocket clients."""
    
    def __init__(self):
        self._message_types = {t.name: t for t in MessageType}
        self._channel_types = {t.name: t for t in ChannelType}
        self._error_codes = {t.name: t for t in ErrorCode}
    
    def encode(
        self,
        msg_type: MessageType,
        payload: Union[dict, BaseModel]
    ) -> str:
        """Encode a message to JSON string."""
        if isinstance(payload, BaseModel):
            payload = payload.dict()
        
        return json.dumps({
            'type': msg_type.name,
            'payload': payload
        })
    
    def decode(self, data: str) -> tuple[MessageType, Union[dict, BaseModel]]:
        """Decode a JSON message."""
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise ProtocolError(f"Invalid JSON: {e}")
        
        msg_type_name = parsed.get('type')
        payload = parsed.get('payload', {})
        
        if msg_type_name not in self._message_types:
            raise ProtocolError(f"Unknown message type: {msg_type_name}")
        
        msg_type = self._message_types[msg_type_name]
        
        # Basic validation
        if msg_type == MessageType.SUBSCRIBE:
            payload = SubscribeMessage(**payload)
        elif msg_type == MessageType.UNSUBSCRIBE:
            payload = UnsubscribeMessage(**payload)
        elif msg_type == MessageType.AUTH:
            payload = AuthMessage(**payload)
        elif msg_type == MessageType.HEARTBEAT:
            payload = HeartbeatMessage(**payload)
        
        return msg_type, payload
