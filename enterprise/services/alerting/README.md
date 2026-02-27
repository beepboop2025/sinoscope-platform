# DragonScope Enterprise Alerting System

A comprehensive multi-channel alerting platform designed for financial markets and enterprise monitoring. The system provides real-time alert detection, intelligent routing, and multi-channel delivery with sophisticated escalation policies.

## Features

### Multi-Channel Alerting
- **WebSocket**: Real-time bidirectional communication for live dashboard updates
- **Email (SMTP)**: Rich HTML notifications with attachment support
- **SMS (Twilio)**: Critical alert delivery via text messaging
- **Slack**: Team collaboration with channel-specific routing
- **PagerDuty**: Incident management integration for high-severity alerts
- **Webhook**: Custom HTTP callbacks for third-party integrations

### Alert Rule Engine
- **Threshold Rules**: Simple value-based triggers (above/below/equal)
- **Anomaly Rules**: Statistical outlier detection with configurable sensitivity
- **Pattern Rules**: Sequence and trend detection
- **Composite Rules**: Multi-condition logic with AND, OR, NOT operators
- **Time-Based Conditions**: Market hours awareness, trading day validation
- **Rule Versioning**: Full audit trail with version history

### Notification Routing
- Severity-based channel selection
- User preference management
- Group and team-based routing
- Conditional routing based on alert metadata
- Priority queuing for critical alerts

### Escalation Policies
- Time-based escalation ladders
- Severity-driven routing paths
- On-call rotation integration
- Automatic acknowledgment tracking
- Escalation timeout management

### Alert Suppression & Grouping
- Duplicate detection and suppression
- Time-window grouping
- Correlation-based aggregation
- Maintenance mode support
- Alert silencing with expiration

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Data Sources  │────▶│ Rule Engine  │────▶│  Alert Queue    │
│  (Market Data)  │     │  (Detection) │     │  (Priority)     │
└─────────────────┘     └──────────────┘     └─────────────────┘
                                                      │
                       ┌──────────────────────────────┼──────────────┐
                       ▼                              ▼              ▼
              ┌─────────────────┐          ┌─────────────────┐  ┌──────────┐
              │   Notification  │          │   Escalation    │  │ History  │
              │    Service      │          │    Engine       │  │  Store   │
              └─────────────────┘          └─────────────────┘  └──────────┘
                       │
        ┌──────────────┼──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │WebSocket│   │  Email  │   │   SMS   │   │  Slack  │   │PagerDuty│
   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```env
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@dragonscope.io
SMTP_PASSWORD=your_app_password

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1234567890

# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token

# PagerDuty Configuration
PAGERDUTY_API_KEY=your_api_key
PAGERDUTY_SERVICE_KEY=your_service_key

# WebSocket Configuration
WS_HOST=0.0.0.0
WS_PORT=8080

# Database
DATABASE_URL=postgresql://user:pass@localhost/alerting
```

### Running the Service

```bash
# Start the API server
uvicorn api:app --host 0.0.0.0 --port 8000

# Start the rule engine processor
python -m alerting.rule_engine --config config.yaml

# Start the notification worker
python -m alerting.notifications --worker
```

## Alert Templates

### Price Alert
```json
{
  "template_id": "price_threshold",
  "name": "Price Threshold Alert",
  "description": "Triggered when price crosses above or below threshold",
  "variables": ["symbol", "price", "threshold", "direction", "timestamp"],
  "severity": "high"
}
```

### Volume Spike
```json
{
  "template_id": "volume_spike",
  "name": "Volume Spike Detection",
  "description": "Triggered when volume exceeds historical average by threshold",
  "variables": ["symbol", "current_volume", "avg_volume", "multiplier", "timestamp"],
  "severity": "medium"
}
```

### Technical Breakout
```json
{
  "template_id": "technical_breakout",
  "name": "Technical Pattern Breakout",
  "description": "Triggered on technical pattern completion",
  "variables": ["symbol", "pattern", "direction", "confidence", "price", "timestamp"],
  "severity": "high"
}
```

### News Alert
```json
{
  "template_id": "news_alert",
  "name": "Breaking News Alert",
  "description": "Triggered on high-impact news events",
  "variables": ["symbol", "headline", "source", "sentiment", "timestamp"],
  "severity": "critical"
}
```

### Risk Limit
```json
{
  "template_id": "risk_limit",
  "name": "Risk Threshold Breach",
  "description": "Triggered when risk metrics exceed limits",
  "variables": ["portfolio", "metric", "current_value", "limit", "utilization_pct", "timestamp"],
  "severity": "critical"
}
```

## API Endpoints

### Alert Management
- `GET /api/v1/alerts` - List alerts with filtering
- `POST /api/v1/alerts` - Create new alert
- `GET /api/v1/alerts/{id}` - Get alert details
- `PUT /api/v1/alerts/{id}` - Update alert
- `DELETE /api/v1/alerts/{id}` - Delete alert
- `POST /api/v1/alerts/{id}/acknowledge` - Acknowledge alert
- `POST /api/v1/alerts/{id}/resolve` - Resolve alert

### Rules
- `GET /api/v1/rules` - List alert rules
- `POST /api/v1/rules` - Create new rule
- `GET /api/v1/rules/{id}` - Get rule details
- `PUT /api/v1/rules/{id}` - Update rule
- `DELETE /api/v1/rules/{id}` - Delete rule
- `POST /api/v1/rules/{id}/enable` - Enable rule
- `POST /api/v1/rules/{id}/disable` - Disable rule
- `GET /api/v1/rules/{id}/versions` - Get rule version history

### Real-time
- `WS /ws/alerts` - WebSocket stream for real-time alerts
- `WS /ws/alerts?filter=severity:critical` - Filtered stream

### Analytics
- `GET /api/v1/analytics/alert-history` - Alert history with aggregation
- `GET /api/v1/analytics/metrics` - Alert metrics and statistics
- `GET /api/v1/analytics/top-alerts` - Most frequent alerts

## Rule Types

### Threshold Rule
```python
{
  "type": "threshold",
  "condition": {
    "metric": "price",
    "operator": "gt",
    "value": 150.00,
    "symbol": "AAPL"
  },
  "time_restriction": {
    "market_hours_only": true,
    "timezone": "America/New_York"
  }
}
```

### Anomaly Rule
```python
{
  "type": "anomaly",
  "condition": {
    "metric": "volume",
    "method": "zscore",
    "threshold": 3.0,
    "window": "30d",
    "symbol": "TSLA"
  }
}
```

### Pattern Rule
```python
{
  "type": "pattern",
  "condition": {
    "pattern": "head_and_shoulders",
    "timeframe": "1d",
    "confirmation": "close",
    "symbol": "SPY"
  }
}
```

### Composite Rule
```python
{
  "type": "composite",
  "logic": "AND",
  "rules": [
    {"type": "threshold", "condition": {"metric": "rsi", "operator": "gt", "value": 70}},
    {"type": "threshold", "condition": {"metric": "volume", "operator": "gt", "value": 1000000}}
  ]
}
```

## Escalation Policies

### Basic Escalation
```python
{
  "policy_id": "basic_escalation",
  "levels": [
    {
      "level": 1,
      "channels": ["websocket", "email"],
      "timeout_minutes": 15,
      "recipients": ["user@example.com"]
    },
    {
      "level": 2,
      "channels": ["sms", "slack"],
      "timeout_minutes": 30,
      "recipients": ["+1234567890", "#alerts"]
    },
    {
      "level": 3,
      "channels": ["pagerduty", "phone"],
      "timeout_minutes": 60,
      "recipients": ["on-call-team"]
    }
  ]
}
```

## License

Copyright © 2024 DragonScope. All rights reserved.
