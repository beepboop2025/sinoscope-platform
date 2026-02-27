# DragonScope Enterprise Integration Hub

## Overview

The Integration Hub connects DragonScope Enterprise to external financial data providers, trading platforms, collaboration tools, and office applications. It provides a unified interface for data ingestion, real-time streaming, and bidirectional communication with enterprise systems.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Integration Hub Layer                            │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│  Financial   │  Trading     │  Office      │  Messaging   │  Custom     │
│  Data        │  Platforms   │  Suite       │  Platforms   │  Connectors │
├──────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ • Bloomberg  │ • TradingView│ • Excel      │ • Slack      │ • Webhooks  │
│ • Refinitiv  │ • Interactive│   Add-in     │ • Teams      │ • REST API  │
│   Eikon      │   Brokers    │ • Google     │ • Discord    │ • GraphQL   │
│ • FactSet    │ • MetaTrader │   Sheets     │ • Telegram   │ • FIX       │
│ • S&P Global │ • Alpaca     │ • Power BI   │              │ • gRPC      │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Unified Data & Event Bus                           │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     DragonScope Core Services                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Supported Systems

### Financial Data Providers

#### Bloomberg Terminal
- **Protocol**: Bloomberg API (blpapi)
- **Capabilities**: 
  - Historical data requests
  - Real-time market data subscriptions
  - Reference data lookups
  - Intraday tick data
  - Earnings estimates
  - Fundamental data
- **Authentication**: Bloomberg SAPI/EMRS
- **Module**: `bloomberg.py`

#### Refinitiv Eikon
- **Protocol**: Eikon Data API, RDP
- **Capabilities**:
  - Time-series data
  - Real-time streaming
  - Symbology conversion
  - News sentiment
- **Authentication**: App Key + OAuth 2.0
- **Module**: `refinitiv.py`

### Office Suite Integration

#### Microsoft Excel
- **Architecture**: COM Add-in + WebSocket Server
- **Capabilities**:
  - Real-Time Data (RTD) functions
  - User Defined Functions (UDFs)
  - Streaming data to cells
  - Custom ribbon interface
- **Functions**: `=DS_PRICE()`, `=DS_HISTORY()`, `=DS_SCREEN()`
- **Module**: `excel.py`

#### Google Sheets
- **Protocol**: Google Apps Script + Web API
- **Capabilities**:
  - Custom functions
  - Real-time updates via triggers
  - Data import tools

### Trading Platforms

#### TradingView
- **Protocol**: Webhooks + Pine Script integration
- **Capabilities**:
  - Strategy alerts to orders
  - Custom indicators
  - Chart markup sharing

#### Interactive Brokers
- **Protocol**: TWS API / IB Gateway
- **Capabilities**:
  - Order routing
  - Portfolio sync
  - Market data

### Messaging Platforms

#### Slack
- **Protocol**: Web API + Socket Mode
- **Capabilities**:
  - Alert notifications
  - Interactive commands
  - Dashboard sharing
  - Approval workflows

#### Microsoft Teams
- **Protocol**: Graph API + Bot Framework
- **Capabilities**:
  - Adaptive card alerts
  - Teams channel integration
  - Meeting integration

## Webhook System

### Event Types

| Event Category | Event Types | Description |
|----------------|-------------|-------------|
| Market Data | `price.update`, `volume.spike`, `halt.triggered` | Real-time market events |
| Analytics | `alert.triggered`, `signal.generated`, `pattern.detected` | AI/ML generated insights |
| Portfolio | `position.opened`, `position.closed`, `margin.call` | Portfolio changes |
| System | `user.login`, `api.quota.exceeded`, `error.reported` | System events |

### Webhook Payload Structure

```json
{
  "event_id": "evt_1234567890",
  "event_type": "alert.triggered",
  "timestamp": "2024-01-15T09:30:00.000Z",
  "webhook_id": "whk_9876543210",
  "data": {
    "alert_id": "alt_abc123",
    "symbol": "AAPL",
    "condition": "price_above",
    "threshold": 185.50,
    "current_value": 186.25,
    "message": "AAPL crossed above $185.50"
  }
}
```

### Security Features
- HMAC-SHA256 payload signing
- IP allowlisting
- TLS 1.3 required
- Replay attack prevention (timestamp validation)
- Automatic retry with exponential backoff

## API Management

### API Key Tiers

| Tier | Rate Limit | Quota (Monthly) | Features |
|------|------------|-----------------|----------|
| Developer | 100 req/min | 10,000 | Read-only, delayed data |
| Professional | 1,000 req/min | 100,000 | Real-time, WebSockets |
| Enterprise | 10,000 req/min | Unlimited | Full access, SLA, dedicated support |

### Authentication Methods
- API Key (header: `X-DS-API-Key`)
- OAuth 2.0 (OIDC compliant)
- mTLS (Enterprise tier)
- JWT tokens

### Endpoints

#### Data Endpoints
```
GET    /api/v1/market/quote/{symbol}
GET    /api/v1/market/history/{symbol}
GET    /api/v1/market/chain/{symbol}
POST   /api/v1/market/screener
```

#### WebSocket Endpoints
```
wss://api.dragonscope.com/v1/stream/market
wss://api.dragonscope.com/v1/stream/portfolio
wss://api.dragonscope.com/v1/stream/alerts
```

#### Management Endpoints
```
GET    /api/v1/account/usage
GET    /api/v1/account/quota
POST   /api/v1/webhooks
GET    /api/v1/webhooks/{id}
DELETE /api/v1/webhooks/{id}
```

## Configuration

### Environment Variables

```bash
# Bloomberg
BLOOMBERG_SAPI_SERVER=localhost
BLOOMBERG_SAPI_PORT=8194
BLOOMBERG_AUTH_KEY=/path/to/auth/key

# Refinitiv
REFINITIV_APP_KEY=your_app_key
REFINITIV_USERNAME=user@company.com
REFINITIV_PASSWORD=secret

# Excel Add-in
EXCEL_WEBSOCKET_PORT=9001
EXCEL_ENABLE_RTD=true
EXCEL_ENABLE_UDF=true

# Webhooks
WEBHOOK_SECRET=your_webhook_signing_secret
WEBHOOK_MAX_RETRIES=5
WEBHOOK_RETRY_BASE_MS=1000

# API Management
API_RATE_LIMIT_DEFAULT=100
API_KEY_ENCRYPTION_KEY=/path/to/encryption.key
```

### YAML Configuration Schema

```yaml
integrations:
  bloomberg:
    enabled: true
    server:
      host: "localhost"
      port: 8194
    subscriptions:
      max_concurrent: 100
      fields:
        - PX_LAST
        - PX_BID
        - PX_ASK
        - VOLUME
    
  excel:
    enabled: true
    websocket:
      host: "0.0.0.0"
      port: 9001
    functions:
      - name: "DS_PRICE"
        category: "DragonScope"
        description: "Get real-time price"
      - name: "DS_HISTORY"
        category: "DragonScope"
        description: "Get historical data"
  
  webhooks:
    enabled: true
    delivery:
      timeout_seconds: 30
      max_retries: 5
      retry_backoff: exponential
    security:
      require_signature: true
      allowed_ips: []
  
  slack:
    enabled: true
    bot_token: "${SLACK_BOT_TOKEN}"
    signing_secret: "${SLACK_SIGNING_SECRET}"
    channels:
      alerts: "#trading-alerts"
      reports: "#daily-reports"
```

## Example Integrations

### Python SDK Usage

```python
from dragonscope.enterprise.integrations import BloombergClient, ExcelServer

# Bloomberg Example
with BloombergClient() as bbg:
    # Historical data
    hist = bbg.get_historical_data(
        securities=["AAPL US Equity", "MSFT US Equity"],
        fields=["PX_LAST", "VOLUME"],
        start_date="2024-01-01",
        end_date="2024-01-31"
    )
    
    # Real-time subscription
    def on_price_update(ticker, field, value):
        print(f"{ticker}: {field} = {value}")
    
    subscription = bbg.subscribe(
        securities=["AAPL US Equity"],
        fields=["PX_LAST", "BID", "ASK"],
        callback=on_price_update
    )

# Excel WebSocket Server
excel_server = ExcelServer(port=9001)
excel_server.start()

# Push data to Excel
excel_server.update_cell("sheet1!A1", "AAPL")
excel_server.update_cell("sheet1!B1", 185.50)
```

### Webhook Registration

```python
from dragonscope.enterprise.integrations import WebhookManager

webhook_mgr = WebhookManager()

# Register webhook
webhook = webhook_mgr.create_webhook(
    url="https://your-app.com/webhooks/dragonscope",
    events=["alert.triggered", "price.update"],
    secret="your_webhook_secret",
    metadata={"environment": "production"}
)

# Test delivery
webhook_mgr.test_delivery(webhook.id)

# View delivery logs
logs = webhook_mgr.get_delivery_logs(webhook.id, limit=100)
```

### API Client Example

```python
import requests

# REST API
headers = {"X-DS-API-Key": "your_api_key"}
response = requests.get(
    "https://api.dragonscope.com/v1/market/quote/AAPL",
    headers=headers
)
quote = response.json()

# WebSocket Streaming
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"Price update: {data}")

ws = websocket.WebSocketApp(
    "wss://api.dragonscope.com/v1/stream/market",
    header=["X-DS-API-Key: your_api_key"],
    on_message=on_message
)
ws.run_forever()
```

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/integrations/

# Integration tests (requires Bloomberg Terminal)
pytest tests/integration/bloomberg/ -v

# Load tests
locust -f tests/load/locustfile.py
```

### Building Excel Add-in

```bash
cd excel-addin/
npm install
npm run build
# Output: DragonScopeExcel.xll
```

## Support

- **Enterprise Support**: enterprise@dragonscope.com
- **Developer Docs**: https://docs.dragonscope.com/integrations
- **Status Page**: https://status.dragonscope.com
