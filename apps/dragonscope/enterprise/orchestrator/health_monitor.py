"""
DragonScope Enterprise - Health Monitor

Comprehensive health monitoring for all services with deep health checks,
health score calculation, automatic failover, and alerting.
"""

from __future__ import annotations

import asyncio
import enum
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Generic, TypeVar
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum

import aiohttp
import aioredis
import asyncpg
from aiohttp import ClientTimeout


logger = logging.getLogger("dragonscope.mso.health")


T = TypeVar('T')


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"       # Fully operational
    DEGRADED = "degraded"     # Partial functionality
    UNHEALTHY = "unhealthy"   # Critical issues
    DOWN = "down"            # Service unavailable
    UNKNOWN = "unknown"      # Status unknown


class CheckType(Enum):
    """Types of health checks."""
    HTTP = "http"
    TCP = "tcp"
    GRPC = "grpc"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    EXTERNAL_API = "external_api"
    CUSTOM = "custom"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_name: str
    check_type: CheckType
    status: HealthStatus
    response_time_ms: float
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    @property
    def is_healthy(self) -> bool:
        """Check if result indicates health."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


@dataclass
class ComponentHealth:
    """Health of a single component."""
    name: str
    status: HealthStatus
    health_score: float  # 0-100
    last_check: float
    check_results: list[HealthCheckResult] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "health_score": round(self.health_score, 2),
            "last_check": datetime.fromtimestamp(self.last_check).isoformat(),
            "checks": [
                {
                    "name": r.check_name,
                    "type": r.check_type.value,
                    "status": r.status.value,
                    "response_time_ms": round(r.response_time_ms, 2),
                    "message": r.message
                }
                for r in self.check_results
            ]
        }


@dataclass
class ServiceHealth:
    """Complete health status of a service."""
    service_name: str
    instance_id: str
    overall_status: HealthStatus
    health_score: float
    components: dict[str, ComponentHealth]
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service": self.service_name,
            "instance": self.instance_id,
            "status": self.overall_status.value,
            "health_score": round(self.health_score, 2),
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "metadata": self.metadata,
            "components": {
                name: comp.to_dict()
                for name, comp in self.components.items()
            }
        }


class HealthCheck(ABC):
    """Abstract base class for health checks."""
    
    def __init__(
        self,
        name: str,
        check_type: CheckType,
        timeout_seconds: float = 5.0,
        interval_seconds: float = 10.0,
        weight: float = 1.0
    ):
        self.name = name
        self.check_type = check_type
        self.timeout_seconds = timeout_seconds
        self.interval_seconds = interval_seconds
        self.weight = weight
        self.last_result: HealthCheckResult | None = None
    
    @abstractmethod
    async def execute(self) -> HealthCheckResult:
        """Execute the health check."""
        pass
    
    async def run(self) -> HealthCheckResult:
        """Run health check with timing."""
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                self.execute(),
                timeout=self.timeout_seconds
            )
            result.response_time_ms = (time.time() - start_time) * 1000
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=self.timeout_seconds * 1000,
                message="Health check timed out"
            )
        except Exception as e:
            result = HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.DOWN,
                response_time_ms=(time.time() - start_time) * 1000,
                message=str(e)
            )
        
        self.last_result = result
        return result


class HTTPHealthCheck(HealthCheck):
    """HTTP-based health check."""
    
    def __init__(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        timeout_seconds: float = 5.0,
        interval_seconds: float = 10.0,
        headers: dict[str, str] | None = None,
        expected_response: dict[str, Any] | None = None
    ):
        super().__init__(name, CheckType.HTTP, timeout_seconds, interval_seconds)
        self.url = url
        self.expected_status = expected_status
        self.headers = headers or {}
        self.expected_response = expected_response
        self._session: aiohttp.ClientSession | None = None
    
    async def execute(self) -> HealthCheckResult:
        """Execute HTTP health check."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=self.timeout_seconds)
            )
        
        start_time = time.time()
        async with self._session.get(self.url, headers=self.headers) as response:
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status != self.expected_status:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=response_time_ms,
                    message=f"Unexpected status code: {response.status}"
                )
            
            # Check response body if expected
            if self.expected_response:
                try:
                    body = await response.json()
                    for key, value in self.expected_response.items():
                        if body.get(key) != value:
                            return HealthCheckResult(
                                check_name=self.name,
                                check_type=self.check_type,
                                status=HealthStatus.DEGRADED,
                                response_time_ms=response_time_ms,
                                message=f"Response mismatch for key: {key}"
                            )
                except Exception as e:
                    return HealthCheckResult(
                        check_name=self.name,
                        check_type=self.check_type,
                        status=HealthStatus.DEGRADED,
                        response_time_ms=response_time_ms,
                        message=f"Failed to parse response: {e}"
                    )
            
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                message="HTTP check passed",
                details={"status_code": response.status}
            )


class DatabaseHealthCheck(HealthCheck):
    """Database connection health check."""
    
    def __init__(
        self,
        name: str,
        dsn: str,
        query: str = "SELECT 1",
        timeout_seconds: float = 5.0,
        interval_seconds: float = 10.0
    ):
        super().__init__(name, CheckType.DATABASE, timeout_seconds, interval_seconds)
        self.dsn = dsn
        self.query = query
    
    async def execute(self) -> HealthCheckResult:
        """Execute database health check."""
        start_time = time.time()
        conn = None
        
        try:
            conn = await asyncpg.connect(dsn=self.dsn, timeout=self.timeout_seconds)
            result = await conn.fetchval(self.query)
            response_time_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                message="Database check passed",
                details={"query_result": result}
            )
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.DOWN,
                response_time_ms=response_time_ms,
                message=f"Database check failed: {e}"
            )
        finally:
            if conn:
                await conn.close()


class CacheHealthCheck(HealthCheck):
    """Cache (Redis) health check."""
    
    def __init__(
        self,
        name: str,
        redis_url: str,
        timeout_seconds: float = 2.0,
        interval_seconds: float = 5.0
    ):
        super().__init__(name, CheckType.CACHE, timeout_seconds, interval_seconds)
        self.redis_url = redis_url
    
    async def execute(self) -> HealthCheckResult:
        """Execute cache health check."""
        start_time = time.time()
        redis = None
        
        try:
            redis = aioredis.from_url(self.redis_url, socket_timeout=self.timeout_seconds)
            
            # Test write/read
            test_key = f"health:{self.name}:{int(time.time())}"
            test_value = "ok"
            
            await redis.set(test_key, test_value, ex=10)
            result = await redis.get(test_key)
            await redis.delete(test_key)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if result and result.decode() == test_value:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    message="Cache check passed"
                )
            else:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time_ms,
                    message="Cache read/write mismatch"
                )
                
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.DOWN,
                response_time_ms=response_time_ms,
                message=f"Cache check failed: {e}"
            )
        finally:
            if redis:
                await redis.close()


class ExternalAPIHealthCheck(HealthCheck):
    """External API health check."""
    
    def __init__(
        self,
        name: str,
        url: str,
        timeout_seconds: float = 10.0,
        interval_seconds: float = 30.0,
        headers: dict[str, str] | None = None,
        critical: bool = False
    ):
        super().__init__(name, CheckType.EXTERNAL_API, timeout_seconds, interval_seconds)
        self.url = url
        self.headers = headers or {}
        self.critical = critical
        self._session: aiohttp.ClientSession | None = None
    
    async def execute(self) -> HealthCheckResult:
        """Execute external API health check."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=self.timeout_seconds)
            )
        
        start_time = time.time()
        
        try:
            async with self._session.get(self.url, headers=self.headers) as response:
                response_time_ms = (time.time() - start_time) * 1000
                
                if response.status < 500:
                    status = HealthStatus.HEALTHY if response.status < 400 else HealthStatus.DEGRADED
                    return HealthCheckResult(
                        check_name=self.name,
                        check_type=self.check_type,
                        status=status,
                        response_time_ms=response_time_ms,
                        message=f"External API responded with {response.status}"
                    )
                else:
                    return HealthCheckResult(
                        check_name=self.name,
                        check_type=self.check_type,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=response_time_ms,
                        message=f"External API error: {response.status}"
                    )
                    
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.DOWN if self.critical else HealthStatus.DEGRADED,
                response_time_ms=response_time_ms,
                message=f"External API unreachable: {e}"
            )


class CustomHealthCheck(HealthCheck):
    """Custom health check with user-provided function."""
    
    def __init__(
        self,
        name: str,
        check_func: Callable[[], Coroutine[Any, Any, HealthCheckResult]],
        timeout_seconds: float = 5.0,
        interval_seconds: float = 10.0
    ):
        super().__init__(name, CheckType.CUSTOM, timeout_seconds, interval_seconds)
        self.check_func = check_func
    
    async def execute(self) -> HealthCheckResult:
        """Execute custom health check."""
        return await self.check_func()


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    condition: str  # e.g., "health_score < 50"
    duration_seconds: float
    severity: str  # info, warning, critical
    message_template: str
    cooldown_seconds: float = 300.0
    
    def evaluate(self, health: ServiceHealth) -> bool:
        """Evaluate alert condition."""
        # Simple condition evaluation
        if "health_score" in self.condition:
            threshold = float(self.condition.split("<")[-1].strip())
            return health.health_score < threshold
        elif "status" in self.condition:
            if "down" in self.condition:
                return health.overall_status == HealthStatus.DOWN
            elif "unhealthy" in self.condition:
                return health.overall_status == HealthStatus.UNHEALTHY
        return False


class AlertManager:
    """Manages health alerts and notifications."""
    
    def __init__(self):
        self.rules: list[AlertRule] = []
        self.alert_history: list[dict[str, Any]] = []
        self.active_alerts: dict[str, dict[str, Any]] = {}
        self._handlers: list[Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = []
        self._last_alert_time: dict[str, float] = {}
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self.rules.append(rule)
    
    def on_alert(self, handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Register alert handler."""
        self._handlers.append(handler)
    
    async def evaluate(self, service_health: ServiceHealth) -> list[dict[str, Any]]:
        """Evaluate all alert rules against service health."""
        triggered = []
        
        for rule in self.rules:
            alert_key = f"{service_health.service_name}:{rule.name}"
            
            if rule.evaluate(service_health):
                # Check cooldown
                last_time = self._last_alert_time.get(alert_key, 0)
                if time.time() - last_time < rule.cooldown_seconds:
                    continue
                
                alert = {
                    "rule": rule.name,
                    "service": service_health.service_name,
                    "instance": service_health.instance_id,
                    "severity": rule.severity,
                    "message": rule.message_template.format(
                        service=service_health.service_name,
                        score=health.health_score,
                        status=health.overall_status.value
                    ),
                    "timestamp": datetime.utcnow().isoformat(),
                    "health": health.to_dict()
                }
                
                triggered.append(alert)
                self.active_alerts[alert_key] = alert
                self.alert_history.append(alert)
                self._last_alert_time[alert_key] = time.time()
                
                # Notify handlers
                for handler in self._handlers:
                    try:
                        await handler(alert)
                    except Exception as e:
                        logger.error(f"Alert handler error: {e}")
        
        return triggered


class FailoverManager:
    """Manages automatic failover for degraded services."""
    
    def __init__(self):
        self._failover_configs: dict[str, dict[str, Any]] = {}
        self._failover_handlers: dict[str, Callable[[str], Coroutine[Any, Any, bool]]] = {}
        self._failover_history: list[dict[str, Any]] = []
    
    def register_service(
        self,
        service_name: str,
        failover_config: dict[str, Any],
        handler: Callable[[str], Coroutine[Any, Any, bool]] | None = None
    ) -> None:
        """Register a service for failover management."""
        self._failover_configs[service_name] = failover_config
        if handler:
            self._failover_handlers[service_name] = handler
    
    async def evaluate_failover(self, service_name: str, health: ServiceHealth) -> bool:
        """Evaluate if failover is needed."""
        config = self._failover_configs.get(service_name)
        if not config:
            return False
        
        # Check health score threshold
        if health.health_score > config.get("min_health_score", 30):
            return False
        
        # Check consecutive failures
        # This would be tracked in a real implementation
        
        return True
    
    async def execute_failover(self, service_name: str, instance_id: str) -> bool:
        """Execute failover for a service instance."""
        logger.critical(f"Executing failover for {service_name}/{instance_id}")
        
        handler = self._failover_handlers.get(service_name)
        if handler:
            try:
                success = await handler(instance_id)
                self._failover_history.append({
                    "service": service_name,
                    "instance": instance_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": success
                })
                return success
            except Exception as e:
                logger.error(f"Failover failed for {service_name}: {e}")
                return False
        
        return False


class HealthMonitor:
    """
    Enterprise Health Monitor for DragonScope.
    
    Monitors all services with deep health checks, calculates health scores,
    manages automatic failover, and triggers alerts on degradation.
    """
    
    def __init__(self, check_interval_seconds: float = 10.0):
        self.check_interval = check_interval_seconds
        
        # Service registrations
        self._services: dict[str, dict[str, Any]] = {}
        self._health_checks: dict[str, list[HealthCheck]] = defaultdict(list)
        self._service_health: dict[str, ServiceHealth] = {}
        
        # Managers
        self.alert_manager = AlertManager()
        self.failover_manager = FailoverManager()
        
        # Running state
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        
        # Event handlers
        self._on_degradation: list[Callable[[str, ServiceHealth], Coroutine[Any, Any, None]]] = []
        self._on_recovery: list[Callable[[str, ServiceHealth], Coroutine[Any, Any, None]]] = []
        
        # Health history
        self._health_history: dict[str, list[ServiceHealth]] = defaultdict(list)
        self._max_history_size = 100
        
        logger.info("HealthMonitor initialized")
    
    async def start(self) -> None:
        """Start the health monitor."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("HealthMonitor started")
    
    async def stop(self) -> None:
        """Stop the health monitor."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("HealthMonitor stopped")
    
    def register_service(
        self,
        service_name: str,
        instance_id: str,
        health_checks: list[HealthCheck] | None = None,
        metadata: dict[str, Any] | None = None,
        failover_config: dict[str, Any] | None = None
    ) -> None:
        """
        Register a service for health monitoring.
        
        Args:
            service_name: Service name
            instance_id: Unique instance identifier
            health_checks: List of health checks to perform
            metadata: Service metadata
            failover_config: Failover configuration
        """
        service_key = f"{service_name}:{instance_id}"
        
        self._services[service_key] = {
            "name": service_name,
            "instance_id": instance_id,
            "metadata": metadata or {},
            "last_check": 0
        }
        
        if health_checks:
            self._health_checks[service_key] = health_checks
        
        if failover_config:
            self.failover_manager.register_service(service_name, failover_config)
        
        logger.info(f"Registered service for health monitoring: {service_key}")
    
    def add_health_check(self, service_name: str, instance_id: str, check: HealthCheck) -> None:
        """Add a health check to a service."""
        service_key = f"{service_name}:{instance_id}"
        self._health_checks[service_key].append(check)
    
    async def check_service(self, service_name: str, instance_id: str) -> ServiceHealth:
        """
        Run health checks for a specific service instance.
        
        Args:
            service_name: Service name
            instance_id: Instance identifier
        
        Returns:
            Service health status
        """
        service_key = f"{service_name}:{instance_id}"
        checks = self._health_checks.get(service_key, [])
        service_info = self._services.get(service_key, {})
        
        # Run all health checks
        component_results: dict[str, ComponentHealth] = {}
        
        for check in checks:
            result = await check.run()
            
            # Group by component (using check type as component name for simplicity)
            component_name = check.check_type.value
            if component_name not in component_results:
                component_results[component_name] = ComponentHealth(
                    name=component_name,
                    status=HealthStatus.UNKNOWN,
                    health_score=100.0,
                    last_check=time.time()
                )
            
            component_results[component_name].check_results.append(result)
        
        # Calculate component health
        for component in component_results.values():
            component.health_score = self._calculate_component_score(component.check_results)
            component.status = self._score_to_status(component.health_score)
        
        # Calculate overall health
        overall_score = self._calculate_overall_score(list(component_results.values()))
        overall_status = self._score_to_status(overall_score)
        
        health = ServiceHealth(
            service_name=service_name,
            instance_id=instance_id,
            overall_status=overall_status,
            health_score=overall_score,
            components=component_results,
            metadata=service_info.get("metadata", {})
        )
        
        # Store health
        self._service_health[service_key] = health
        self._health_history[service_key].append(health)
        
        # Trim history
        if len(self._health_history[service_key]) > self._max_history_size:
            self._health_history[service_key] = self._health_history[service_key][-self._max_history_size:]
        
        # Update last check time
        if service_key in self._services:
            self._services[service_key]["last_check"] = time.time()
        
        # Check for degradation/recovery
        await self._handle_state_change(service_key, health)
        
        # Evaluate alerts
        await self.alert_manager.evaluate(health)
        
        # Evaluate failover
        if await self.failover_manager.evaluate_failover(service_name, health):
            await self.failover_manager.execute_failover(service_name, instance_id)
        
        return health
    
    def _calculate_component_score(self, results: list[HealthCheckResult]) -> float:
        """Calculate health score from check results."""
        if not results:
            return 100.0
        
        total_weight = sum(r.check.weight for r in results)
        if total_weight == 0:
            return 100.0
        
        score = 0.0
        for result in results:
            weight = result.check.weight / total_weight
            
            if result.status == HealthStatus.HEALTHY:
                score += 100 * weight
            elif result.status == HealthStatus.DEGRADED:
                score += 50 * weight
            elif result.status == HealthStatus.UNHEALTHY:
                score += 10 * weight
            else:
                score += 0
        
        return max(0, min(100, score))
    
    def _calculate_overall_score(self, components: list[ComponentHealth]) -> float:
        """Calculate overall health score from components."""
        if not components:
            return 100.0
        
        # Weight by criticality (simplified - would be configurable)
        critical_components = {"database", "cache"}
        
        total_score = 0.0
        total_weight = 0.0
        
        for component in components:
            weight = 2.0 if component.name in critical_components else 1.0
            total_score += component.health_score * weight
            total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 100.0
    
    def _score_to_status(self, score: float) -> HealthStatus:
        """Convert health score to status."""
        if score >= 80:
            return HealthStatus.HEALTHY
        elif score >= 50:
            return HealthStatus.DEGRADED
        elif score >= 20:
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DOWN
    
    async def _handle_state_change(self, service_key: str, health: ServiceHealth) -> None:
        """Handle health state changes."""
        history = self._health_history.get(service_key, [])
        if len(history) < 2:
            return
        
        previous = history[-2]
        
        # Detect degradation
        if previous.overall_status == HealthStatus.HEALTHY and \
           health.overall_status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.DOWN):
            logger.warning(f"Service degraded: {service_key} (score: {health.health_score:.1f})")
            for handler in self._on_degradation:
                try:
                    await handler(service_key, health)
                except Exception as e:
                    logger.error(f"Degradation handler error: {e}")
        
        # Detect recovery
        elif previous.overall_status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.DOWN) and \
             health.overall_status == HealthStatus.HEALTHY:
            logger.info(f"Service recovered: {service_key} (score: {health.health_score:.1f})")
            for handler in self._on_recovery:
                try:
                    await handler(service_key, health)
                except Exception as e:
                    logger.error(f"Recovery handler error: {e}")
    
    async def _monitor_loop(self) -> None:
        """Background health monitoring loop."""
        while self._running:
            try:
                await self._run_all_checks()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    async def _run_all_checks(self) -> None:
        """Run health checks for all registered services."""
        tasks = []
        
        for service_key, service_info in self._services.items():
            # Check if it's time to run checks for this service
            last_check = service_info.get("last_check", 0)
            
            # Stagger checks to avoid thundering herd
            task = asyncio.create_task(
                self.check_service(
                    service_info["name"],
                    service_info["instance_id"]
                ),
                name=f"health-check-{service_key}"
            )
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_health(self, service_name: str, instance_id: str) -> ServiceHealth | None:
        """Get current health for a service instance."""
        service_key = f"{service_name}:{instance_id}"
        return self._service_health.get(service_key)
    
    def get_health_score(self, service_name: str, instance_id: str) -> float:
        """Get health score for a service instance."""
        health = self.get_health(service_name, instance_id)
        return health.health_score if health else 0.0
    
    def get_all_health(self) -> dict[str, ServiceHealth]:
        """Get health for all services."""
        return dict(self._service_health)
    
    def get_service_health(self, service_name: str) -> list[ServiceHealth]:
        """Get health for all instances of a service."""
        return [
            health for key, health in self._service_health.items()
            if health.service_name == service_name
        ]
    
    def get_health_history(
        self,
        service_name: str,
        instance_id: str,
        limit: int = 100
    ) -> list[ServiceHealth]:
        """Get health history for a service instance."""
        service_key = f"{service_name}:{instance_id}"
        history = self._health_history.get(service_key, [])
        return history[-limit:] if limit > 0 else history
    
    def on_degradation(
        self,
        handler: Callable[[str, ServiceHealth], Coroutine[Any, Any, None]]
    ) -> None:
        """Register handler for service degradation events."""
        self._on_degradation.append(handler)
    
    def on_recovery(
        self,
        handler: Callable[[str, ServiceHealth], Coroutine[Any, Any, None]]
    ) -> None:
        """Register handler for service recovery events."""
        self._on_recovery.append(handler)
    
    def get_summary(self) -> dict[str, Any]:
        """Get health summary for all services."""
        total = len(self._service_health)
        healthy = sum(1 for h in self._service_health.values() if h.overall_status == HealthStatus.HEALTHY)
        degraded = sum(1 for h in self._service_health.values() if h.overall_status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for h in self._service_health.values() if h.overall_status == HealthStatus.UNHEALTHY)
        down = sum(1 for h in self._service_health.values() if h.overall_status == HealthStatus.DOWN)
        
        return {
            "total_services": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "down": down,
            "health_percentage": (healthy / total * 100) if total > 0 else 0,
            "services": {
                key: health.to_dict()
                for key, health in self._service_health.items()
            }
        }


# Singleton instance
_health_monitor_instance: HealthMonitor | None = None


def get_health_monitor() -> HealthMonitor:
    """Get singleton HealthMonitor instance."""
    global _health_monitor_instance
    if _health_monitor_instance is None:
        _health_monitor_instance = HealthMonitor()
    return _health_monitor_instance


def set_health_monitor(monitor: HealthMonitor) -> None:
    """Set singleton HealthMonitor instance."""
    global _health_monitor_instance
    _health_monitor_instance = monitor
