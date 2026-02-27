"""
DragonScope Enterprise Alerting - Escalation Policies

Time-based escalation system with severity routing, on-call rotation,
and acknowledgment tracking for enterprise alert management.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EscalationStatus(str, Enum):
    """Status of an escalation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Severity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class OnCallUser:
    """Represents an on-call user."""
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    slack_id: Optional[str] = None
    pagerduty_key: Optional[str] = None
    priority: int = 1
    notification_channels: List[str] = field(default_factory=list)
    
    def get_contact(self, channel_type: str) -> Optional[str]:
        """Get contact info for specific channel."""
        channel_map = {
            "email": self.email,
            "sms": self.phone,
            "slack": self.slack_id,
            "pagerduty": self.pagerduty_key
        }
        return channel_map.get(channel_type)


@dataclass
class OnCallRotation:
    """On-call rotation configuration."""
    rotation_id: UUID
    name: str
    description: str
    schedule_type: str = "weekly"  # weekly, daily, custom
    timezone: str = "America/New_York"
    members: List[OnCallUser] = field(default_factory=list)
    current_index: int = 0
    handoff_time: str = "09:00"  # HH:MM format
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_current_oncall(self) -> Optional[OnCallUser]:
        """Get current on-call user."""
        if not self.members:
            return None
        return self.members[self.current_index]
    
    def get_next_oncall(self) -> Optional[OnCallUser]:
        """Get next user in rotation."""
        if not self.members:
            return None
        next_index = (self.current_index + 1) % len(self.members)
        return self.members[next_index]
    
    def rotate(self) -> OnCallUser:
        """Advance to next person in rotation."""
        if self.members:
            self.current_index = (self.current_index + 1) % len(self.members)
            self.updated_at = datetime.utcnow()
            return self.members[self.current_index]
        raise ValueError("No members in rotation")
    
    def get_oncall_at_time(self, dt: datetime) -> Optional[OnCallUser]:
        """Get on-call user at specific time (basic implementation)."""
        if not self.members:
            return None
        
        if self.schedule_type == "weekly":
            # Rotate weekly
            weeks_since_start = (dt - self.created_at).days // 7
            index = weeks_since_start % len(self.members)
            return self.members[index]
        
        elif self.schedule_type == "daily":
            # Rotate daily
            days_since_start = (dt - self.created_at).days
            index = days_since_start % len(self.members)
            return self.members[index]
        
        return self.get_current_oncall()


@dataclass
class EscalationLevel:
    """Single level in escalation policy."""
    level: int
    name: str
    timeout_minutes: int
    channels: List[str]  # email, sms, slack, pagerduty, etc.
    recipients: List[str]  # Can be user IDs, emails, or group names
    require_ack: bool = True
    notify_all: bool = False  # If True, notify all recipients simultaneously
    repeat_count: int = 1  # How many times to repeat before escalating
    repeat_interval_minutes: int = 5
    auto_escalate_on_no_ack: bool = True
    custom_message_template: Optional[str] = None
    
    def get_recipients(
        self,
        rotation: Optional[OnCallRotation] = None
    ) -> List[OnCallUser]:
        """Resolve recipients to actual users."""
        users = []
        
        for recipient in self.recipients:
            if recipient == "on-call" and rotation:
                user = rotation.get_current_oncall()
                if user:
                    users.append(user)
            elif recipient == "on-call-next" and rotation:
                user = rotation.get_next_oncall()
                if user:
                    users.append(user)
            elif recipient.startswith("user:"):
                # Lookup user by ID
                user_id = recipient.split(":", 1)[1]
                # Would lookup from user database
                pass
            elif recipient.startswith("group:"):
                # Lookup group members
                group_name = recipient.split(":", 1)[1]
                # Would lookup from group database
                pass
            elif "@" in recipient:
                # Direct email
                user = OnCallUser(
                    user_id=recipient,
                    name=recipient.split("@")[0],
                    email=recipient
                )
                users.append(user)
        
        return users


@dataclass
class SeverityRouting:
    """Routing configuration based on severity."""
    severity: Severity
    channels: List[str]
    immediate: bool = False
    skip_escalation: bool = False
    override_recipients: Optional[List[str]] = None
    suppression_window_minutes: Optional[int] = None


@dataclass
class EscalationPolicy:
    """Complete escalation policy."""
    policy_id: UUID
    name: str
    description: str
    levels: List[EscalationLevel] = field(default_factory=list)
    severity_routing: Dict[Severity, SeverityRouting] = field(default_factory=dict)
    rotation_id: Optional[UUID] = None
    global_timeout_minutes: Optional[int] = None
    auto_resolve_after_minutes: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_level(self, level_number: int) -> Optional[EscalationLevel]:
        """Get escalation level by number."""
        for level in self.levels:
            if level.level == level_number:
                return level
        return None
    
    def get_next_level(self, current_level: int) -> Optional[EscalationLevel]:
        """Get next escalation level."""
        next_level_num = current_level + 1
        return self.get_level(next_level_num)
    
    def get_routing_for_severity(self, severity: Severity) -> SeverityRouting:
        """Get routing configuration for severity."""
        return self.severity_routing.get(severity, SeverityRouting(
            severity=severity,
            channels=["email"]
        ))


@dataclass
class Acknowledgment:
    """Alert acknowledgment record."""
    acknowledgment_id: UUID
    escalation_id: UUID
    alert_id: UUID
    user_id: str
    user_name: str
    acknowledged_at: datetime
    message: Optional[str] = None
    via_channel: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if acknowledgment has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class EscalationInstance:
    """Active escalation instance."""
    escalation_id: UUID
    policy_id: UUID
    alert_id: UUID
    severity: Severity
    symbol: Optional[str]
    message: str
    status: EscalationStatus
    current_level: int = 1
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_escalated_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    repeat_count: int = 0
    notifications_sent: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_elapsed_minutes(self) -> float:
        """Get elapsed time since escalation started."""
        return (datetime.utcnow() - self.started_at).total_seconds() / 60
    
    def get_time_at_current_level(self) -> float:
        """Get time spent at current level."""
        reference = self.last_escalated_at or self.started_at
        return (datetime.utcnow() - reference).total_seconds() / 60
    
    def should_escalate(self, level: EscalationLevel) -> bool:
        """Check if should escalate to next level."""
        if self.status in [EscalationStatus.ACKNOWLEDGED, EscalationStatus.RESOLVED]:
            return False
        
        if not level.auto_escalate_on_no_ack:
            return False
        
        return self.get_time_at_current_level() >= level.timeout_minutes


class EscalationEngine:
    """Main escalation engine managing policies and instances."""
    
    def __init__(self):
        self.policies: Dict[UUID, EscalationPolicy] = {}
        self.rotations: Dict[UUID, OnCallRotation] = {}
        self.instances: Dict[UUID, EscalationInstance] = {}
        self.acknowledgments: Dict[UUID, List[Acknowledgment]] = {}
        self.running = False
        self.check_interval_seconds = 30
        self._escalation_handlers: List[Callable[[EscalationInstance], None]] = []
        self._notification_handlers: List[Callable[[EscalationInstance, EscalationLevel, List[OnCallUser]], None]] = []
    
    def register_escalation_handler(self, handler: Callable[[EscalationInstance], None]):
        """Register handler for escalation events."""
        self._escalation_handlers.append(handler)
    
    def register_notification_handler(
        self,
        handler: Callable[[EscalationInstance, EscalationLevel, List[OnCallUser]], None]
    ):
        """Register handler for notification events."""
        self._notification_handlers.append(handler)
    
    def add_policy(self, policy: EscalationPolicy) -> UUID:
        """Add an escalation policy."""
        self.policies[policy.policy_id] = policy
        logger.info(f"Added escalation policy: {policy.name}")
        return policy.policy_id
    
    def get_policy(self, policy_id: UUID) -> Optional[EscalationPolicy]:
        """Get policy by ID."""
        return self.policies.get(policy_id)
    
    def update_policy(
        self,
        policy_id: UUID,
        changes: Dict[str, Any]
    ) -> Optional[EscalationPolicy]:
        """Update an escalation policy."""
        if policy_id not in self.policies:
            return None
        
        policy = self.policies[policy_id]
        
        for key, value in changes.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        
        policy.updated_at = datetime.utcnow()
        logger.info(f"Updated escalation policy: {policy.name}")
        return policy
    
    def delete_policy(self, policy_id: UUID) -> bool:
        """Delete an escalation policy."""
        if policy_id in self.policies:
            del self.policies[policy_id]
            return True
        return False
    
    def add_rotation(self, rotation: OnCallRotation) -> UUID:
        """Add an on-call rotation."""
        self.rotations[rotation.rotation_id] = rotation
        logger.info(f"Added on-call rotation: {rotation.name}")
        return rotation.rotation_id
    
    def get_rotation(self, rotation_id: UUID) -> Optional[OnCallRotation]:
        """Get rotation by ID."""
        return self.rotations.get(rotation_id)
    
    def start_escalation(
        self,
        policy_id: UUID,
        alert_id: UUID,
        severity: Severity,
        message: str,
        symbol: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[EscalationInstance]:
        """Start a new escalation process."""
        policy = self.policies.get(policy_id)
        if not policy or not policy.enabled:
            logger.error(f"Policy not found or disabled: {policy_id}")
            return None
        
        escalation_id = uuid4()
        instance = EscalationInstance(
            escalation_id=escalation_id,
            policy_id=policy_id,
            alert_id=alert_id,
            severity=severity,
            symbol=symbol,
            message=message,
            status=EscalationStatus.IN_PROGRESS,
            current_level=1,
            metadata=metadata or {}
        )
        
        self.instances[escalation_id] = instance
        
        # Apply severity-based routing
        routing = policy.get_routing_for_severity(severity)
        if routing.immediate:
            # Override first level with immediate routing
            pass
        
        # Send initial notifications
        self._notify_level(instance, 1)
        
        logger.info(f"Started escalation {escalation_id} for alert {alert_id}")
        return instance
    
    def _notify_level(self, instance: EscalationInstance, level_number: int):
        """Send notifications for an escalation level."""
        policy = self.policies.get(instance.policy_id)
        if not policy:
            return
        
        level = policy.get_level(level_number)
        if not level:
            return
        
        rotation = None
        if policy.rotation_id:
            rotation = self.rotations.get(policy.rotation_id)
        
        recipients = level.get_recipients(rotation)
        
        # Record notification
        notification_record = {
            "level": level_number,
            "sent_at": datetime.utcnow().isoformat(),
            "channels": level.channels,
            "recipients": [r.user_id for r in recipients],
            "repeat_count": instance.repeat_count
        }
        instance.notifications_sent.append(notification_record)
        
        # Call notification handlers
        for handler in self._notification_handlers:
            try:
                handler(instance, level, recipients)
            except Exception as e:
                logger.error(f"Notification handler error: {e}")
    
    def acknowledge(
        self,
        escalation_id: UUID,
        user_id: str,
        user_name: str,
        message: Optional[str] = None,
        via_channel: Optional[str] = None,
        expires_minutes: Optional[int] = None
    ) -> Optional[Acknowledgment]:
        """Acknowledge an escalation."""
        instance = self.instances.get(escalation_id)
        if not instance:
            return None
        
        if instance.status in [EscalationStatus.RESOLVED, EscalationStatus.CANCELLED]:
            return None
        
        instance.status = EscalationStatus.ACKNOWLEDGED
        instance.acknowledged_at = datetime.utcnow()
        instance.acknowledged_by = user_id
        
        acknowledgment = Acknowledgment(
            acknowledgment_id=uuid4(),
            escalation_id=escalation_id,
            alert_id=instance.alert_id,
            user_id=user_id,
            user_name=user_name,
            acknowledged_at=datetime.utcnow(),
            message=message,
            via_channel=via_channel
        )
        
        if expires_minutes:
            acknowledgment.expires_at = datetime.utcnow() + timedelta(minutes=expires_minutes)
        
        if escalation_id not in self.acknowledgments:
            self.acknowledgments[escalation_id] = []
        self.acknowledgments[escalation_id].append(acknowledgment)
        
        logger.info(f"Escalation {escalation_id} acknowledged by {user_name}")
        return acknowledgment
    
    def resolve(
        self,
        escalation_id: UUID,
        user_id: str,
        resolution_notes: Optional[str] = None
    ) -> bool:
        """Resolve an escalation."""
        instance = self.instances.get(escalation_id)
        if not instance:
            return False
        
        instance.status = EscalationStatus.RESOLVED
        instance.resolved_at = datetime.utcnow()
        instance.resolved_by = user_id
        instance.metadata["resolution_notes"] = resolution_notes
        
        logger.info(f"Escalation {escalation_id} resolved by {user_id}")
        return True
    
    def escalate_manual(self, escalation_id: UUID) -> bool:
        """Manually escalate to next level."""
        instance = self.instances.get(escalation_id)
        if not instance:
            return False
        
        policy = self.policies.get(instance.policy_id)
        if not policy:
            return False
        
        next_level = policy.get_next_level(instance.current_level)
        if not next_level:
            logger.info(f"No more escalation levels for {escalation_id}")
            return False
        
        instance.current_level = next_level.level
        instance.last_escalated_at = datetime.utcnow()
        instance.repeat_count = 0
        instance.status = EscalationStatus.ESCALATED
        
        self._notify_level(instance, next_level.level)
        
        # Call escalation handlers
        for handler in self._escalation_handlers:
            try:
                handler(instance)
            except Exception as e:
                logger.error(f"Escalation handler error: {e}")
        
        logger.info(f"Escalation {escalation_id} escalated to level {next_level.level}")
        return True
    
    async def run_escalation_checker(self):
        """Background task to check and process escalations."""
        self.running = True
        logger.info("Escalation engine started")
        
        while self.running:
            try:
                await self._process_escalations()
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Escalation checker error: {e}")
    
    async def _process_escalations(self):
        """Process active escalations."""
        now = datetime.utcnow()
        
        for instance in list(self.instances.values()):
            if instance.status not in [EscalationStatus.IN_PROGRESS, EscalationStatus.ESCALATED]:
                continue
            
            policy = self.policies.get(instance.policy_id)
            if not policy:
                continue
            
            # Check for auto-resolution
            if policy.auto_resolve_after_minutes:
                elapsed = instance.get_elapsed_minutes()
                if elapsed >= policy.auto_resolve_after_minutes:
                    instance.status = EscalationStatus.EXPIRED
                    instance.resolved_at = now
                    continue
            
            # Check current level for escalation
            level = policy.get_level(instance.current_level)
            if not level:
                continue
            
            if instance.should_escalate(level):
                # Check if we should repeat first
                if instance.repeat_count < level.repeat_count - 1:
                    instance.repeat_count += 1
                    self._notify_level(instance, instance.current_level)
                else:
                    # Escalate to next level
                    self.escalate_manual(instance.escalation_id)
    
    def get_escalation(self, escalation_id: UUID) -> Optional[EscalationInstance]:
        """Get escalation instance by ID."""
        return self.instances.get(escalation_id)
    
    def get_active_escalations(
        self,
        policy_id: Optional[UUID] = None,
        severity: Optional[Severity] = None
    ) -> List[EscalationInstance]:
        """Get active escalation instances."""
        active_statuses = [
            EscalationStatus.PENDING,
            EscalationStatus.IN_PROGRESS,
            EscalationStatus.ESCALATED
        ]
        
        result = [
            i for i in self.instances.values()
            if i.status in active_statuses
        ]
        
        if policy_id:
            result = [i for i in result if i.policy_id == policy_id]
        
        if severity:
            result = [i for i in result if i.severity == severity]
        
        return result
    
    def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get escalation statistics."""
        instances = list(self.instances.values())
        
        if start_time:
            instances = [i for i in instances if i.started_at >= start_time]
        if end_time:
            instances = [i for i in instances if i.started_at <= end_time]
        
        total = len(instances)
        acknowledged = len([i for i in instances if i.acknowledged_at])
        resolved = len([i for i in instances if i.status == EscalationStatus.RESOLVED])
        expired = len([i for i in instances if i.status == EscalationStatus.EXPIRED])
        
        avg_time_to_ack = 0
        ack_times = [
            (i.acknowledged_at - i.started_at).total_seconds() / 60
            for i in instances if i.acknowledged_at
        ]
        if ack_times:
            avg_time_to_ack = sum(ack_times) / len(ack_times)
        
        by_severity = {}
        for sev in Severity:
            count = len([i for i in instances if i.severity == sev])
            by_severity[sev.value] = count
        
        return {
            "total": total,
            "acknowledged": acknowledged,
            "resolved": resolved,
            "expired": expired,
            "acknowledgment_rate": acknowledged / total if total > 0 else 0,
            "avg_time_to_acknowledge_minutes": avg_time_to_ack,
            "by_severity": by_severity
        }


# Factory functions for common escalation policies

def create_basic_escalation_policy(
    name: str = "Basic Escalation"
) -> EscalationPolicy:
    """Factory for basic 3-level escalation policy."""
    return EscalationPolicy(
        policy_id=uuid4(),
        name=name,
        description="Basic escalation: notify user, then manager, then on-call",
        levels=[
            EscalationLevel(
                level=1,
                name="Initial Notification",
                timeout_minutes=15,
                channels=["email", "websocket"],
                recipients=["on-call"],
                require_ack=True
            ),
            EscalationLevel(
                level=2,
                name="Secondary Escalation",
                timeout_minutes=30,
                channels=["sms", "slack"],
                recipients=["on-call", "on-call-next"],
                require_ack=True
            ),
            EscalationLevel(
                level=3,
                name="Critical Escalation",
                timeout_minutes=60,
                channels=["pagerduty", "phone"],
                recipients=["on-call", "on-call-next", "manager@company.com"],
                require_ack=True
            )
        ],
        severity_routing={
            Severity.CRITICAL: SeverityRouting(
                severity=Severity.CRITICAL,
                channels=["pagerduty", "sms", "email"],
                immediate=True
            ),
            Severity.HIGH: SeverityRouting(
                severity=Severity.HIGH,
                channels=["sms", "email", "slack"]
            ),
            Severity.MEDIUM: SeverityRouting(
                severity=Severity.MEDIUM,
                channels=["email", "slack"]
            ),
            Severity.LOW: SeverityRouting(
                severity=Severity.LOW,
                channels=["email"]
            )
        }
    )


def create_immediate_page_policy(
    name: str = "Immediate Paging"
) -> EscalationPolicy:
    """Factory for immediate paging policy for critical alerts."""
    return EscalationPolicy(
        policy_id=uuid4(),
        name=name,
        description="Immediately page on-call for critical issues",
        levels=[
            EscalationLevel(
                level=1,
                name="Immediate Page",
                timeout_minutes=5,
                channels=["pagerduty", "sms", "phone"],
                recipients=["on-call"],
                require_ack=True
            ),
            EscalationLevel(
                level=2,
                name="Manager Escalation",
                timeout_minutes=15,
                channels=["pagerduty", "phone"],
                recipients=["on-call", "manager@company.com"],
                require_ack=True
            )
        ],
        severity_routing={
            Severity.CRITICAL: SeverityRouting(
                severity=Severity.CRITICAL,
                channels=["pagerduty", "phone"],
                immediate=True
            )
        }
    )


def create_business_hours_policy(
    name: str = "Business Hours Only"
) -> EscalationPolicy:
    """Factory for business hours only escalation."""
    return EscalationPolicy(
        policy_id=uuid4(),
        name=name,
        description="Only escalate during business hours",
        levels=[
            EscalationLevel(
                level=1,
                name="Business Hours Notification",
                timeout_minutes=30,
                channels=["email", "slack"],
                recipients=["on-call"],
                require_ack=True
            )
        ],
        global_timeout_minutes=480,  # 8 hours
        auto_resolve_after_minutes=1440  # 24 hours
    )


if __name__ == "__main__":
    # Demo usage
    engine = EscalationEngine()
    
    # Create on-call rotation
    rotation = OnCallRotation(
        rotation_id=uuid4(),
        name="Primary On-Call",
        description="Main production support rotation",
        members=[
            OnCallUser(
                user_id="user1",
                name="John Doe",
                email="john@dragonscope.io",
                phone="+1234567890",
                slack_id="@john"
            ),
            OnCallUser(
                user_id="user2",
                name="Jane Smith",
                email="jane@dragonscope.io",
                phone="+1234567891",
                slack_id="@jane"
            )
        ]
    )
    engine.add_rotation(rotation)
    
    # Create policy
    policy = create_basic_escalation_policy()
    policy.rotation_id = rotation.rotation_id
    engine.add_policy(policy)
    
    # Start escalation
    instance = engine.start_escalation(
        policy_id=policy.policy_id,
        alert_id=uuid4(),
        severity=Severity.HIGH,
        message="Production database latency high",
        symbol="INFRA"
    )
    
    if instance:
        print(f"Started escalation: {instance.escalation_id}")
        print(f"Current level: {instance.current_level}")
        print(f"Current on-call: {rotation.get_current_oncall().name}")
        
        # Simulate acknowledgment
        ack = engine.acknowledge(
            escalation_id=instance.escalation_id,
            user_id="user1",
            user_name="John Doe",
            message="Looking into it"
        )
        print(f"Acknowledged: {ack is not None}")
