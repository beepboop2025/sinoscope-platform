# DragonScope Enterprise WebSocket Gateway

A high-performance WebSocket gateway designed for financial data streaming, supporting 100,000+ concurrent connections with channel-based pub/sub, authentication, heartbeat handling, and automatic reconnection.

## Features

- **100k+ Concurrent Connections**: Efficient connection management with per-IP rate limiting
- **Channel-based Pub/Sub**: Subscribe to tickers, orderbooks, portfolios, and custom channels
- **Binary Protocol**: MessagePack encoding with zlib/lz4 compression for minimal bandwidth
- **Authentication**: JWT-based auth over WebSocket with configurable requirements
- **Heartbeat/Ping-Pong**: Automatic keep-alive with configurable timeouts
- **Message Batching**: Efficient batched message delivery to reduce overhead
- **Backpressure Handling**: Circuit breaker pattern and message buffering
- **Redis Integration**: Distributed pub/sub support for horizontal scaling
- **Automatic Reconnection**: Client library with exponential backoff
- **Comprehensive Metrics**: Real-time monitoring of connections, throughput, and latency

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   WebSocket     │────▶│  Connection      │────▶│   Channel       │
│   Clients       │     │  Manager         │     │   Manager       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                           │
                               ▼                           ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Message         │────▶│  Pub/Sub        │
                        │  Handler         │     │  (Redis/Local)  │
                        └──────────────────┘     └─────────────────┘
```

## Quick Start

### Installation

```bash
cd /Users/mrinal/dev/DragonScope/enterprise/services/gateway
pip install -r requirements.txt
```

### Running the Server

```bash
# Standalone mode (no Redis)
python websocket_server.py

# With Redis support
REDIS_URL=redis://localhost:6379 python websocket_server.py
```

The server will start on `ws://localhost:8000/ws`.

### Using the Client

```python
import asyncio
from client_example import DragonScopeClient, ChannelType

async def main():
    client = DragonScopeClient(
        uri="ws://localhost:8000/ws",
        use_binary=True,
        auto_reconnect=True
    )
    
    # Handle messages
    def on_ticker(channel, payload):
        print(f"Ticker: {payload.data}")
    
    client.on_channel("ticker:BTC-USD", on_ticker)
    
    # Connect
    await client.connect()
    
    # Subscribe
    await client.subscribe("BTC-USD", ChannelType.TICKER)
    
    # Keep running
    await asyncio.sleep(60)
    await client.disconnect()

asyncio.run(main())
```

## Protocol

### Message Types

| Type | Code | Description |
|------|------|-------------|
| SUBSCRIBE | 1 | Subscribe to a channel |
| UNSUBSCRIBE | 2 | Unsubscribe from a channel |
| SNAPSHOT | 3 | Full state snapshot |
| UPDATE | 4 | Incremental update |
| ERROR | 5 | Error response |
| HEARTBEAT | 6 | Keep-alive ping/pong |
| AUTH | 7 | Authentication request/response |
| BATCH | 8 | Batched messages |
| ACK | 9 | Acknowledgment |

### Channel Types

| Type | Code | Description |
|------|------|-------------|
| TICKER | 1 | Price ticker data |
| ORDERBOOK | 2 | Order book updates |
| TRADE | 3 | Trade executions |
| PORTFOLIO | 4 | User portfolio updates |
| SYSTEM | 5 | System messages |
| CUSTOM | 6 | Custom channels |

### Binary Protocol Format

```
[version:1][msg_type:1][compression:1][flags:1][payload_len:4][payload:N]
```

- **version**: Protocol version (currently 1)
- **msg_type**: Message type identifier
- **compression**: Compression algorithm (0=none, 1=zlib, 2=lz4)
- **flags**: Bit flags (0x01 = compressed)
- **payload_len**: Payload length in bytes (4 bytes, big-endian)
- **payload**: MessagePack encoded payload

### Example Messages

#### Subscribe
```json
{
  "type": "SUBSCRIBE",
  "payload": {
    "channel": "BTC-USD",
    "channel_type": 1,
    "snapshot": true
  }
}
```

#### Ticker Update
```json
{
  "type": "UPDATE",
  "payload": {
    "channel": "ticker:BTC-USD",
    "channel_type": 1,
    "data": {
      "symbol": "BTC-USD",
      "price": 50000.00,
      "change": 1000.00,
      "volume": 1000000.00
    },
    "timestamp": 1709123456789
  }
}
```

## Server API

### Publishing Data

```python
from websocket_server import create_server

server = create_server()
await server.start()

# Publish ticker
await server.publish_ticker("BTC-USD", price=50000.0, change=1000.0, volume=1000000.0)

# Publish orderbook
await server.publish_orderbook(
    "BTC-USD",
    bids=[(49999.0, 1.5), (49998.0, 2.0)],
    asks=[(50001.0, 1.2), (50002.0, 3.0)],
    sequence=12345
)

# Publish portfolio update
await server.publish_portfolio(
    user_id="user_123",
    balances={"USD": {"available": 10000.0, "locked": 500.0}},
    positions={"BTC": {"size": 2.5, "entry_price": 45000.0}}
)
```

### Health & Metrics

```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# Channel info
curl http://localhost:8000/channels
```

## Configuration

### GatewayConfig

```python
class GatewayConfig:
    MAX_CONNECTIONS = 100000
    CONNECTIONS_PER_IP = 100
    
    CONNECTION_TIMEOUT = 60.0
    HEARTBEAT_INTERVAL = 30.0
    HEARTBEAT_TIMEOUT = 60.0
    AUTH_TIMEOUT = 10.0
    
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    MESSAGES_PER_SECOND = 100
    BATCH_SIZE = 100
    BATCH_INTERVAL_MS = 10
    
    ENABLE_COMPRESSION = True
    ENABLE_METRICS = True
    REQUIRE_AUTH = True
    
    REDIS_URL = "redis://localhost:6379"
    USE_REDIS = True
```

## Benchmarking

Run performance benchmarks:

```bash
# All benchmarks
python benchmark.py

# Specific tests
python benchmark.py connections
python benchmark.py throughput
python benchmark.py latency
```

## Backpressure & Circuit Breaker

The pub/sub system includes sophisticated backpressure handling:

```python
from pubsub import RedisPubSub, BackpressureStrategy

pubsub = RedisPubSub(
    redis_url="redis://localhost:6379",
    buffer_size=10000,
    strategy=BackpressureStrategy.DROP_OLD  # or DROP_NEW, BLOCK, THROTTLE
)
```

Circuit breaker configuration:

```python
from pubsub import CircuitBreaker

cb = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3
)
```

## Scaling

### Single Instance (Local Pub/Sub)

```python
server = create_server(use_redis=False)
```

Best for: Development, small deployments (<10k connections)

### Multi-Instance (Redis Pub/Sub)

```python
server = create_server(
    redis_url="redis://redis-cluster:6379",
    use_redis=True
)
```

Best for: Production, horizontal scaling (100k+ connections)

## File Structure

```
gateway/
├── __init__.py           # Package exports
├── websocket_server.py   # Main server implementation
├── protocol.py          # Binary protocol & message types
├── pubsub.py           # Redis/Local pub/sub
├── client_example.py   # Example client implementation
├── benchmark.py        # Performance benchmarks
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## License

Proprietary - DragonScope Enterprise
