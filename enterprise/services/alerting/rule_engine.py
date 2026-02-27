"""
DragonScope Enterprise Alerting - Rule Engine

A sophisticated rule engine for financial market alert detection.
Supports threshold, anomaly, pattern, and composite rule types
with time-based conditions and multi-condition logic.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4
import hashlib

import numpy as np
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RuleType(str, Enum):
    """Types of alert rules."""
    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    COMPOSITE = "composite"


class Operator(str, Enum):
    """Comparison operators for threshold rules."""
    GT = "gt"  # greater than
    GTE = "gte"  # greater than or equal
    LT = "lt"  # less than
    LTE = "lte"  # less than or equal
    EQ = "eq"  # equal
    NEQ = "neq"  # not equal
    BETWEEN = "between"  # within range
    OUTSIDE = "outside"  # outside range


class LogicOperator(str, Enum):
    """Logical operators for composite rules."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class AnomalyMethod(str, Enum):
    """Methods for anomaly detection."""
    ZSCORE = "zscore"
    IQR = "iqr"
    MAD = "mad"  # Median Absolute Deviation
    PERCENTILE = "percentile"


class PatternType(str, Enum):
    """Technical pattern types."""
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    TRIANGLE_ASCENDING = "triangle_ascending"
    TRIANGLE_DESCENDING = "triangle_descending"
    FLAG_BULL = "flag_bull"
    FLAG_BEAR = "flag_bear"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"


class Severity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MarketHours:
    """Market hours configuration."""
    timezone: str = "America/New_York"
    pre_market_start: time = field(default_factory=lambda: time(4, 0))
    market_open: time = field(default_factory=lambda: time(9, 30))
    market_close: time = field(default_factory=lambda: time(16, 0))
    after_hours_end: time = field(default_factory=lambda: time(20, 0))
    
    # Trading days (0=Monday, 6=Sunday)
    trading_days: Set[int] = field(default_factory=lambda: {0, 1, 2, 3, 4})
    
    def is_trading_day(self, dt: datetime) -> bool:
        """Check if given datetime is a trading day."""
        return dt.weekday() in self.trading_days
    
    def is_market_hours(self, dt: datetime) -> bool:
        """Check if given datetime is within market hours."""
        if not self.is_trading_day(dt):
            return False
        t = dt.time()
        return self.market_open <= t <= self.market_close
    
    def is_extended_hours(self, dt: datetime) -> bool:
        """Check if given datetime is within extended hours."""
        if not self.is_trading_day(dt):
            return False
        t = dt.time()
        return (self.pre_market_start <= t < self.market_open or
                self.market_close < t <= self.after_hours_end)


@dataclass
class RuleVersion:
    """Rule version information."""
    version_id: UUID
    rule_id: UUID
    version_number: int
    created_at: datetime
    created_by: str
    changes: Dict[str, Any]
    rule_snapshot: Dict[str, Any]
    is_active: bool = True


@dataclass
class AlertEvent:
    """Represents a triggered alert event."""
    alert_id: UUID
    rule_id: UUID
    rule_name: str
    rule_type: RuleType
    severity: Severity
    symbol: Optional[str]
    message: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": str(self.alert_id),
            "rule_id": str(self.rule_id),
            "rule_name": self.rule_name,
            "rule_type": self.rule_type.value,
            "severity": self.severity.value,
            "symbol": self.symbol,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata
        }


class RuleCondition(ABC):
    """Abstract base class for rule conditions."""
    
    @abstractmethod
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate the condition against data."""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize condition to dictionary."""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuleCondition:
        """Deserialize condition from dictionary."""
        pass


@dataclass
class ThresholdCondition(RuleCondition):
    """Threshold-based condition."""
    metric: str
    operator: Operator
    value: Union[float, Tuple[float, float]]
    symbol: Optional[str] = None
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate threshold condition."""
        # Get metric value
        if self.symbol:
            symbol_data = data.get(self.symbol, {})
            actual_value = symbol_data.get(self.metric)
        else:
            actual_value = data.get(self.metric)
        
        if actual_value is None:
            logger.warning(f"Metric '{self.metric}' not found in data")
            return False
        
        try:
            actual_value = float(actual_value)
        except (TypeError, ValueError):
            logger.warning(f"Cannot convert metric value to float: {actual_value}")
            return False
        
        # Apply operator
        if self.operator == Operator.GT:
            return actual_value > self.value
        elif self.operator == Operator.GTE:
            return actual_value >= self.value
        elif self.operator == Operator.LT:
            return actual_value < self.value
        elif self.operator == Operator.LTE:
            return actual_value <= self.value
        elif self.operator == Operator.EQ:
            return actual_value == self.value
        elif self.operator == Operator.NEQ:
            return actual_value != self.value
        elif self.operator == Operator.BETWEEN:
            low, high = self.value
            return low <= actual_value <= high
        elif self.operator == Operator.OUTSIDE:
            low, high = self.value
            return actual_value < low or actual_value > high
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "operator": self.operator.value,
            "value": self.value,
            "symbol": self.symbol
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ThresholdCondition:
        return cls(
            metric=data["metric"],
            operator=Operator(data["operator"]),
            value=data["value"],
            symbol=data.get("symbol")
        )


@dataclass
class AnomalyCondition(RuleCondition):
    """Anomaly detection condition."""
    metric: str
    method: AnomalyMethod
    threshold: float
    window: str  # e.g., "30d", "1h"
    symbol: Optional[str] = None
    historical_data: List[float] = field(default_factory=list)
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate anomaly condition."""
        if not self.historical_data:
            logger.warning("No historical data for anomaly detection")
            return False
        
        # Get current value
        if self.symbol:
            symbol_data = data.get(self.symbol, {})
            current = symbol_data.get(self.metric)
        else:
            current = data.get(self.metric)
        
        if current is None:
            return False
        
        current = float(current)
        history = np.array(self.historical_data)
        
        if self.method == AnomalyMethod.ZSCORE:
            mean = np.mean(history)
            std = np.std(history)
            if std == 0:
                return False
            zscore = abs(current - mean) / std
            return zscore > self.threshold
        
        elif self.method == AnomalyMethod.IQR:
            q1 = np.percentile(history, 25)
            q3 = np.percentile(history, 75)
            iqr = q3 - q1
            lower = q1 - self.threshold * iqr
            upper = q3 + self.threshold * iqr
            return current < lower or current > upper
        
        elif self.method == AnomalyMethod.MAD:
            median = np.median(history)
            mad = np.median(np.abs(history - median))
            if mad == 0:
                return False
            modified_zscore = 0.6745 * (current - median) / mad
            return abs(modified_zscore) > self.threshold
        
        elif self.method == AnomalyMethod.PERCENTILE:
            lower = np.percentile(history, self.threshold)
            upper = np.percentile(history, 100 - self.threshold)
            return current < lower or current > upper
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "method": self.method.value,
            "threshold": self.threshold,
            "window": self.window,
            "symbol": self.symbol,
            "historical_data": self.historical_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AnomalyCondition:
        return cls(
            metric=data["metric"],
            method=AnomalyMethod(data["method"]),
            threshold=data["threshold"],
            window=data["window"],
            symbol=data.get("symbol"),
            historical_data=data.get("historical_data", [])
        )


@dataclass
class PatternCondition(RuleCondition):
    """Pattern detection condition."""
    pattern: PatternType
    timeframe: str
    confirmation: str = "close"
    symbol: Optional[str] = None
    min_confidence: float = 0.7
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate pattern condition."""
        if self.symbol:
            symbol_data = data.get(self.symbol, {})
            pattern_data = symbol_data.get("patterns", {})
        else:
            pattern_data = data.get("patterns", {})
        
        detected_pattern = pattern_data.get("pattern_type")
        confidence = pattern_data.get("confidence", 0)
        
        if detected_pattern != self.pattern.value:
            return False
        
        return confidence >= self.min_confidence
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "timeframe": self.timeframe,
            "confirmation": self.confirmation,
            "symbol": self.symbol,
            "min_confidence": self.min_confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PatternCondition:
        return cls(
            pattern=PatternType(data["pattern"]),
            timeframe=data["timeframe"],
            confirmation=data.get("confirmation", "close"),
            symbol=data.get("symbol"),
            min_confidence=data.get("min_confidence", 0.7)
        )


@dataclass
class CompositeCondition(RuleCondition):
    """Composite condition with logical operators."""
    operator: LogicOperator
    conditions: List[RuleCondition]
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate composite condition."""
        if not self.conditions:
            return False
        
        if self.operator == LogicOperator.AND:
            return all(c.evaluate(data) for c in self.conditions)
        elif self.operator == LogicOperator.OR:
            return any(c.evaluate(data) for c in self.conditions)
        elif self.operator == LogicOperator.NOT:
            return not self.conditions[0].evaluate(data) if self.conditions else False
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator": self.operator.value,
            "conditions": [c.to_dict() for c in self.conditions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CompositeCondition:
        conditions = []
        for c_data in data.get("conditions", []):
            c_type = c_data.get("type", "threshold")
            if c_type == "threshold":
                conditions.append(ThresholdCondition.from_dict(c_data))
            elif c_type == "anomaly":
                conditions.append(AnomalyCondition.from_dict(c_data))
            elif c_type == "pattern":
                conditions.append(PatternCondition.from_dict(c_data))
            elif c_type == "composite":
                conditions.append(CompositeCondition.from_dict(c_data))
        
        return cls(
            operator=LogicOperator(data["operator"]),
            conditions=conditions
        )


@dataclass
class TimeRestriction:
    """Time-based restrictions for rule evaluation."""
    market_hours_only: bool = False
    extended_hours: bool = False
    timezone: str = "America/New_York"
    specific_hours: Optional[Tuple[time, time]] = None
    specific_days: Optional[Set[int]] = None
    
    def is_allowed(self, dt: datetime) -> bool:
        """Check if evaluation is allowed at given time."""
        market_hours = MarketHours(timezone=self.timezone)
        
        if self.market_hours_only and not market_hours.is_market_hours(dt):
            return False
        
        if self.extended_hours and not (
            market_hours.is_market_hours(dt) or 
            market_hours.is_extended_hours(dt)
        ):
            return False
        
        if self.specific_hours:
            start, end = self.specific_hours
            if not (start <= dt.time() <= end):
                return False
        
        if self.specific_days and dt.weekday() not in self.specific_days:
            return False
        
        return True


@dataclass
class AlertRule:
    """Alert rule definition."""
    rule_id: UUID
    name: str
    description: str
    rule_type: RuleType
    condition: RuleCondition
    severity: Severity
    symbol: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    cooldown_minutes: int = 5
    time_restriction: Optional[TimeRestriction] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Versioning
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"
    
    # Runtime state
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    
    def is_on_cooldown(self) -> bool:
        """Check if rule is on cooldown."""
        if self.last_triggered is None:
            return False
        cooldown_end = self.last_triggered + timedelta(minutes=self.cooldown_minutes)
        return datetime.utcnow() < cooldown_end
    
    def can_trigger(self, dt: Optional[datetime] = None) -> bool:
        """Check if rule can trigger at given time."""
        if not self.enabled:
            return False
        
        if self.is_on_cooldown():
            return False
        
        if self.time_restriction:
            check_time = dt or datetime.utcnow()
            if not self.time_restriction.is_allowed(check_time):
                return False
        
        return True
    
    def evaluate(self, data: Dict[str, Any]) -> Optional[AlertEvent]:
        """Evaluate rule against data."""
        if not self.can_trigger():
            return None
        
        if self.condition.evaluate(data):
            self.last_triggered = datetime.utcnow()
            self.trigger_count += 1
            
            # Build alert message
            message = self._build_message(data)
            
            return AlertEvent(
                alert_id=uuid4(),
                rule_id=self.rule_id,
                rule_name=self.name,
                rule_type=self.rule_type,
                severity=self.severity,
                symbol=self.symbol,
                message=message,
                timestamp=datetime.utcnow(),
                data=data
            )
        
        return None
    
    def _build_message(self, data: Dict[str, Any]) -> str:
        """Build alert message from template."""
        templates = {
            RuleType.THRESHOLD: f"Threshold alert: {self.name} triggered",
            RuleType.ANOMALY: f"Anomaly detected: {self.name}",
            RuleType.PATTERN: f"Pattern identified: {self.name}",
            RuleType.COMPOSITE: f"Composite rule triggered: {self.name}"
        }
        return templates.get(self.rule_type, f"Alert: {self.name}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize rule to dictionary."""
        return {
            "rule_id": str(self.rule_id),
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type.value,
            "condition": self.condition.to_dict(),
            "severity": self.severity.value,
            "symbol": self.symbol,
            "tags": self.tags,
            "enabled": self.enabled,
            "cooldown_minutes": self.cooldown_minutes,
            "time_restriction": {
                "market_hours_only": self.time_restriction.market_hours_only,
                "extended_hours": self.time_restriction.extended_hours,
                "timezone": self.time_restriction.timezone
            } if self.time_restriction else None,
            "metadata": self.metadata,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "trigger_count": self.trigger_count
        }


class RuleEngine:
    """Main rule engine for alert processing."""
    
    def __init__(self):
        self.rules: Dict[UUID, AlertRule] = {}
        self.versions: Dict[UUID, List[RuleVersion]] = {}
        self.alert_handlers: List[Callable[[AlertEvent], None]] = []
        self.running = False
        self._lock = asyncio.Lock()
    
    def register_handler(self, handler: Callable[[AlertEvent], None]) -> None:
        """Register an alert event handler."""
        self.alert_handlers.append(handler)
    
    def add_rule(
        self,
        name: str,
        description: str,
        rule_type: RuleType,
        condition: RuleCondition,
        severity: Severity = Severity.MEDIUM,
        symbol: Optional[str] = None,
        tags: Optional[List[str]] = None,
        cooldown_minutes: int = 5,
        time_restriction: Optional[TimeRestriction] = None,
        created_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AlertRule:
        """Add a new alert rule."""
        rule_id = uuid4()
        
        rule = AlertRule(
            rule_id=rule_id,
            name=name,
            description=description,
            rule_type=rule_type,
            condition=condition,
            severity=severity,
            symbol=symbol,
            tags=tags or [],
            cooldown_minutes=cooldown_minutes,
            time_restriction=time_restriction,
            created_by=created_by,
            metadata=metadata or {}
        )
        
        self.rules[rule_id] = rule
        
        # Create initial version
        version = RuleVersion(
            version_id=uuid4(),
            rule_id=rule_id,
            version_number=1,
            created_at=datetime.utcnow(),
            created_by=created_by,
            changes={"action": "created"},
            rule_snapshot=rule.to_dict()
        )
        self.versions[rule_id] = [version]
        
        logger.info(f"Created rule '{name}' ({rule_id}) of type {rule_type.value}")
        return rule
    
    def update_rule(
        self,
        rule_id: UUID,
        changes: Dict[str, Any],
        updated_by: str = "system"
    ) -> Optional[AlertRule]:
        """Update an existing rule and create new version."""
        if rule_id not in self.rules:
            return None
        
        rule = self.rules[rule_id]
        old_snapshot = rule.to_dict()
        
        # Apply changes
        for key, value in changes.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        rule.version += 1
        rule.updated_at = datetime.utcnow()
        
        # Create new version
        versions = self.versions.get(rule_id, [])
        version = RuleVersion(
            version_id=uuid4(),
            rule_id=rule_id,
            version_number=rule.version,
            created_at=datetime.utcnow(),
            created_by=updated_by,
            changes=changes,
            rule_snapshot=rule.to_dict()
        )
        versions.append(version)
        self.versions[rule_id] = versions
        
        logger.info(f"Updated rule '{rule.name}' to version {rule.version}")
        return rule
    
    def delete_rule(self, rule_id: UUID) -> bool:
        """Delete a rule."""
        if rule_id in self.rules:
            rule = self.rules.pop(rule_id)
            # Keep versions for audit trail
            logger.info(f"Deleted rule '{rule.name}' ({rule_id})")
            return True
        return False
    
    def get_rule(self, rule_id: UUID) -> Optional[AlertRule]:
        """Get a rule by ID."""
        return self.rules.get(rule_id)
    
    def get_rules(
        self,
        symbol: Optional[str] = None,
        rule_type: Optional[RuleType] = None,
        severity: Optional[Severity] = None,
        tags: Optional[List[str]] = None,
        enabled_only: bool = False
    ) -> List[AlertRule]:
        """Get rules with optional filtering."""
        result = list(self.rules.values())
        
        if symbol:
            result = [r for r in result if r.symbol == symbol]
        
        if rule_type:
            result = [r for r in result if r.rule_type == rule_type]
        
        if severity:
            result = [r for r in result if r.severity == severity]
        
        if tags:
            result = [r for r in result if any(t in r.tags for t in tags)]
        
        if enabled_only:
            result = [r for r in result if r.enabled]
        
        return result
    
    def get_rule_versions(self, rule_id: UUID) -> List[RuleVersion]:
        """Get version history for a rule."""
        return self.versions.get(rule_id, [])
    
    def evaluate_all(self, data: Dict[str, Any]) -> List[AlertEvent]:
        """Evaluate all rules against data."""
        alerts = []
        
        for rule in self.rules.values():
            try:
                alert = rule.evaluate(data)
                if alert:
                    alerts.append(alert)
                    # Notify handlers
                    for handler in self.alert_handlers:
                        try:
                            handler(alert)
                        except Exception as e:
                            logger.error(f"Handler error: {e}")
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
        
        return alerts
    
    def evaluate_symbol(self, symbol: str, data: Dict[str, Any]) -> List[AlertEvent]:
        """Evaluate rules for a specific symbol."""
        symbol_rules = self.get_rules(symbol=symbol)
        alerts = []
        
        for rule in symbol_rules:
            try:
                alert = rule.evaluate(data)
                if alert:
                    alerts.append(alert)
                    for handler in self.alert_handlers:
                        try:
                            handler(alert)
                        except Exception as e:
                            logger.error(f"Handler error: {e}")
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
        
        return alerts
    
    async def start_stream_processor(self, data_stream):
        """Start processing a data stream."""
        self.running = True
        logger.info("Rule engine stream processor started")
        
        while self.running:
            try:
                data = await data_stream.get()
                if data is None:
                    break
                
                self.evaluate_all(data)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream processing error: {e}")
    
    def stop(self):
        """Stop the rule engine."""
        self.running = False
        logger.info("Rule engine stopped")
    
    def enable_rule(self, rule_id: UUID) -> bool:
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: UUID) -> bool:
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False


# Factory functions for common rule types

def create_price_threshold_rule(
    symbol: str,
    threshold: float,
    direction: str = "above",
    severity: Severity = Severity.HIGH
) -> Tuple[AlertRule, RuleEngine]:
    """Factory function to create a price threshold rule."""
    engine = RuleEngine()
    
    operator = Operator.GT if direction == "above" else Operator.LT
    condition = ThresholdCondition(
        metric="price",
        operator=operator,
        value=threshold,
        symbol=symbol
    )
    
    rule = engine.add_rule(
        name=f"{symbol} Price {direction} ${threshold}",
        description=f"Alert when {symbol} price goes {direction} ${threshold}",
        rule_type=RuleType.THRESHOLD,
        condition=condition,
        severity=severity,
        symbol=symbol,
        tags=["price", symbol, direction]
    )
    
    return rule, engine


def create_volume_spike_rule(
    symbol: str,
    multiplier: float = 2.0,
    window: str = "30d"
) -> Tuple[AlertRule, RuleEngine]:
    """Factory function to create a volume spike rule."""
    engine = RuleEngine()
    
    condition = AnomalyCondition(
        metric="volume",
        method=AnomalyMethod.ZSCORE,
        threshold=multiplier,
        window=window,
        symbol=symbol
    )
    
    rule = engine.add_rule(
        name=f"{symbol} Volume Spike",
        description=f"Alert when {symbol} volume exceeds {multiplier}x normal",
        rule_type=RuleType.ANOMALY,
        condition=condition,
        severity=Severity.MEDIUM,
        symbol=symbol,
        tags=["volume", "anomaly", symbol]
    )
    
    return rule, engine


def create_breakout_rule(
    symbol: str,
    pattern: PatternType = PatternType.BREAKOUT,
    severity: Severity = Severity.HIGH
) -> Tuple[AlertRule, RuleEngine]:
    """Factory function to create a breakout pattern rule."""
    engine = RuleEngine()
    
    condition = PatternCondition(
        pattern=pattern,
        timeframe="1d",
        confirmation="close",
        symbol=symbol
    )
    
    rule = engine.add_rule(
        name=f"{symbol} {pattern.value.replace('_', ' ').title()}",
        description=f"Detect {pattern.value} pattern for {symbol}",
        rule_type=RuleType.PATTERN,
        condition=condition,
        severity=severity,
        symbol=symbol,
        tags=["pattern", pattern.value, symbol]
    )
    
    return rule, engine


def create_rsi_extreme_rule(
    symbol: str,
    overbought: float = 70.0,
    oversold: float = 30.0
) -> Tuple[List[AlertRule], RuleEngine]:
    """Factory function to create RSI overbought/oversold rules."""
    engine = RuleEngine()
    rules = []
    
    # Overbought rule
    overbought_condition = ThresholdCondition(
        metric="rsi",
        operator=Operator.GT,
        value=overbought,
        symbol=symbol
    )
    
    rules.append(engine.add_rule(
        name=f"{symbol} RSI Overbought",
        description=f"Alert when {symbol} RSI exceeds {overbought}",
        rule_type=RuleType.THRESHOLD,
        condition=overbought_condition,
        severity=Severity.MEDIUM,
        symbol=symbol,
        tags=["rsi", "overbought", symbol]
    ))
    
    # Oversold rule
    oversold_condition = ThresholdCondition(
        metric="rsi",
        operator=Operator.LT,
        value=oversold,
        symbol=symbol
    )
    
    rules.append(engine.add_rule(
        name=f"{symbol} RSI Oversold",
        description=f"Alert when {symbol} RSI falls below {oversold}",
        rule_type=RuleType.THRESHOLD,
        condition=oversold_condition,
        severity=Severity.MEDIUM,
        symbol=symbol,
        tags=["rsi", "oversold", symbol]
    ))
    
    return rules, engine


if __name__ == "__main__":
    # Demo usage
    engine = RuleEngine()
    
    # Create sample rules
    condition = ThresholdCondition(
        metric="price",
        operator=Operator.GT,
        value=150.0,
        symbol="AAPL"
    )
    
    rule = engine.add_rule(
        name="AAPL Price Above $150",
        description="Alert when AAPL exceeds $150",
        rule_type=RuleType.THRESHOLD,
        condition=condition,
        severity=Severity.HIGH,
        symbol="AAPL",
        tags=["price", "AAPL"]
    )
    
    # Test evaluation
    test_data = {
        "AAPL": {
            "price": 155.0,
            "volume": 1000000
        }
    }
    
    alerts = engine.evaluate_all(test_data)
    for alert in alerts:
        print(f"Alert: {alert.message}")
        print(f"  Severity: {alert.severity.value}")
        print(f"  Data: {alert.data}")
