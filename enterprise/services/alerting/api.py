"""
DragonScope Enterprise Alerting - REST API

FastAPI endpoints for alert management, WebSocket streaming,
and analytics with full CRUD operations.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from rule_engine import (
    RuleEngine, AlertRule, RuleType, RuleCondition, ThresholdCondition,
    AnomalyCondition, PatternCondition, CompositeCondition, Operator,
    AnomalyMethod, PatternType, LogicOperator, Severity, AlertEvent,
    TimeRestriction, MarketHours
)
from notifications import (
    NotificationService, NotificationChannel, ChannelType,
    create_email_channel, create_sms_channel, create_slack_channel,
    create_pagerduty_channel, create_webhook_channel,
    ALERT_TEMPLATES
)
from escalation import (
    EscalationEngine, EscalationPolicy, EscalationLevel,
    OnCallRotation, OnCallUser, SeverityRouting, Severity
)

# Initialize services
rule_engine = RuleEngine()
notification_service = NotificationService()
escalation_engine = EscalationEngine()

# WebSocket connection manager
class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_subscriptions: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, room: str = "alerts"):
        """Accept and store WebSocket connection."""
        await websocket.accept()
        
        if room not in self.active_connections:
            self.active_connections[room] = []
        
        self.active_connections[room].append(websocket)
        self.user_subscriptions[websocket] = {"room": room, "filters": {}}
    
    def disconnect(self, websocket: WebSocket, room: str = "alerts"):
        """Remove WebSocket connection."""
        if room in self.active_connections:
            self.active_connections[room] = [
                ws for ws in self.active_connections[room] if ws != websocket
            ]
        if websocket in self.user_subscriptions:
            del self.user_subscriptions[websocket]
    
    async def broadcast(self, message: Dict[str, Any], room: str = "alerts"):
        """Broadcast message to all connections in a room."""
        if room not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[room]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, room)
    
    def set_filters(self, websocket: WebSocket, filters: Dict[str, Any]):
        """Set filters for a connection."""
        if websocket in self.user_subscriptions:
            self.user_subscriptions[websocket]["filters"] = filters
    
    def should_receive(self, websocket: WebSocket, alert: Dict[str, Any]) -> bool:
        """Check if alert passes filters for this connection."""
        if websocket not in self.user_subscriptions:
            return True
        
        filters = self.user_subscriptions[websocket].get("filters", {})
        
        # Check severity filter
        if "severity" in filters:
            if alert.get("severity") != filters["severity"]:
                return False
        
        # Check symbol filter
        if "symbol" in filters:
            if alert.get("symbol") != filters["symbol"]:
                return False
        
        # Check rule_type filter
        if "rule_type" in filters:
            if alert.get("rule_type") != filters["rule_type"]:
                return False
        
        return True

manager = ConnectionManager()

# Pydantic models for API

class ThresholdConditionCreate(BaseModel):
    metric: str
    operator: Operator
    value: float
    symbol: Optional[str] = None

class AnomalyConditionCreate(BaseModel):
    metric: str
    method: AnomalyMethod
    threshold: float
    window: str = "30d"
    symbol: Optional[str] = None

class PatternConditionCreate(BaseModel):
    pattern: PatternType
    timeframe: str = "1d"
    confirmation: str = "close"
    symbol: Optional[str] = None

class RuleCreate(BaseModel):
    name: str
    description: str
    rule_type: RuleType
    condition: Dict[str, Any]
    severity: Severity = Severity.MEDIUM
    symbol: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    cooldown_minutes: int = 5
    market_hours_only: bool = False
    extended_hours: bool = False

class RuleResponse(BaseModel):
    rule_id: str
    name: str
    description: str
    rule_type: str
    severity: str
    symbol: Optional[str]
    tags: List[str]
    enabled: bool
    cooldown_minutes: int
    version: int
    created_at: str
    updated_at: str
    trigger_count: int

class AlertResponse(BaseModel):
    alert_id: str
    rule_id: str
    rule_name: str
    rule_type: str
    severity: str
    symbol: Optional[str]
    message: str
    timestamp: str
    data: Dict[str, Any]

class ChannelCreate(BaseModel):
    name: str
    channel_type: ChannelType
    config: Dict[str, Any]
    rate_limit_per_minute: int = 60

class ChannelResponse(BaseModel):
    channel_id: str
    name: str
    channel_type: str
    enabled: bool
    rate_limit_per_minute: int
    sent_count: int

class EscalationLevelCreate(BaseModel):
    level: int
    name: str
    timeout_minutes: int
    channels: List[str]
    recipients: List[str]
    require_ack: bool = True

class EscalationPolicyCreate(BaseModel):
    name: str
    description: str
    levels: List[EscalationLevelCreate]
    rotation_id: Optional[str] = None

class EscalationPolicyResponse(BaseModel):
    policy_id: str
    name: str
    description: str
    levels: int
    enabled: bool
    created_at: str

class EscalationResponse(BaseModel):
    escalation_id: str
    policy_id: str
    alert_id: str
    severity: str
    status: str
    current_level: int
    started_at: str
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None

class AlertHistoryFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    severity: Optional[Severity] = None
    symbol: Optional[str] = None
    rule_type: Optional[RuleType] = None

class AlertMetrics(BaseModel):
    total_alerts: int
    by_severity: Dict[str, int]
    by_rule_type: Dict[str, int]
    by_symbol: Dict[str, int]
    acknowledgment_rate: float
    avg_resolution_time_minutes: Optional[float]

# Alert history storage (in production, use database)
alert_history: List[Dict[str, Any]] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    asyncio.create_task(escalation_engine.run_escalation_checker())
    yield
    # Shutdown
    escalation_engine.running = False

app = FastAPI(
    title="DragonScope Enterprise Alerting API",
    description="Multi-channel alerting system for financial markets",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ALERT RULES API ====================

@app.post("/api/v1/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(rule: RuleCreate):
    """Create a new alert rule."""
    # Convert condition based on rule type
    if rule.rule_type == RuleType.THRESHOLD:
        condition = ThresholdCondition(
            metric=rule.condition["metric"],
            operator=Operator(rule.condition["operator"]),
            value=rule.condition["value"],
            symbol=rule.condition.get("symbol") or rule.symbol
        )
    elif rule.rule_type == RuleType.ANOMALY:
        condition = AnomalyCondition(
            metric=rule.condition["metric"],
            method=AnomalyMethod(rule.condition["method"]),
            threshold=rule.condition["threshold"],
            window=rule.condition.get("window", "30d"),
            symbol=rule.condition.get("symbol") or rule.symbol
        )
    elif rule.rule_type == RuleType.PATTERN:
        condition = PatternCondition(
            pattern=PatternType(rule.condition["pattern"]),
            timeframe=rule.condition.get("timeframe", "1d"),
            confirmation=rule.condition.get("confirmation", "close"),
            symbol=rule.condition.get("symbol") or rule.symbol
        )
    elif rule.rule_type == RuleType.COMPOSITE:
        condition = CompositeCondition(
            operator=LogicOperator(rule.condition["operator"]),
            conditions=[]
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid rule type")
    
    time_restriction = None
    if rule.market_hours_only or rule.extended_hours:
        time_restriction = TimeRestriction(
            market_hours_only=rule.market_hours_only,
            extended_hours=rule.extended_hours
        )
    
    new_rule = rule_engine.add_rule(
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        condition=condition,
        severity=rule.severity,
        symbol=rule.symbol,
        tags=rule.tags,
        cooldown_minutes=rule.cooldown_minutes,
        time_restriction=time_restriction
    )
    
    return RuleResponse(**new_rule.to_dict())

@app.get("/api/v1/rules", response_model=List[RuleResponse])
async def list_rules(
    symbol: Optional[str] = None,
    severity: Optional[Severity] = None,
    rule_type: Optional[RuleType] = None,
    enabled_only: bool = False
):
    """List alert rules with optional filtering."""
    rules = rule_engine.get_rules(
        symbol=symbol,
        rule_type=rule_type,
        severity=severity,
        enabled_only=enabled_only
    )
    return [RuleResponse(**rule.to_dict()) for rule in rules]

@app.get("/api/v1/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str):
    """Get a specific rule by ID."""
    try:
        uuid_obj = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    rule = rule_engine.get_rule(uuid_obj)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return RuleResponse(**rule.to_dict())

@app.put("/api/v1/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: str, updates: Dict[str, Any]):
    """Update an existing rule."""
    try:
        uuid_obj = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    rule = rule_engine.update_rule(uuid_obj, updates)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return RuleResponse(**rule.to_dict())

@app.delete("/api/v1/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: str):
    """Delete a rule."""
    try:
        uuid_obj = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    if not rule_engine.delete_rule(uuid_obj):
        raise HTTPException(status_code=404, detail="Rule not found")

@app.post("/api/v1/rules/{rule_id}/enable")
async def enable_rule(rule_id: str):
    """Enable a rule."""
    try:
        uuid_obj = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    if not rule_engine.enable_rule(uuid_obj):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "enabled"}

@app.post("/api/v1/rules/{rule_id}/disable")
async def disable_rule(rule_id: str):
    """Disable a rule."""
    try:
        uuid_obj = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    if not rule_engine.disable_rule(uuid_obj):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "disabled"}

@app.get("/api/v1/rules/{rule_id}/versions")
async def get_rule_versions(rule_id: str):
    """Get version history for a rule."""
    try:
        uuid_obj = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    versions = rule_engine.get_rule_versions(uuid_obj)
    return [
        {
            "version_id": str(v.version_id),
            "version_number": v.version_number,
            "created_at": v.created_at.isoformat(),
            "created_by": v.created_by,
            "changes": v.changes
        }
        for v in versions
    ]

# ==================== ALERTS API ====================

@app.get("/api/v1/alerts", response_model=List[AlertResponse])
async def list_alerts(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    severity: Optional[Severity] = None,
    symbol: Optional[str] = None,
    limit: int = Query(50, ge=1, le=1000)
):
    """List alerts from history with filtering."""
    alerts = alert_history
    
    if start_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) >= start_date]
    if end_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) <= end_date]
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity.value]
    if symbol:
        alerts = [a for a in alerts if a.get("symbol") == symbol]
    
    alerts = sorted(alerts, key=lambda x: x["timestamp"], reverse=True)[:limit]
    return [AlertResponse(**a) for a in alerts]

@app.post("/api/v1/alerts/evaluate")
async def evaluate_data(data: Dict[str, Any]):
    """Manually trigger rule evaluation with provided data."""
    alerts = rule_engine.evaluate_all(data)
    
    for alert in alerts:
        alert_dict = alert.to_dict()
        alert_history.append(alert_dict)
        await manager.broadcast(alert_dict)
    
    return {
        "alerts_triggered": len(alerts),
        "alerts": [a.to_dict() for a in alerts]
    }

@app.get("/api/v1/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """Get a specific alert by ID."""
    for alert in alert_history:
        if alert["alert_id"] == alert_id:
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user_id: str, message: Optional[str] = None):
    """Acknowledge an alert."""
    for esc in escalation_engine.instances.values():
        if str(esc.alert_id) == alert_id:
            ack = escalation_engine.acknowledge(
                escalation_id=esc.escalation_id,
                user_id=user_id,
                user_name=user_id,
                message=message
            )
            if ack:
                return {"status": "acknowledged", "acknowledgment_id": str(ack.acknowledgment_id)}
    
    raise HTTPException(status_code=404, detail="Alert not found or already resolved")

@app.post("/api/v1/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, user_id: str, notes: Optional[str] = None):
    """Resolve an alert."""
    for esc in escalation_engine.instances.values():
        if str(esc.alert_id) == alert_id:
            if escalation_engine.resolve(esc.escalation_id, user_id, notes):
                return {"status": "resolved"}
    
    raise HTTPException(status_code=404, detail="Alert not found")

# ==================== NOTIFICATION CHANNELS API ====================

@app.post("/api/v1/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(channel: ChannelCreate):
    """Create a notification channel."""
    new_channel = NotificationChannel(
        channel_id=uuid4(),
        channel_type=channel.channel_type,
        name=channel.name,
        config=channel.config,
        rate_limit_per_minute=channel.rate_limit_per_minute
    )
    
    channel_id = notification_service.add_channel(new_channel)
    
    return ChannelResponse(
        channel_id=str(channel_id),
        name=new_channel.name,
        channel_type=new_channel.channel_type.value,
        enabled=new_channel.enabled,
        rate_limit_per_minute=new_channel.rate_limit_per_minute,
        sent_count=new_channel.sent_count
    )

@app.get("/api/v1/channels", response_model=List[ChannelResponse])
async def list_channels():
    """List all notification channels."""
    return [
        ChannelResponse(
            channel_id=str(c.channel_id),
            name=c.name,
            channel_type=c.channel_type.value,
            enabled=c.enabled,
            rate_limit_per_minute=c.rate_limit_per_minute,
            sent_count=c.sent_count
        )
        for c in notification_service.channels.values()
    ]

@app.get("/api/v1/channels/{channel_id}")
async def get_channel(channel_id: str):
    """Get channel details."""
    try:
        uuid_obj = UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel ID")
    
    channel = notification_service.channels.get(uuid_obj)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    safe_config = {k: v for k, v in channel.config.items() 
                   if 'password' not in k.lower() and 'token' not in k.lower() and 'key' not in k.lower()}
    
    return {
        "channel_id": str(channel.channel_id),
        "name": channel.name,
        "channel_type": channel.channel_type.value,
        "enabled": channel.enabled,
        "config": safe_config,
        "rate_limit_per_minute": channel.rate_limit_per_minute,
        "sent_count": channel.sent_count,
        "last_sent": channel.last_sent.isoformat() if channel.last_sent else None
    }

@app.delete("/api/v1/channels/{channel_id}")
async def delete_channel(channel_id: str):
    """Delete a notification channel."""
    try:
        uuid_obj = UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel ID")
    
    if not notification_service.remove_channel(uuid_obj):
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {"status": "deleted"}

# ==================== ESCALATION POLICIES API ====================

@app.post("/api/v1/policies", response_model=EscalationPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(policy: EscalationPolicyCreate):
    """Create an escalation policy."""
    levels = [
        EscalationLevel(
            level=l.level,
            name=l.name,
            timeout_minutes=l.timeout_minutes,
            channels=l.channels,
            recipients=l.recipients,
            require_ack=l.require_ack
        )
        for l in policy.levels
    ]
    
    new_policy = EscalationPolicy(
        policy_id=uuid4(),
        name=policy.name,
        description=policy.description,
        levels=levels,
        rotation_id=UUID(policy.rotation_id) if policy.rotation_id else None
    )
    
    policy_id = escalation_engine.add_policy(new_policy)
    
    return EscalationPolicyResponse(
        policy_id=str(policy_id),
        name=new_policy.name,
        description=new_policy.description,
        levels=len(new_policy.levels),
        enabled=new_policy.enabled,
        created_at=new_policy.created_at.isoformat()
    )

@app.get("/api/v1/policies", response_model=List[EscalationPolicyResponse])
async def list_policies():
    """List all escalation policies."""
    return [
        EscalationPolicyResponse(
            policy_id=str(p.policy_id),
            name=p.name,
            description=p.description,
            levels=len(p.levels),
            enabled=p.enabled,
            created_at=p.created_at.isoformat()
        )
        for p in escalation_engine.policies.values()
    ]

@app.get("/api/v1/policies/{policy_id}")
async def get_policy(policy_id: str):
    """Get escalation policy details."""
    try:
        uuid_obj = UUID(policy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid policy ID")
    
    policy = escalation_engine.get_policy(uuid_obj)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return {
        "policy_id": str(policy.policy_id),
        "name": policy.name,
        "description": policy.description,
        "levels": [
            {
                "level": l.level,
                "name": l.name,
                "timeout_minutes": l.timeout_minutes,
                "channels": l.channels,
                "recipients": l.recipients,
                "require_ack": l.require_ack
            }
            for l in policy.levels
        ],
        "rotation_id": str(policy.rotation_id) if policy.rotation_id else None,
        "enabled": policy.enabled
    }

@app.post("/api/v1/policies/{policy_id}/escalate")
async def trigger_escalation(
    policy_id: str,
    alert_id: str,
    severity: Severity,
    message: str,
    symbol: Optional[str] = None
):
    """Manually trigger an escalation."""
    try:
        policy_uuid = UUID(policy_id)
        alert_uuid = UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    instance = escalation_engine.start_escalation(
        policy_id=policy_uuid,
        alert_id=alert_uuid,
        severity=severity,
        message=message,
        symbol=symbol
    )
    
    if not instance:
        raise HTTPException(status_code=400, detail="Failed to start escalation")
    
    return EscalationResponse(
        escalation_id=str(instance.escalation_id),
        policy_id=str(instance.policy_id),
        alert_id=str(instance.alert_id),
        severity=instance.severity.value,
        status=instance.status.value,
        current_level=instance.current_level,
        started_at=instance.started_at.isoformat()
    )

@app.get("/api/v1/escalations")
async def list_escalations(
    status: Optional[str] = None,
    policy_id: Optional[str] = None
):
    """List active escalation instances."""
    instances = escalation_engine.get_active_escalations()
    
    if status:
        instances = [i for i in instances if i.status.value == status]
    if policy_id:
        instances = [i for i in instances if str(i.policy_id) == policy_id]
    
    return [
        EscalationResponse(
            escalation_id=str(i.escalation_id),
            policy_id=str(i.policy_id),
            alert_id=str(i.alert_id),
            severity=i.severity.value,
            status=i.status.value,
            current_level=i.current_level,
            started_at=i.started_at.isoformat(),
            acknowledged_by=i.acknowledged_by,
            resolved_by=i.resolved_by
        )
        for i in instances
    ]

# ==================== WEBSOCKET API ====================

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alert streaming."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for client messages (filters, etc.)
            data = await websocket.receive_json()
            
            if data.get("action") == "filter":
                manager.set_filters(websocket, data.get("filters", {}))
                await websocket.send_json({"status": "filters_updated"})
            
            elif data.get("action") == "ping":
                await websocket.send_json({"status": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ==================== ANALYTICS API ====================

@app.get("/api/v1/analytics/alert-history")
async def get_alert_history(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    interval: str = "1h"
):
    """Get aggregated alert history."""
    alerts = alert_history
    
    if start_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) >= start_date]
    if end_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) <= end_date]
    
    # Simple aggregation by hour
    from collections import defaultdict
    by_time = defaultdict(int)
    
    for alert in alerts:
        ts = datetime.fromisoformat(alert["timestamp"])
        hour_key = ts.strftime("%Y-%m-%d %H:00")
        by_time[hour_key] += 1
    
    return {
        "total": len(alerts),
        "interval": interval,
        "time_series": [
            {"timestamp": k, "count": v}
            for k, v in sorted(by_time.items())
        ]
    }

@app.get("/api/v1/analytics/metrics")
async def get_metrics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> AlertMetrics:
    """Get alert metrics and statistics."""
    alerts = alert_history
    
    if start_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) >= start_date]
    if end_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) <= end_date]
    
    by_severity = {}
    by_rule_type = {}
    by_symbol = {}
    
    for alert in alerts:
        sev = alert.get("severity", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        
        rt = alert.get("rule_type", "unknown")
        by_rule_type[rt] = by_rule_type.get(rt, 0) + 1
        
        sym = alert.get("symbol", "unknown")
        by_symbol[sym] = by_symbol.get(sym, 0) + 1
    
    # Calculate acknowledgment rate
    stats = escalation_engine.get_statistics(start_date, end_date)
    
    return AlertMetrics(
        total_alerts=len(alerts),
        by_severity=by_severity,
        by_rule_type=by_rule_type,
        by_symbol=by_symbol,
        acknowledgment_rate=stats.get("acknowledgment_rate", 0),
        avg_resolution_time_minutes=None
    )

@app.get("/api/v1/analytics/top-alerts")
async def get_top_alerts(
    limit: int = Query(10, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """Get most frequent alerts."""
    alerts = alert_history
    
    if start_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) >= start_date]
    if end_date:
        alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) <= end_date]
    
    from collections import Counter
    
    # Count by rule name
    rule_counts = Counter(a.get("rule_name", "unknown") for a in alerts)
    symbol_counts = Counter(a.get("symbol", "unknown") for a in alerts if a.get("symbol"))
    
    return {
        "by_rule": [
            {"rule_name": name, "count": count}
            for name, count in rule_counts.most_common(limit)
        ],
        "by_symbol": [
            {"symbol": sym, "count": count}
            for sym, count in symbol_counts.most_common(limit)
        ]
    }

# ==================== TEMPLATES API ====================

@app.get("/api/v1/templates")
async def list_templates():
    """List available alert templates."""
    return [
        {
            "template_id": key,
            "name": template.name,
            "channel_type": template.channel_type.value,
            "description": template.description,
            "variables": template.variables
        }
        for key, template in ALERT_TEMPLATES.items()
    ]

@app.get("/api/v1/templates/{template_id}")
async def get_template(template_id: str):
    """Get template details."""
    template = ALERT_TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "template_id": template_id,
        "name": template.name,
        "channel_type": template.channel_type.value,
        "description": template.description,
        "subject_template": template.subject_template,
        "body_template": template.body_template,
        "variables": template.variables
    }

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "rule_engine": len(rule_engine.rules),
            "notification_service": len(notification_service.channels),
            "escalation_engine": len(escalation_engine.policies)
        }
    }

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "DragonScope Enterprise Alerting API",
        "version": "1.0.0",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
