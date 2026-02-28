# DragonScope Enterprise - API Reference

Complete API documentation for integrating with DragonScope Enterprise.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [REST API](#rest-api)
4. [WebSocket API](#websocket-api)
5. [Rate Limiting](#rate-limiting)
6. [Error Codes](#error-codes)
7. [Code Examples](#code-examples)

---

## Overview

### Base URLs

| Environment | URL | Purpose |
|-------------|-----|---------|
| Production | `https://api.dragonscope.io/v3` | Live trading |
| Sandbox | `https://sandbox-api.dragonscope.io/v3` | Testing |
| Enterprise On-Prem | `https://your-domain.com/api/v3` | Self-hosted |

### WebSocket Endpoints

| Environment | URL |
|-------------|-----|
| Production | `wss://ws.dragonscope.io/v3` |
| Sandbox | `wss://sandbox-ws.dragonscope.io/v3` |

### API Versions

| Version | Status | Sunset Date |
|---------|--------|-------------|
| v3 | Current | - |
| v2 | Deprecated | 2026-12-31 |
| v1 | Deprecated | 2026-06-30 |

---

## Authentication

DragonScope Enterprise supports multiple authentication methods.

### API Key Authentication

**For server-to-server integrations:**

```http
GET /v3/market/quotes/AAPL
Authorization: Bearer ds_api_YOUR_API_KEY
```

**Generating API Keys:**
```bash
curl -X POST https://api.dragonscope.io/v3/auth/keys \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "name": "Trading Bot",
    "permissions": ["market:read", "orders:write"],
    "ip_whitelist": ["203.0.113.0/24"],
    "expires_at": "2026-12-31T23:59:59Z"
  }'
```

### OAuth 2.0

**For user-authorized applications:**

```http
# Authorization URL
https://auth.dragonscope.io/oauth/authorize?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=https://yourapp.com/callback&
  scope=market:read+orders:write+portfolio:read&
  state=RANDOM_STATE
```

**Token Exchange:**
```bash
curl -X POST https://auth.dragonscope.io/oauth/token \
  -d "grant_type=authorization_code" \
  -d "code=AUTH_CODE" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "redirect_uri=https://yourapp.com/callback"
```

**Response:**
```json
{
  "access_token": "ds_at_eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "ds_rt_dGhpcyBpcyBhIHJlZnJlc2g...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "market:read orders:write portfolio:read"
}
```

### JWT Token Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-2026-01"
  },
  "payload": {
    "iss": "dragonscope.io",
    "sub": "user_12345",
    "aud": "api.dragonscope.io",
    "exp": 1705315200,
    "iat": 1705311600,
    "jti": "token_abc123",
    "scope": ["market:read", "orders:write"],
    "org_id": "org_enterprise_01",
    "tier": "enterprise"
  }
}
```

### Permission Scopes

| Scope | Description |
|-------|-------------|
| `market:read` | Access market data |
| `market:stream` | WebSocket market data |
| `orders:read` | View orders |
| `orders:write` | Create/cancel orders |
| `portfolio:read` | View positions |
| `portfolio:write` | Modify positions |
| `account:read` | View account info |
| `admin:users` | User management |
| `admin:config` | System configuration |

---

## REST API

### Market Data

#### Get Quote

```http
GET /v3/market/quotes/{symbol}
```

**Response:**
```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "exchange": "NASDAQ",
  "currency": "USD",
  "last_price": 185.92,
  "bid": 185.90,
  "ask": 185.95,
  "bid_size": 500,
  "ask_size": 300,
  "volume": 45230000,
  "open": 183.50,
  "high": 186.10,
  "low": 182.75,
  "close": 183.58,
  "change": 2.34,
  "change_percent": 1.27,
  "timestamp": "2026-01-15T14:30:00.123Z",
  "market_status": "open",
  "extended_hours": {
    "last_price": 186.05,
    "change": 2.47,
    "timestamp": "2026-01-15T20:15:00.456Z"
  }
}
```

#### Get Multiple Quotes

```http
GET /v3/market/quotes?symbols=AAPL,MSFT,GOOGL
```

#### Get Historical Bars

```http
GET /v3/market/history/{symbol}?timeframe=1d&start=2026-01-01&end=2026-01-15
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `symbol` | string | Security symbol |
| `timeframe` | string | 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1m |
| `start` | ISO8601 | Start date/time |
| `end` | ISO8601 | End date/time |
| `limit` | integer | Max results (default: 1000, max: 10000) |

**Response:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "bars": [
    {
      "timestamp": "2026-01-15T00:00:00Z",
      "open": 183.50,
      "high": 186.10,
      "low": 182.75,
      "close": 185.92,
      "volume": 45230000,
      "vwap": 184.82
    }
  ]
}
```

#### Get Order Book (Level 2)

```http
GET /v3/market/orderbook/{symbol}?depth=20
```

**Response:**
```json
{
  "symbol": "AAPL",
  "timestamp": "2026-01-15T14:30:00.123Z",
  "bids": [
    {"price": 185.90, "size": 500, "orders": 12},
    {"price": 185.89, "size": 300, "orders": 8},
    {"price": 185.88, "size": 1500, "orders": 25}
  ],
  "asks": [
    {"price": 185.95, "size": 300, "orders": 10},
    {"price": 185.96, "size": 800, "orders": 15},
    {"price": 185.97, "size": 200, "orders": 5}
  ],
  "spread": 0.05,
  "spread_percent": 0.027
}
```

#### Get Trades (Time & Sales)

```http
GET /v3/market/trades/{symbol}?limit=100
```

---

### Trading

#### Place Order

```http
POST /v3/orders
```

**Request:**
```json
{
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 100,
  "order_type": "limit",
  "limit_price": 185.50,
  "time_in_force": "day",
  "client_order_id": "my_strategy_001",
  "extended_hours": false
}
```

**Order Types:**

| Type | Required Fields |
|------|-----------------|
| `market` | symbol, side, quantity |
| `limit` | symbol, side, quantity, limit_price |
| `stop` | symbol, side, quantity, stop_price |
| `stop_limit` | symbol, side, quantity, stop_price, limit_price |
| `trailing_stop` | symbol, side, quantity, trail_amount or trail_percent |

**Response:**
```json
{
  "order_id": "ord_123456789",
  "client_order_id": "my_strategy_001",
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 100,
  "filled_quantity": 0,
  "remaining_quantity": 100,
  "order_type": "limit",
  "limit_price": 185.50,
  "status": "pending",
  "time_in_force": "day",
  "created_at": "2026-01-15T14:30:00.123Z",
  "updated_at": "2026-01-15T14:30:00.123Z"
}
```

#### Cancel Order

```http
DELETE /v3/orders/{order_id}
```

#### Get Order Status

```http
GET /v3/orders/{order_id}
```

#### List Orders

```http
GET /v3/orders?status=open&limit=50
```

**Query Parameters:**

| Parameter | Description |
|-----------|-------------|
| `status` | all, open, closed, pending, filled, cancelled |
| `symbol` | Filter by symbol |
| `after` | Orders after timestamp |
| `before` | Orders before timestamp |
| `limit` | Max results (max: 500) |

#### Replace Order

```http
PATCH /v3/orders/{order_id}
```

```json
{
  "quantity": 200,
  "limit_price": 185.75
}
```

---

### Portfolio

#### Get Positions

```http
GET /v3/portfolio/positions
```

**Response:**
```json
{
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "side": "long",
      "avg_entry_price": 180.50,
      "current_price": 185.92,
      "market_value": 18592.00,
      "cost_basis": 18050.00,
      "unrealized_pnl": 542.00,
      "unrealized_pnl_percent": 3.00,
      "realized_pnl": 0,
      "last_updated": "2026-01-15T14:30:00.123Z"
    }
  ],
  "summary": {
    "total_market_value": 124567.89,
    "total_unrealized_pnl": 4523.00,
    "total_realized_pnl": 1234.00,
    "buying_power": 35432.11,
    "cash": 25000.00,
    "margin_used": 0.15
  }
}
```

#### Get Account Summary

```http
GET /v3/account/summary
```

---

### Options

#### Get Options Chain

```http
GET /v3/options/chain/{symbol}?expiration=2026-02-20
```

**Response:**
```json
{
  "symbol": "AAPL",
  "underlying_price": 185.92,
  "expirations": ["2026-02-20", "2026-03-20"],
  "strikes": [180, 185, 190, 195],
  "calls": [
    {
      "symbol": "AAPL260220C00180000",
      "strike": 180,
      "expiration": "2026-02-20",
      "last_price": 8.50,
      "bid": 8.40,
      "ask": 8.60,
      "volume": 1250,
      "open_interest": 45600,
      "greeks": {
        "delta": 0.72,
        "gamma": 0.04,
        "theta": -0.08,
        "vega": 0.25,
        "rho": 0.12,
        "implied_volatility": 0.28
      }
    }
  ],
  "puts": [...]
}
```

---

## WebSocket API

### Connection

```javascript
const ws = new WebSocket('wss://ws.dragonscope.io/v3', [], {
  headers: { 'Authorization': 'Bearer YOUR_TOKEN' }
});
```

### Authentication

```json
{
  "action": "auth",
  "token": "Bearer YOUR_TOKEN"
}
```

### Subscribe to Quotes

```json
{
  "action": "subscribe",
  "channels": ["quotes"],
  "symbols": ["AAPL", "MSFT", "GOOGL"]
}
```

### Subscribe to Order Book

```json
{
  "action": "subscribe",
  "channels": ["orderbook"],
  "symbols": ["AAPL"],
  "depth": 10
}
```

### Subscribe to Trades

```json
{
  "action": "subscribe",
  "channels": ["trades"],
  "symbols": ["AAPL"]
}
```

### Order Updates

```json
{
  "action": "subscribe",
  "channels": ["orders"]
}
```

### WebSocket Message Format

**Quote Update:**
```json
{
  "type": "quote",
  "symbol": "AAPL",
  "data": {
    "bid": 185.90,
    "ask": 185.95,
    "bid_size": 500,
    "ask_size": 300,
    "last_price": 185.92,
    "volume": 45230100,
    "timestamp": "2026-01-15T14:30:00.123Z"
  }
}
```

**Order Book Update:**
```json
{
  "type": "orderbook",
  "symbol": "AAPL",
  "data": {
    "bids": [[185.90, 500], [185.89, 300]],
    "asks": [[185.95, 300], [185.96, 800]],
    "timestamp": "2026-01-15T14:30:00.123Z"
  }
}
```

**Trade Update:**
```json
{
  "type": "trade",
  "symbol": "AAPL",
  "data": {
    "price": 185.92,
    "size": 100,
    "exchange": "NASDAQ",
    "condition": "@",
    "timestamp": "2026-01-15T14:30:00.123Z"
  }
}
```

**Order Update:**
```json
{
  "type": "order",
  "data": {
    "order_id": "ord_123456789",
    "status": "filled",
    "filled_quantity": 100,
    "remaining_quantity": 0,
    "avg_fill_price": 185.50,
    "timestamp": "2026-01-15T14:30:00.123Z"
  }
}
```

### Heartbeat

```json
// Client → Server (every 30 seconds)
{
  "action": "ping",
  "timestamp": 1705315200123
}

// Server → Client
{
  "type": "pong",
  "timestamp": 1705315200123,
  "latency_ms": 12
}
```

---

## Rate Limiting

### Limits by Tier

| Tier | REST Requests/Min | WebSocket Connections | Burst |
|------|-------------------|----------------------|-------|
| Free | 60 | 1 | 10 |
| Basic | 300 | 2 | 50 |
| Pro | 1,000 | 5 | 200 |
| Enterprise | 10,000 | 20 | 1,000 |
| Enterprise+ | Custom | Custom | Custom |

### Rate Limit Headers

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1705315200
X-RateLimit-Retry-After: 45
```

### Rate Limit Response

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Retry-After: 60

{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Retry after 60 seconds.",
  "retry_after": 60,
  "limit": 1000,
  "window": "1 minute"
}
```

### Best Practices

1. **Batch requests** when possible
2. **Use WebSocket** for real-time data instead of polling
3. **Implement exponential backoff** on 429 errors
4. **Cache responses** appropriately
5. **Respect Retry-After headers**

---

## Error Codes

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Success |
| 201 | Created | Resource created successfully |
| 204 | No Content | Success, no body returned |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict (e.g., duplicate) |
| 422 | Unprocessable | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Error | Server error |
| 503 | Service Unavailable | Temporary outage |

### API Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `invalid_symbol` | Symbol not found | Check symbol format |
| `market_closed` | Market not open | Check market hours |
| `insufficient_funds` | Not enough buying power | Reduce order size |
| `order_too_large` | Exceeds max order size | Split order |
| `invalid_order_type` | Unsupported order type | Check documentation |
| `duplicate_client_order_id` | ID already used | Use unique ID |
| `order_not_found` | Order ID doesn't exist | Verify order ID |
| `order_not_cancelable` | Order cannot be cancelled | Check order status |
| `price_out_of_range` | Price outside allowed range | Adjust price |
| `ws_auth_failed` | WebSocket auth failed | Reconnect with valid token |
| `subscription_limit` | Too many subscriptions | Reduce subscriptions |

### Error Response Format

```json
{
  "error": {
    "code": "insufficient_funds",
    "message": "Insufficient buying power for this order",
    "details": {
      "required": 18550.00,
      "available": 12000.00,
      "shortfall": 6550.00
    },
    "request_id": "req_abc123xyz",
    "documentation_url": "https://docs.dragonscope.io/errors/insufficient_funds"
  }
}
```

---

## Code Examples

### Python

```python
import requests
import websocket
import json
from typing import Dict, List

class DragonScopeClient:
    def __init__(self, api_key: str, sandbox: bool = False):
        self.api_key = api_key
        self.base_url = (
            "https://sandbox-api.dragonscope.io/v3" 
            if sandbox 
            else "https://api.dragonscope.io/v3"
        )
        self.ws_url = (
            "wss://sandbox-ws.dragonscope.io/v3"
            if sandbox
            else "wss://ws.dragonscope.io/v3"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
    
    def get_quote(self, symbol: str) -> Dict:
        """Get real-time quote for a symbol."""
        response = self.session.get(f"{self.base_url}/market/quotes/{symbol}")
        response.raise_for_status()
        return response.json()
    
    def get_quotes(self, symbols: List[str]) -> Dict:
        """Get quotes for multiple symbols."""
        symbol_str = ",".join(symbols)
        response = self.session.get(
            f"{self.base_url}/market/quotes",
            params={"symbols": symbol_str}
        )
        response.raise_for_status()
        return response.json()
    
    def get_historical_bars(
        self, 
        symbol: str, 
        timeframe: str = "1d",
        start: str = None,
        end: str = None,
        limit: int = 1000
    ) -> Dict:
        """Get historical OHLCV data."""
        params = {
            "timeframe": timeframe,
            "limit": limit
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
            
        response = self.session.get(
            f"{self.base_url}/market/history/{symbol}",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        limit_price: float = None,
        stop_price: float = None,
        time_in_force: str = "day",
        client_order_id: str = None
    ) -> Dict:
        """Place a new order."""
        order_data = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "time_in_force": time_in_force
        }
        
        if limit_price:
            order_data["limit_price"] = limit_price
        if stop_price:
            order_data["stop_price"] = stop_price
        if client_order_id:
            order_data["client_order_id"] = client_order_id
            
        response = self.session.post(
            f"{self.base_url}/orders",
            json=order_data
        )
        response.raise_for_status()
        return response.json()
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an existing order."""
        response = self.session.delete(f"{self.base_url}/orders/{order_id}")
        response.raise_for_status()
        return response.json()
    
    def get_positions(self) -> Dict:
        """Get current positions."""
        response = self.session.get(f"{self.base_url}/portfolio/positions")
        response.raise_for_status()
        return response.json()
    
    def stream_quotes(self, symbols: List[str], callback):
        """Stream real-time quotes via WebSocket."""
        def on_open(ws):
            # Authenticate
            ws.send(json.dumps({
                "action": "auth",
                "token": f"Bearer {self.api_key}"
            }))
            
            # Subscribe to quotes
            ws.send(json.dumps({
                "action": "subscribe",
                "channels": ["quotes"],
                "symbols": symbols
            }))
        
        def on_message(ws, message):
            data = json.loads(message)
            callback(data)
        
        def on_error(ws, error):
            print(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print("WebSocket connection closed")
        
        ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            header=[f"Authorization: Bearer {self.api_key}"]
        )
        
        ws.run_forever()


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = DragonScopeClient(
        api_key="ds_api_your_key_here",
        sandbox=True
    )
    
    # Get quote
    quote = client.get_quote("AAPL")
    print(f"AAPL: ${quote['last_price']} ({quote['change_percent']:+.2f}%)")
    
    # Get historical data
    bars = client.get_historical_bars("AAPL", timeframe="1d", limit=30)
    print(f"Retrieved {len(bars['bars'])} days of data")
    
    # Place order
    order = client.place_order(
        symbol="AAPL",
        side="buy",
        quantity=100,
        order_type="limit",
        limit_price=185.50
    )
    print(f"Order placed: {order['order_id']}")
    
    # Stream quotes
    def handle_quote(data):
        if data.get("type") == "quote":
            print(f"{data['symbol']}: ${data['data']['last_price']}")
    
    # client.stream_quotes(["AAPL", "MSFT", "GOOGL"], handle_quote)
```

### JavaScript/Node.js

```javascript
const axios = require('axios');
const WebSocket = require('ws');

class DragonScopeClient {
  constructor(apiKey, sandbox = false) {
    this.apiKey = apiKey;
    this.baseUrl = sandbox 
      ? 'https://sandbox-api.dragonscope.io/v3'
      : 'https://api.dragonscope.io/v3';
    this.wsUrl = sandbox
      ? 'wss://sandbox-ws.dragonscope.io/v3'
      : 'wss://ws.dragonscope.io/v3';
    
    this.client = axios.create({
      baseURL: this.baseUrl,
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    });
  }

  /**
   * Get real-time quote for a symbol
   */
  async getQuote(symbol) {
    const response = await this.client.get(`/market/quotes/${symbol}`);
    return response.data;
  }

  /**
   * Get quotes for multiple symbols
   */
  async getQuotes(symbols) {
    const response = await this.client.get('/market/quotes', {
      params: { symbols: symbols.join(',') }
    });
    return response.data;
  }

  /**
   * Get historical bars
   */
  async getHistoricalBars(symbol, options = {}) {
    const { timeframe = '1d', start, end, limit = 1000 } = options;
    const params = { timeframe, limit };
    if (start) params.start = start;
    if (end) params.end = end;
    
    const response = await this.client.get(
      `/market/history/${symbol}`,
      { params }
    );
    return response.data;
  }

  /**
   * Get order book (Level 2)
   */
  async getOrderBook(symbol, depth = 20) {
    const response = await this.client.get(
      `/market/orderbook/${symbol}`,
      { params: { depth } }
    );
    return response.data;
  }

  /**
   * Place a new order
   */
  async placeOrder(orderParams) {
    const {
      symbol,
      side,
      quantity,
      orderType = 'market',
      limitPrice,
      stopPrice,
      timeInForce = 'day',
      clientOrderId
    } = orderParams;

    const orderData = {
      symbol,
      side,
      quantity,
      order_type: orderType,
      time_in_force: timeInForce
    };

    if (limitPrice) orderData.limit_price = limitPrice;
    if (stopPrice) orderData.stop_price = stopPrice;
    if (clientOrderId) orderData.client_order_id = clientOrderId;

    const response = await this.client.post('/orders', orderData);
    return response.data;
  }

  /**
   * Cancel an order
   */
  async cancelOrder(orderId) {
    const response = await this.client.delete(`/orders/${orderId}`);
    return response.data;
  }

  /**
   * Get order status
   */
  async getOrder(orderId) {
    const response = await this.client.get(`/orders/${orderId}`);
    return response.data;
  }

  /**
   * List orders
   */
  async listOrders(options = {}) {
    const response = await this.client.get('/orders', { params: options });
    return response.data;
  }

  /**
   * Get positions
   */
  async getPositions() {
    const response = await this.client.get('/portfolio/positions');
    return response.data;
  }

  /**
   * Get options chain
   */
  async getOptionsChain(symbol, expiration) {
    const params = {};
    if (expiration) params.expiration = expiration;
    
    const response = await this.client.get(
      `/options/chain/${symbol}`,
      { params }
    );
    return response.data;
  }

  /**
   * Stream real-time data via WebSocket
   */
  stream(symbols, channels = ['quotes']) {
    const ws = new WebSocket(this.wsUrl, {
      headers: { 'Authorization': `Bearer ${this.apiKey}` }
    });

    const handlers = {
      onQuote: null,
      onTrade: null,
      onOrderBook: null,
      onOrder: null,
      onError: null,
      onConnect: null,
      onDisconnect: null
    };

    ws.on('open', () => {
      // Authenticate
      ws.send(JSON.stringify({
        action: 'auth',
        token: `Bearer ${this.apiKey}`
      }));

      // Subscribe to channels
      ws.send(JSON.stringify({
        action: 'subscribe',
        channels,
        symbols
      }));

      if (handlers.onConnect) handlers.onConnect();
    });

    ws.on('message', (data) => {
      const message = JSON.parse(data);
      
      switch (message.type) {
        case 'quote':
          if (handlers.onQuote) handlers.onQuote(message);
          break;
        case 'trade':
          if (handlers.onTrade) handlers.onTrade(message);
          break;
        case 'orderbook':
          if (handlers.onOrderBook) handlers.onOrderBook(message);
          break;
        case 'order':
          if (handlers.onOrder) handlers.onOrder(message);
          break;
        case 'error':
          if (handlers.onError) handlers.onError(message);
          break;
      }
    });

    ws.on('error', (error) => {
      if (handlers.onError) handlers.onError(error);
    });

    ws.on('close', () => {
      if (handlers.onDisconnect) handlers.onDisconnect();
    });

    // Return handler setters
    return {
      onQuote: (fn) => { handlers.onQuote = fn; return this; },
      onTrade: (fn) => { handlers.onTrade = fn; return this; },
      onOrderBook: (fn) => { handlers.onOrderBook = fn; return this; },
      onOrder: (fn) => { handlers.onOrder = fn; return this; },
      onError: (fn) => { handlers.onError = fn; return this; },
      onConnect: (fn) => { handlers.onConnect = fn; return this; },
      onDisconnect: (fn) => { handlers.onDisconnect = fn; return this; },
      close: () => ws.close()
    };
  }
}

// Example usage
async function main() {
  const client = new DragonScopeClient('ds_api_your_key_here', true);

  try {
    // Get quote
    const quote = await client.getQuote('AAPL');
    console.log(`AAPL: $${quote.last_price} (${quote.change_percent:+.2f}%)`);

    // Get historical data
    const bars = await client.getHistoricalBars('AAPL', {
      timeframe: '1d',
      limit: 30
    });
    console.log(`Retrieved ${bars.bars.length} days of data`);

    // Place order
    const order = await client.placeOrder({
      symbol: 'AAPL',
      side: 'buy',
      quantity: 100,
      orderType: 'limit',
      limitPrice: 185.50
    });
    console.log('Order placed:', order.order_id);

    // Get positions
    const positions = await client.getPositions();
    console.log('Positions:', positions.positions);

    // Stream quotes
    const stream = client.stream(['AAPL', 'MSFT', 'GOOGL'], ['quotes', 'trades']);
    
    stream
      .onQuote((data) => {
        console.log(`${data.symbol}: $${data.data.last_price}`);
      })
      .onTrade((data) => {
        console.log(`Trade: ${data.symbol} $${data.data.price} x ${data.data.size}`);
      })
      .onError((error) => {
        console.error('Stream error:', error);
      });

    // Keep running
    await new Promise(() => {});

  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
  }
}

main();
```

### Go

```go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"

	"github.com/gorilla/websocket"
)

// Client represents a DragonScope API client
type Client struct {
	APIKey  string
	BaseURL string
	WSURL   string
	HTTP    *http.Client
}

// Quote represents a market quote
type Quote struct {
	Symbol         string    `json:"symbol"`
	Name           string    `json:"name"`
	Exchange       string    `json:"exchange"`
	LastPrice      float64   `json:"last_price"`
	Bid            float64   `json:"bid"`
	Ask            float64   `json:"ask"`
	BidSize        int       `json:"bid_size"`
	AskSize        int       `json:"ask_size"`
	Volume         int64     `json:"volume"`
	Open           float64   `json:"open"`
	High           float64   `json:"high"`
	Low            float64   `json:"low"`
	Close          float64   `json:"close"`
	Change         float64   `json:"change"`
	ChangePercent  float64   `json:"change_percent"`
	Timestamp      time.Time `json:"timestamp"`
}

// Order represents a trading order
type Order struct {
	OrderID          string    `json:"order_id"`
	ClientOrderID    string    `json:"client_order_id"`
	Symbol           string    `json:"symbol"`
	Side             string    `json:"side"`
	Quantity         int       `json:"quantity"`
	FilledQuantity   int       `json:"filled_quantity"`
	RemainingQuantity int      `json:"remaining_quantity"`
	OrderType        string    `json:"order_type"`
	LimitPrice       float64   `json:"limit_price,omitempty"`
	StopPrice        float64   `json:"stop_price,omitempty"`
	Status           string    `json:"status"`
	TimeInForce      string    `json:"time_in_force"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
}

// Position represents a portfolio position
type Position struct {
	Symbol            string    `json:"symbol"`
	Quantity          int       `json:"quantity"`
	Side              string    `json:"side"`
	AvgEntryPrice     float64   `json:"avg_entry_price"`
	CurrentPrice      float64   `json:"current_price"`
	MarketValue       float64   `json:"market_value"`
	CostBasis         float64   `json:"cost_basis"`
	UnrealizedPnL     float64   `json:"unrealized_pnl"`
	UnrealizedPnLPercent float64 `json:"unrealized_pnl_percent"`
	RealizedPnL       float64   `json:"realized_pnl"`
	LastUpdated       time.Time `json:"last_updated"`
}

// NewClient creates a new DragonScope client
func NewClient(apiKey string, sandbox bool) *Client {
	baseURL := "https://api.dragonscope.io/v3"
	wsURL := "wss://ws.dragonscope.io/v3"
	
	if sandbox {
		baseURL = "https://sandbox-api.dragonscope.io/v3"
		wsURL = "wss://sandbox-ws.dragonscope.io/v3"
	}
	
	return &Client{
		APIKey:  apiKey,
		BaseURL: baseURL,
		WSURL:   wsURL,
		HTTP: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// GetQuote retrieves a quote for a symbol
func (c *Client) GetQuote(ctx context.Context, symbol string) (*Quote, error) {
	url := fmt.Sprintf("%s/market/quotes/%s", c.BaseURL, symbol)
	
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %s", resp.Status)
	}
	
	var quote Quote
	if err := json.NewDecoder(resp.Body).Decode(&quote); err != nil {
		return nil, err
	}
	
	return &quote, nil
}

// GetQuotes retrieves quotes for multiple symbols
func (c *Client) GetQuotes(ctx context.Context, symbols []string) (map[string]*Quote, error) {
	url := fmt.Sprintf("%s/market/quotes", c.BaseURL)
	
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	
	q := req.URL.Query()
	q.Add("symbols", joinStrings(symbols, ","))
	req.URL.RawQuery = q.Encode()
	
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var result map[string]*Quote
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	
	return result, nil
}

// GetHistoricalBars retrieves historical OHLCV data
func (c *Client) GetHistoricalBars(
	ctx context.Context,
	symbol string,
	timeframe string,
	start *time.Time,
	end *time.Time,
	limit int,
) (*HistoricalBarsResponse, error) {
	url := fmt.Sprintf("%s/market/history/%s", c.BaseURL, symbol)
	
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	
	q := req.URL.Query()
	q.Add("timeframe", timeframe)
	if start != nil {
		q.Add("start", start.Format(time.RFC3339))
	}
	if end != nil {
		q.Add("end", end.Format(time.RFC3339))
	}
	if limit > 0 {
		q.Add("limit", fmt.Sprintf("%d", limit))
	}
	req.URL.RawQuery = q.Encode()
	
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var result HistoricalBarsResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	
	return &result, nil
}

// HistoricalBarsResponse represents historical bar data
type HistoricalBarsResponse struct {
	Symbol    string `json:"symbol"`
	Timeframe string `json:"timeframe"`
	Bars      []Bar  `json:"bars"`
}

// Bar represents a single OHLCV bar
type Bar struct {
	Timestamp time.Time `json:"timestamp"`
	Open      float64   `json:"open"`
	High      float64   `json:"high"`
	Low       float64   `json:"low"`
	Close     float64   `json:"close"`
	Volume    int64     `json:"volume"`
	VWAP      float64   `json:"vwap"`
}

// PlaceOrder creates a new order
func (c *Client) PlaceOrder(ctx context.Context, orderReq *OrderRequest) (*Order, error) {
	url := fmt.Sprintf("%s/orders", c.BaseURL)
	
	body, err := json.Marshal(orderReq)
	if err != nil {
		return nil, err
	}
	
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("Content-Type", "application/json")
	
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("order failed: %s", resp.Status)
	}
	
	var order Order
	if err := json.NewDecoder(resp.Body).Decode(&order); err != nil {
		return nil, err
	}
	
	return &order, nil
}

// OrderRequest represents an order creation request
type OrderRequest struct {
	Symbol          string  `json:"symbol"`
	Side            string  `json:"side"`
	Quantity        int     `json:"quantity"`
	OrderType       string  `json:"order_type"`
	LimitPrice      float64 `json:"limit_price,omitempty"`
	StopPrice       float64 `json:"stop_price,omitempty"`
	TimeInForce     string  `json:"time_in_force"`
	ClientOrderID   string  `json:"client_order_id,omitempty"`
	ExtendedHours   bool    `json:"extended_hours,omitempty"`
}

// CancelOrder cancels an existing order
func (c *Client) CancelOrder(ctx context.Context, orderID string) error {
	url := fmt.Sprintf("%s/orders/%s", c.BaseURL, orderID)
	
	req, err := http.NewRequestWithContext(ctx, "DELETE", url, nil)
	if err != nil {
		return err
	}
	
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("cancel failed: %s", resp.Status)
	}
	
	return nil
}

// GetPositions retrieves current positions
func (c *Client) GetPositions(ctx context.Context) (*PositionsResponse, error) {
	url := fmt.Sprintf("%s/portfolio/positions", c.BaseURL)
	
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var result PositionsResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	
	return &result, nil
}

// PositionsResponse represents positions data
type PositionsResponse struct {
	Positions []Position `json:"positions"`
	Summary   struct {
		TotalMarketValue  float64 `json:"total_market_value"`
		TotalUnrealizedPnL float64 `json:"total_unrealized_pnl"`
		TotalRealizedPnL   float64 `json:"total_realized_pnl"`
		BuyingPower       float64 `json:"buying_power"`
		Cash              float64 `json:"cash"`
		MarginUsed        float64 `json:"margin_used"`
	} `json:"summary"`
}

// StreamQuotes connects to WebSocket and streams quotes
type StreamHandler struct {
	OnQuote     func(*WSQuoteMessage)
	OnTrade     func(*WSTradeMessage)
	OnOrderBook func(*WSOrderBookMessage)
	OnError     func(error)
	OnConnect   func()
	OnDisconnect func()
}

// WSQuoteMessage represents a WebSocket quote update
type WSQuoteMessage struct {
	Type   string `json:"type"`
	Symbol string `json:"symbol"`
	Data   struct {
		Bid       float64   `json:"bid"`
		Ask       float64   `json:"ask"`
		BidSize   int       `json:"bid_size"`
		AskSize   int       `json:"ask_size"`
		LastPrice float64   `json:"last_price"`
		Volume    int64     `json:"volume"`
		Timestamp time.Time `json:"timestamp"`
	} `json:"data"`
}

// WSTradeMessage represents a WebSocket trade update
type WSTradeMessage struct {
	Type   string `json:"type"`
	Symbol string `json:"symbol"`
	Data   struct {
		Price     float64   `json:"price"`
		Size      int       `json:"size"`
		Exchange  string    `json:"exchange"`
		Condition string    `json:"condition"`
		Timestamp time.Time `json:"timestamp"`
	} `json:"data"`
}

// WSOrderBookMessage represents a WebSocket order book update
type WSOrderBookMessage struct {
	Type   string      `json:"type"`
	Symbol string      `json:"symbol"`
	Data   OrderBookData `json:"data"`
}

type OrderBookData struct {
	Bids      [][2]float64 `json:"bids"`
	Asks      [][2]float64 `json:"asks"`
	Timestamp time.Time    `json:"timestamp"`
}

// StreamQuotes starts a WebSocket connection for streaming quotes
func (c *Client) StreamQuotes(symbols []string, handler *StreamHandler) error {
	u, err := url.Parse(c.WSURL)
	if err != nil {
		return err
	}
	
	headers := http.Header{}
	headers.Set("Authorization", "Bearer "+c.APIKey)
	
	conn, _, err := websocket.DefaultDialer.Dial(u.String(), headers)
	if err != nil {
		return err
	}
	defer conn.Close()
	
	if handler.OnConnect != nil {
		handler.OnConnect()
	}
	
	// Authenticate
	authMsg := map[string]string{
		"action": "auth",
		"token":  "Bearer " + c.APIKey,
	}
	if err := conn.WriteJSON(authMsg); err != nil {
		return err
	}
	
	// Subscribe
	subMsg := map[string]interface{}{
		"action":   "subscribe",
		"channels": []string{"quotes", "trades"},
		"symbols":  symbols,
	}
	if err := conn.WriteJSON(subMsg); err != nil {
		return err
	}
	
	// Read messages
	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			if handler.OnError != nil {
				handler.OnError(err)
			}
			if handler.OnDisconnect != nil {
				handler.OnDisconnect()
			}
			return err
		}
		
		// Determine message type and handle
		var baseMsg struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(message, &baseMsg); err != nil {
			continue
		}
		
		switch baseMsg.Type {
		case "quote":
			if handler.OnQuote != nil {
				var msg WSQuoteMessage
				if err := json.Unmarshal(message, &msg); err == nil {
					handler.OnQuote(&msg)
				}
			}
		case "trade":
			if handler.OnTrade != nil {
				var msg WSTradeMessage
				if err := json.Unmarshal(message, &msg); err == nil {
					handler.OnTrade(&msg)
				}
			}
		case "orderbook":
			if handler.OnOrderBook != nil {
				var msg WSOrderBookMessage
				if err := json.Unmarshal(message, &msg); err == nil {
					handler.OnOrderBook(&msg)
				}
			}
		}
	}
}

// Helper function to join strings
func joinStrings(strs []string, sep string) string {
	if len(strs) == 0 {
		return ""
	}
	result := strs[0]
	for i := 1; i < len(strs); i++ {
		result += sep + strs[i]
	}
	return result
}

// Example usage
func main() {
	client := NewClient("ds_api_your_key_here", true)
	ctx := context.Background()
	
	// Get quote
	quote, err := client.GetQuote(ctx, "AAPL")
	if err != nil {
		fmt.Printf("Error getting quote: %v\n", err)
		return
	}
	fmt.Printf("AAPL: $%.2f (%.2f%%)\n", quote.LastPrice, quote.ChangePercent)
	
	// Place order
	order, err := client.PlaceOrder(ctx, &OrderRequest{
		Symbol:      "AAPL",
		Side:        "buy",
		Quantity:    100,
		OrderType:   "limit",
		LimitPrice:  185.50,
		TimeInForce: "day",
	})
	if err != nil {
		fmt.Printf("Error placing order: %v\n", err)
		return
	}
	fmt.Printf("Order placed: %s\n", order.OrderID)
	
	// Stream quotes
	handler := &StreamHandler{
		OnQuote: func(msg *WSQuoteMessage) {
			fmt.Printf("%s: $%.2f\n", msg.Symbol, msg.Data.LastPrice)
		},
		OnConnect: func() {
			fmt.Println("WebSocket connected")
		},
		OnError: func(err error) {
			fmt.Printf("WebSocket error: %v\n", err)
		},
	}
	
	if err := client.StreamQuotes([]string{"AAPL", "MSFT"}, handler); err != nil {
		fmt.Printf("Stream error: %v\n", err)
	}
}
```

---

## SDKs and Libraries

| Language | Package | Installation |
|----------|---------|--------------|
| Python | `dragonscope-py` | `pip install dragonscope-py` |
| JavaScript | `@dragonscope/sdk` | `npm install @dragonscope/sdk` |
| Go | `github.com/dragonscope/go-sdk` | `go get github.com/dragonscope/go-sdk` |
| Java | `io.dragonscope:sdk` | Maven/Gradle |
| C# | `DragonScope.SDK` | `dotnet add package DragonScope.SDK` |
| Rust | `dragonscope` | `cargo add dragonscope` |

---

## Changelog

### v3.2.0 (2026-01-15)
- Added options chain endpoint
- Enhanced WebSocket with order updates
- New Webhook alert delivery

### v3.1.0 (2025-11-20)
- Added portfolio analytics endpoints
- Improved rate limit headers
- New batch order endpoint

### v3.0.0 (2025-09-01)
- Initial v3 release
- REST API redesign
- WebSocket protocol v3

---

<p align="center">
  Questions? Contact <a href="mailto:api@dragonscope.io">api@dragonscope.io</a>
</p>
