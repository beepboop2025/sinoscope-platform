"""
DragonScope Enterprise Alerting - Notification Service

Multi-channel notification delivery system supporting WebSocket, Email, SMS,
Slack, PagerDuty, and custom Webhooks with templating and batch processing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

import aiohttp
from jinja2 import Environment, BaseLoader, TemplateError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Supported notification channels."""
    WEBSOCKET = "websocket"
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


class DeliveryStatus(str, Enum):
    """Delivery status for notifications."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class NotificationChannel:
    """Configuration for a notification channel."""
    channel_id: UUID
    channel_type: ChannelType
    name: str
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit_per_minute: int = 60
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Runtime tracking
    last_sent: Optional[datetime] = None
    sent_count: int = 0


@dataclass
class NotificationTemplate:
    """Template for notification content."""
    template_id: UUID
    name: str
    channel_type: ChannelType
    subject_template: str
    body_template: str
    description: str = ""
    variables: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def render(self, variables: Dict[str, Any]) -> tuple[str, str]:
        """Render template with variables."""
        env = Environment(loader=BaseLoader())
        
        subject = env.from_string(self.subject_template).render(variables)
        body = env.from_string(self.body_template).render(variables)
        
        return subject, body


@dataclass
class Notification:
    """Individual notification instance."""
    notification_id: UUID
    alert_id: UUID
    channel_id: UUID
    channel_type: ChannelType
    recipient: str
    subject: str
    body: str
    status: DeliveryStatus = DeliveryStatus.PENDING
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryReceipt:
    """Receipt for delivered notification."""
    receipt_id: UUID
    notification_id: UUID
    channel_type: ChannelType
    status: DeliveryStatus
    timestamp: datetime
    provider_response: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None


# Alert Templates for Common Scenarios

ALERT_TEMPLATES = {
    "price_threshold": NotificationTemplate(
        template_id=uuid4(),
        name="Price Threshold Alert",
        channel_type=ChannelType.EMAIL,
        subject_template="🚨 Price Alert: {{ symbol }} {{ direction }} ${{ threshold }}",
        body_template="""
<h2>Price Alert Triggered</h2>

<p><strong>Symbol:</strong> {{ symbol }}</p>
<p><strong>Current Price:</strong> ${{ price }}</p>
<p><strong>Threshold:</strong> ${{ threshold }}</p>
<p><strong>Direction:</strong> {{ direction }}</p>
<p><strong>Time:</strong> {{ timestamp }}</p>

<hr>
<p><em>This is an automated alert from DragonScope Enterprise Alerting System.</em></p>
""",
        description="Alert when price crosses above or below threshold",
        variables=["symbol", "price", "threshold", "direction", "timestamp"]
    ),
    
    "volume_spike": NotificationTemplate(
        template_id=uuid4(),
        name="Volume Spike Detection",
        channel_type=ChannelType.EMAIL,
        subject_template="📊 Volume Spike: {{ symbol }}",
        body_template="""
<h2>Volume Spike Detected</h2>

<p><strong>Symbol:</strong> {{ symbol }}</p>
<p><strong>Current Volume:</strong> {{ current_volume }}</p>
<p><strong>Average Volume:</strong> {{ avg_volume }}</p>
<p><strong>Multiplier:</strong> {{ multiplier }}x</p>
<p><strong>Time:</strong> {{ timestamp }}</p>

<hr>
<p><em>This is an automated alert from DragonScope Enterprise Alerting System.</em></p>
""",
        description="Alert when volume exceeds historical average",
        variables=["symbol", "current_volume", "avg_volume", "multiplier", "timestamp"]
    ),
    
    "technical_breakout": NotificationTemplate(
        template_id=uuid4(),
        name="Technical Pattern Breakout",
        channel_type=ChannelType.EMAIL,
        subject_template="📈 Pattern Alert: {{ pattern }} on {{ symbol }}",
        body_template="""
<h2>Technical Pattern Identified</h2>

<p><strong>Symbol:</strong> {{ symbol }}</p>
<p><strong>Pattern:</strong> {{ pattern }}</p>
<p><strong>Direction:</strong> {{ direction }}</p>
<p><strong>Confidence:</strong> {{ confidence }}%</p>
<p><strong>Price:</strong> ${{ price }}</p>
<p><strong>Time:</strong> {{ timestamp }}</p>

<hr>
<p><em>This is an automated alert from DragonScope Enterprise Alerting System.</em></p>
""",
        description="Alert on technical pattern completion",
        variables=["symbol", "pattern", "direction", "confidence", "price", "timestamp"]
    ),
    
    "news_alert": NotificationTemplate(
        template_id=uuid4(),
        name="Breaking News Alert",
        channel_type=ChannelType.EMAIL,
        subject_template="📰 News Alert: {{ symbol }} - {{ headline|truncate(50) }}",
        body_template="""
<h2>Breaking News Alert</h2>

<p><strong>Symbol:</strong> {{ symbol }}</p>
<p><strong>Headline:</strong> {{ headline }}</p>
<p><strong>Source:</strong> {{ source }}</p>
<p><strong>Sentiment:</strong> {{ sentiment }}</p>
<p><strong>Time:</strong> {{ timestamp }}</p>

<hr>
<p><em>This is an automated alert from DragonScope Enterprise Alerting System.</em></p>
""",
        description="Alert on high-impact news events",
        variables=["symbol", "headline", "source", "sentiment", "timestamp"]
    ),
    
    "risk_limit": NotificationTemplate(
        template_id=uuid4(),
        name="Risk Threshold Breach",
        channel_type=ChannelType.EMAIL,
        subject_template="⚠️ RISK ALERT: {{ portfolio }} - {{ metric }}",
        body_template="""
<h2 style="color: #dc3545;">Risk Limit Breached</h2>

<p><strong>Portfolio:</strong> {{ portfolio }}</p>
<p><strong>Metric:</strong> {{ metric }}</p>
<p><strong>Current Value:</strong> {{ current_value }}</p>
<p><strong>Risk Limit:</strong> {{ limit }}</p>
<p><strong>Utilization:</strong> {{ utilization_pct }}%</p>
<p><strong>Time:</strong> {{ timestamp }}</p>

<p style="color: #dc3545;"><strong>Action Required:</strong> Please review position immediately.</p>

<hr>
<p><em>This is an automated alert from DragonScope Enterprise Alerting System.</em></p>
""",
        description="Alert when risk metrics exceed limits",
        variables=["portfolio", "metric", "current_value", "limit", "utilization_pct", "timestamp"]
    ),
    
    # SMS Templates (shorter)
    "price_threshold_sms": NotificationTemplate(
        template_id=uuid4(),
        name="Price Threshold SMS",
        channel_type=ChannelType.SMS,
        subject_template="",
        body_template="DragonScope Alert: {{ symbol }} price {{ direction }} ${{ threshold }}. Current: ${{ price }}",
        variables=["symbol", "price", "threshold", "direction"]
    ),
    
    "risk_limit_sms": NotificationTemplate(
        template_id=uuid4(),
        name="Risk Limit SMS",
        channel_type=ChannelType.SMS,
        subject_template="",
        body_template="RISK ALERT: {{ portfolio }} {{ metric }} at {{ utilization_pct }}% of limit. Action required!",
        variables=["portfolio", "metric", "utilization_pct"]
    ),
    
    # Slack Templates
    "price_threshold_slack": NotificationTemplate(
        template_id=uuid4(),
        name="Price Threshold Slack",
        channel_type=ChannelType.SLACK,
        subject_template="",
        body_template="""
{
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 Price Alert: {{ symbol }}"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Symbol:*\\n{{ symbol }}"},
                {"type": "mrkdwn", "text": "*Current Price:*\\n${{ price }}"},
                {"type": "mrkdwn", "text": "*Threshold:*\\n${{ threshold }}"},
                {"type": "mrkdwn", "text": "*Direction:*\\n{{ direction }}"}
            ]
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Time: {{ timestamp }}"}
            ]
        }
    ]
}
""",
        variables=["symbol", "price", "threshold", "direction", "timestamp"]
    ),
    
    "risk_limit_slack": NotificationTemplate(
        template_id=uuid4(),
        name="Risk Limit Slack",
        channel_type=ChannelType.SLACK,
        subject_template="",
        body_template="""
{
    "attachments": [
        {
            "color": "danger",
            "title": "⚠️ Risk Limit Breached: {{ portfolio }}",
            "fields": [
                {"title": "Metric", "value": "{{ metric }}", "short": true},
                {"title": "Current Value", "value": "{{ current_value }}", "short": true},
                {"title": "Risk Limit", "value": "{{ limit }}", "short": true},
                {"title": "Utilization", "value": "{{ utilization_pct }}%", "short": true}
            ],
            "footer": "DragonScope Alerting",
            "ts": "{{ timestamp }}"
        }
    ]
}
""",
        variables=["portfolio", "metric", "current_value", "limit", "utilization_pct", "timestamp"]
    )
}


class BaseChannel(ABC):
    """Abstract base class for notification channels."""
    
    def __init__(self, channel_config: NotificationChannel):
        self.config = channel_config
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    async def send(self, notification: Notification) -> DeliveryReceipt:
        """Send a notification."""
        pass
    
    def check_rate_limit(self) -> bool:
        """Check if channel is within rate limit."""
        if self.config.last_sent is None:
            return True
        
        time_since_last = datetime.utcnow() - self.config.last_sent
        min_interval = timedelta(minutes=1) / self.config.rate_limit_per_minute
        
        return time_since_last >= min_interval
    
    def update_rate_limit(self):
        """Update rate limit tracking."""
        self.config.last_sent = datetime.utcnow()
        self.config.sent_count += 1


class WebSocketChannel(BaseChannel):
    """WebSocket notification channel."""
    
    # In-memory store of connected clients
    clients: Dict[str, List[Callable]] = {}
    
    def __init__(self, channel_config: NotificationChannel):
        super().__init__(channel_config)
        self.room = channel_config.config.get("room", "alerts")
    
    @classmethod
    def register_client(cls, room: str, callback: Callable):
        """Register a WebSocket client callback."""
        if room not in cls.clients:
            cls.clients[room] = []
        cls.clients[room].append(callback)
    
    @classmethod
    def unregister_client(cls, room: str, callback: Callable):
        """Unregister a WebSocket client callback."""
        if room in cls.clients:
            cls.clients[room] = [c for c in cls.clients[room] if c != callback]
    
    async def send(self, notification: Notification) -> DeliveryReceipt:
        """Send via WebSocket to all connected clients."""
        try:
            clients = self.clients.get(self.room, [])
            message = {
                "notification_id": str(notification.notification_id),
                "alert_id": str(notification.alert_id),
                "subject": notification.subject,
                "body": notification.body,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            for callback in clients:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"WebSocket callback error: {e}")
            
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.WEBSOCKET,
                status=DeliveryStatus.DELIVERED,
                timestamp=datetime.utcnow(),
                provider_response={"clients_notified": len(clients)}
            )
            
        except Exception as e:
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.WEBSOCKET,
                status=DeliveryStatus.FAILED,
                timestamp=datetime.utcnow(),
                error_details=str(e)
            )


class EmailChannel(BaseChannel):
    """Email notification channel via SMTP."""
    
    async def send(self, notification: Notification) -> DeliveryReceipt:
        """Send email via SMTP."""
        try:
            config = self.config.config
            
            # Build email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = notification.subject
            msg['From'] = config.get('from_address', 'alerts@dragonscope.io')
            msg['To'] = notification.recipient
            
            # Attach HTML body
            msg.attach(MIMEText(notification.body, 'html'))
            
            # Send via SMTP
            host = config.get('smtp_host', 'localhost')
            port = config.get('smtp_port', 587)
            username = config.get('smtp_user')
            password = config.get('smtp_password')
            use_tls = config.get('use_tls', True)
            
            # Run SMTP in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def send_email():
                with smtplib.SMTP(host, port) as server:
                    if use_tls:
                        server.starttls()
                    if username and password:
                        server.login(username, password)
                    server.send_message(msg)
            
            await loop.run_in_executor(None, send_email)
            
            self.update_rate_limit()
            
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.EMAIL,
                status=DeliveryStatus.DELIVERED,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.EMAIL,
                status=DeliveryStatus.FAILED,
                timestamp=datetime.utcnow(),
                error_details=str(e)
            )


class SMSChannel(BaseChannel):
    """SMS notification channel via Twilio."""
    
    async def send(self, notification: Notification) -> DeliveryReceipt:
        """Send SMS via Twilio API."""
        try:
            config = self.config.config
            account_sid = config.get('account_sid')
            auth_token = config.get('auth_token')
            from_number = config.get('from_number')
            
            if not all([account_sid, auth_token, from_number]):
                raise ValueError("Missing Twilio configuration")
            
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            auth = aiohttp.BasicAuth(account_sid, auth_token)
            
            payload = {
                'From': from_number,
                'To': notification.recipient,
                'Body': notification.body
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, auth=auth) as resp:
                    response_data = await resp.json()
                    
                    if resp.status == 201:
                        self.update_rate_limit()
                        return DeliveryReceipt(
                            receipt_id=uuid4(),
                            notification_id=notification.notification_id,
                            channel_type=ChannelType.SMS,
                            status=DeliveryStatus.DELIVERED,
                            timestamp=datetime.utcnow(),
                            provider_response=response_data
                        )
                    else:
                        raise Exception(f"Twilio error: {response_data.get('message')}")
                        
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.SMS,
                status=DeliveryStatus.FAILED,
                timestamp=datetime.utcnow(),
                error_details=str(e)
            )


class SlackChannel(BaseChannel):
    """Slack notification channel."""
    
    async def send(self, notification: Notification) -> DeliveryReceipt:
        """Send Slack message via webhook or API."""
        try:
            config = self.config.config
            bot_token = config.get('bot_token')
            webhook_url = config.get('webhook_url')
            
            # Parse body as JSON if it's formatted that way
            try:
                payload = json.loads(notification.body)
            except json.JSONDecodeError:
                # Plain text message
                payload = {
                    "text": notification.subject,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": notification.body}
                        }
                    ]
                }
            
            if webhook_url:
                # Use webhook
                async with aiohttp.ClientSession() as session:
                    async with session.post(webhook_url, json=payload) as resp:
                        if resp.status in [200, 201]:
                            self.update_rate_limit()
                            return DeliveryReceipt(
                                receipt_id=uuid4(),
                                notification_id=notification.notification_id,
                                channel_type=ChannelType.SLACK,
                                status=DeliveryStatus.DELIVERED,
                                timestamp=datetime.utcnow()
                            )
                        else:
                            raise Exception(f"Slack webhook error: {resp.status}")
            
            elif bot_token:
                # Use API
                channel = config.get('channel', notification.recipient)
                headers = {"Authorization": f"Bearer {bot_token}"}
                api_payload = {
                    "channel": channel,
                    **payload
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://slack.com/api/chat.postMessage",
                        headers=headers,
                        json=api_payload
                    ) as resp:
                        response_data = await resp.json()
                        if response_data.get('ok'):
                            self.update_rate_limit()
                            return DeliveryReceipt(
                                receipt_id=uuid4(),
                                notification_id=notification.notification_id,
                                channel_type=ChannelType.SLACK,
                                status=DeliveryStatus.DELIVERED,
                                timestamp=datetime.utcnow(),
                                provider_response=response_data
                            )
                        else:
                            raise Exception(f"Slack API error: {response_data.get('error')}")
            else:
                raise ValueError("Missing Slack configuration (bot_token or webhook_url)")
                
        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.SLACK,
                status=DeliveryStatus.FAILED,
                timestamp=datetime.utcnow(),
                error_details=str(e)
            )


class PagerDutyChannel(BaseChannel):
    """PagerDuty notification channel."""
    
    async def send(self, notification: Notification) -> DeliveryReceipt:
        """Send PagerDuty incident."""
        try:
            config = self.config.config
            api_key = config.get('api_key')
            service_key = config.get('service_key') or config.get('routing_key')
            
            if not all([api_key, service_key]):
                raise ValueError("Missing PagerDuty configuration")
            
            # Determine severity
            severity_map = {
                "critical": "critical",
                "high": "error",
                "medium": "warning",
                "low": "info",
                "info": "info"
            }
            
            pd_severity = severity_map.get(
                notification.metadata.get('severity', 'warning').lower(),
                'warning'
            )
            
            payload = {
                "routing_key": service_key,
                "event_action": "trigger",
                "dedup_key": str(notification.alert_id),
                "payload": {
                    "summary": notification.subject,
                    "severity": pd_severity,
                    "source": "DragonScope Alerting",
                    "custom_details": {
                        "body": notification.body,
                        **notification.metadata
                    }
                }
            }
            
            headers = {
                "Authorization": f"Token token={api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    headers=headers,
                    json=payload
                ) as resp:
                    response_data = await resp.json()
                    
                    if resp.status == 202:
                        self.update_rate_limit()
                        return DeliveryReceipt(
                            receipt_id=uuid4(),
                            notification_id=notification.notification_id,
                            channel_type=ChannelType.PAGERDUTY,
                            status=DeliveryStatus.DELIVERED,
                            timestamp=datetime.utcnow(),
                            provider_response=response_data
                        )
                    else:
                        raise Exception(f"PagerDuty error: {response_data}")
                        
        except Exception as e:
            logger.error(f"PagerDuty send failed: {e}")
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.PAGERDUTY,
                status=DeliveryStatus.FAILED,
                timestamp=datetime.utcnow(),
                error_details=str(e)
            )


class WebhookChannel(BaseChannel):
    """Generic webhook notification channel."""
    
    async def send(self, notification: Notification) -> DeliveryReceipt:
        """Send HTTP webhook."""
        try:
            config = self.config.config
            webhook_url = config.get('url') or notification.recipient
            method = config.get('method', 'POST').upper()
            headers = config.get('headers', {})
            headers['Content-Type'] = headers.get('Content-Type', 'application/json')
            
            # Build payload
            payload = {
                "notification_id": str(notification.notification_id),
                "alert_id": str(notification.alert_id),
                "subject": notification.subject,
                "body": notification.body,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": notification.metadata
            }
            
            # Add custom payload template if configured
            if 'payload_template' in config:
                template = config['payload_template']
                payload = template.format(**payload)
                # Parse back if it's JSON
                try:
                    payload = json.loads(payload)
                except:
                    pass
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    webhook_url,
                    headers=headers,
                    json=payload if isinstance(payload, dict) else None,
                    data=payload if isinstance(payload, str) else None
                ) as resp:
                    response_text = await resp.text()
                    
                    if resp.status < 400:
                        self.update_rate_limit()
                        return DeliveryReceipt(
                            receipt_id=uuid4(),
                            notification_id=notification.notification_id,
                            channel_type=ChannelType.WEBHOOK,
                            status=DeliveryStatus.DELIVERED,
                            timestamp=datetime.utcnow(),
                            provider_response={"status": resp.status, "body": response_text[:1000]}
                        )
                    else:
                        raise Exception(f"Webhook error: {resp.status} - {response_text[:500]}")
                        
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=ChannelType.WEBHOOK,
                status=DeliveryStatus.FAILED,
                timestamp=datetime.utcnow(),
                error_details=str(e)
            )


class NotificationService:
    """Main notification service orchestrating multi-channel delivery."""
    
    CHANNEL_MAP = {
        ChannelType.WEBSOCKET: WebSocketChannel,
        ChannelType.EMAIL: EmailChannel,
        ChannelType.SMS: SMSChannel,
        ChannelType.SLACK: SlackChannel,
        ChannelType.PAGERDUTY: PagerDutyChannel,
        ChannelType.WEBHOOK: WebhookChannel
    }
    
    def __init__(self):
        self.channels: Dict[UUID, NotificationChannel] = {}
        self.channel_instances: Dict[UUID, BaseChannel] = {}
        self.templates: Dict[str, NotificationTemplate] = dict(ALERT_TEMPLATES)
        self.notification_queue: asyncio.Queue = asyncio.Queue()
        self.receipts: List[DeliveryReceipt] = []
        self.running = False
        self._batch_buffer: List[Notification] = []
        self._batch_timer: Optional[asyncio.Task] = None
        self._batch_interval = 5  # seconds
    
    def add_channel(self, channel: NotificationChannel) -> UUID:
        """Add a notification channel."""
        self.channels[channel.channel_id] = channel
        channel_class = self.CHANNEL_MAP.get(channel.channel_type)
        if channel_class:
            self.channel_instances[channel.channel_id] = channel_class(channel)
        logger.info(f"Added {channel.channel_type.value} channel: {channel.name}")
        return channel.channel_id
    
    def remove_channel(self, channel_id: UUID) -> bool:
        """Remove a notification channel."""
        if channel_id in self.channels:
            del self.channels[channel_id]
            if channel_id in self.channel_instances:
                del self.channel_instances[channel_id]
            return True
        return False
    
    def get_template(self, template_id: str) -> Optional[NotificationTemplate]:
        """Get a notification template."""
        return self.templates.get(template_id)
    
    def add_template(self, template: NotificationTemplate) -> str:
        """Add a custom template."""
        template_key = str(template.template_id)
        self.templates[template_key] = template
        return template_key
    
    def create_notification(
        self,
        alert_id: UUID,
        channel_id: UUID,
        recipient: str,
        template_id: str,
        variables: Dict[str, Any],
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Notification]:
        """Create a notification from template."""
        template = self.get_template(template_id)
        if not template:
            logger.error(f"Template not found: {template_id}")
            return None
        
        channel = self.channels.get(channel_id)
        if not channel:
            logger.error(f"Channel not found: {channel_id}")
            return None
        
        subject, body = template.render(variables)
        
        return Notification(
            notification_id=uuid4(),
            alert_id=alert_id,
            channel_id=channel_id,
            channel_type=channel.channel_type,
            recipient=recipient,
            subject=subject,
            body=body,
            priority=priority,
            metadata=metadata or {}
        )
    
    async def send_notification(self, notification: Notification) -> DeliveryReceipt:
        """Send a single notification."""
        channel_instance = self.channel_instances.get(notification.channel_id)
        if not channel_instance:
            return DeliveryReceipt(
                receipt_id=uuid4(),
                notification_id=notification.notification_id,
                channel_type=notification.channel_type,
                status=DeliveryStatus.FAILED,
                timestamp=datetime.utcnow(),
                error_details="Channel not found"
            )
        
        notification.status = DeliveryStatus.SENDING
        receipt = await channel_instance.send(notification)
        notification.status = receipt.status
        
        if receipt.status == DeliveryStatus.DELIVERED:
            notification.delivered_at = datetime.utcnow()
        
        self.receipts.append(receipt)
        return receipt
    
    async def send_batch(self, notifications: List[Notification]) -> List[DeliveryReceipt]:
        """Send multiple notifications concurrently."""
        tasks = [self.send_notification(n) for n in notifications]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def queue_notification(self, notification: Notification):
        """Queue notification for batch processing."""
        await self.notification_queue.put(notification)
    
    async def process_queue(self):
        """Process notification queue."""
        batch = []
        
        while self.running:
            try:
                # Collect batch
                notification = await asyncio.wait_for(
                    self.notification_queue.get(),
                    timeout=1.0
                )
                batch.append(notification)
                
                # Process batch when full or timeout
                if len(batch) >= 100:
                    await self.send_batch(batch)
                    batch = []
                    
            except asyncio.TimeoutError:
                if batch:
                    await self.send_batch(batch)
                    batch = []
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
    
    async def start_worker(self):
        """Start the notification worker."""
        self.running = True
        logger.info("Notification service worker started")
        await self.process_queue()
    
    def stop(self):
        """Stop the notification service."""
        self.running = False
        logger.info("Notification service stopped")
    
    def get_delivery_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get delivery statistics."""
        receipts = self.receipts
        
        if start_time:
            receipts = [r for r in receipts if r.timestamp >= start_time]
        if end_time:
            receipts = [r for r in receipts if r.timestamp <= end_time]
        
        total = len(receipts)
        delivered = len([r for r in receipts if r.status == DeliveryStatus.DELIVERED])
        failed = len([r for r in receipts if r.status == DeliveryStatus.FAILED])
        
        by_channel = {}
        for r in receipts:
            channel = r.channel_type.value
            if channel not in by_channel:
                by_channel[channel] = {"total": 0, "delivered": 0, "failed": 0}
            by_channel[channel]["total"] += 1
            if r.status == DeliveryStatus.DELIVERED:
                by_channel[channel]["delivered"] += 1
            elif r.status == DeliveryStatus.FAILED:
                by_channel[channel]["failed"] += 1
        
        return {
            "total": total,
            "delivered": delivered,
            "failed": failed,
            "success_rate": delivered / total if total > 0 else 0,
            "by_channel": by_channel
        }


# Convenience functions

def create_email_channel(
    name: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_address: str
) -> NotificationChannel:
    """Factory function to create email channel."""
    return NotificationChannel(
        channel_id=uuid4(),
        channel_type=ChannelType.EMAIL,
        name=name,
        config={
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_user": smtp_user,
            "smtp_password": smtp_password,
            "from_address": from_address,
            "use_tls": True
        }
    )


def create_sms_channel(
    name: str,
    account_sid: str,
    auth_token: str,
    from_number: str
) -> NotificationChannel:
    """Factory function to create SMS channel."""
    return NotificationChannel(
        channel_id=uuid4(),
        channel_type=ChannelType.SMS,
        name=name,
        config={
            "account_sid": account_sid,
            "auth_token": auth_token,
            "from_number": from_number
        },
        rate_limit_per_minute=30  # Twilio rate limit
    )


def create_slack_channel(
    name: str,
    bot_token: Optional[str] = None,
    webhook_url: Optional[str] = None,
    default_channel: str = "#alerts"
) -> NotificationChannel:
    """Factory function to create Slack channel."""
    return NotificationChannel(
        channel_id=uuid4(),
        channel_type=ChannelType.SLACK,
        name=name,
        config={
            "bot_token": bot_token,
            "webhook_url": webhook_url,
            "channel": default_channel
        }
    )


def create_pagerduty_channel(
    name: str,
    api_key: str,
    service_key: str
) -> NotificationChannel:
    """Factory function to create PagerDuty channel."""
    return NotificationChannel(
        channel_id=uuid4(),
        channel_type=ChannelType.PAGERDUTY,
        name=name,
        config={
            "api_key": api_key,
            "service_key": service_key
        },
        rate_limit_per_minute=120
    )


def create_webhook_channel(
    name: str,
    url: str,
    method: str = "POST",
    headers: Optional[Dict[str, str]] = None
) -> NotificationChannel:
    """Factory function to create webhook channel."""
    return NotificationChannel(
        channel_id=uuid4(),
        channel_type=ChannelType.WEBHOOK,
        name=name,
        config={
            "url": url,
            "method": method,
            "headers": headers or {}
        }
    )


if __name__ == "__main__":
    # Demo usage
    async def demo():
        service = NotificationService()
        
        # Add WebSocket channel (no external config needed)
        ws_channel = NotificationChannel(
            channel_id=uuid4(),
            channel_type=ChannelType.WEBSOCKET,
            name="WebSocket Alerts",
            config={"room": "alerts"}
        )
        service.add_channel(ws_channel)
        
        # Create notification from template
        template = ALERT_TEMPLATES["price_threshold"]
        variables = {
            "symbol": "AAPL",
            "price": "155.50",
            "threshold": "150.00",
            "direction": "above",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        subject, body = template.render(variables)
        print(f"Subject: {subject}")
        print(f"Body preview: {body[:200]}...")
        
        # Create notification
        notification = service.create_notification(
            alert_id=uuid4(),
            channel_id=ws_channel.channel_id,
            recipient="websocket",
            template_id="price_threshold_slack",
            variables=variables
        )
        
        if notification:
            print(f"\nCreated notification: {notification.notification_id}")
            print(f"Channel: {notification.channel_type.value}")
    
    asyncio.run(demo())
