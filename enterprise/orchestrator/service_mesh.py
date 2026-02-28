"""
DragonScope Enterprise - Service Mesh

Enterprise-grade service mesh implementation with service discovery,
load balancing, health checking, circuit breaking, and retry policies.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Generic, TypeVar
from collections import defaultdict
from contextlib import asynccontextmanager

import aiohttp
import consul.aio
from aiohttp import ClientTimeout, ClientSession


logger = logging.getLogger("dragonscope.mso.mesh")


T = TypeVar('T')


class LoadBalanceStrategy(Enum):
    """Load balancing algorithms."""
    ROUND_ROBIN = auto()
    WEIGHTED_ROUND_ROBIN = auto()
    LEAST_CONNECTIONS = auto()
    CONSISTENT_HASH = auto()
    LATENCY_BASED = auto()
    RANDOM = auto()


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


class ServiceStatus(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    """Represents a single service instance."""
    id: str
    name: str
    host: str
    port: int
    metadata: dict[str, Any] = field(default_factory=dict)
    weight: int = 1
    status: ServiceStatus = ServiceStatus.UNKNOWN
    health_score: float = 100.0
    last_heartbeat: float = field(default_factory=time.time)
    connection_count: int = 0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    tags: list[str] = field(default_factory=list)
    
    @property
    def address(self) -> str:
        """Full service address."""
        return f"{self.host}:{self.port}"
    
    @property
    def url(self) -> str:
        """Service URL."""
        scheme = "https" if self.metadata.get("tls", False) else "http"
        return f"{scheme}://{self.address}"
    
    def is_healthy(self) -> bool:
        """Check if instance is healthy."""
        return self.status == ServiceStatus.HEALTHY
    
    def update_latency(self, latency_ms: float) -> None:
        """Update average latency using EWMA."""
        alpha = 0.2  # Smoothing factor
        self.avg_latency_ms = alpha * latency_ms + (1 - alpha) * self.avg_latency_ms


@dataclass
class RetryPolicy:
    """Retry configuration."""
    max_retries: int = 3
    base_delay: float = 0.1  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    retryable_statuses: set[int] = field(default_factory=lambda: {408, 429, 500, 502, 503, 504})
    retryable_exceptions: set[type[Exception]] = field(
        default_factory=lambda: {asyncio.TimeoutError, aiohttp.ClientError}
    )
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with jitter."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        # Add jitter (±20%)
        jitter = delay * 0.2 * (2 * random.random() - 1)
        return delay + jitter


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: float = 30.0
    half_open_max_calls: int = 2
    slow_call_threshold_ms: float = 1000.0
    slow_call_rate_threshold: float = 50.0  # percentage


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time: float | None = None
        self.lock = asyncio.Lock()
        self.total_calls = 0
        self.slow_calls = 0
        
    async def call(self, func: Callable[..., Coroutine[Any, Any, T]], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info(f"Circuit {self.name}: Transitioning to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(f"Circuit {self.name} is OPEN")
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(f"Circuit {self.name} HALF_OPEN limit reached")
                self.half_open_calls += 1
        
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            await self._on_success(time.time() - start_time)
            return result
        except Exception as e:
            await self._on_failure(time.time() - start_time)
            raise
    
    async def _on_success(self, duration: float) -> None:
        """Handle successful call."""
        async with self.lock:
            self.total_calls += 1
            if duration > self.config.slow_call_threshold_ms / 1000:
                self.slow_calls += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._close_circuit()
            else:
                self.failure_count = max(0, self.failure_count - 1)
    
    async def _on_failure(self, duration: float) -> None:
        """Handle failed call."""
        async with self.lock:
            self.total_calls += 1
            if duration > self.config.slow_call_threshold_ms / 1000:
                self.slow_calls += 1
            
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self._open_circuit()
            elif self.failure_count >= self.config.failure_threshold:
                self._open_circuit()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.timeout_seconds
    
    def _open_circuit(self) -> None:
        """Open the circuit."""
        self.state = CircuitState.OPEN
        self.failure_count = 0
        self.success_count = 0
        logger.warning(f"Circuit {self.name}: Transitioning to OPEN")
    
    def _close_circuit(self) -> None:
        """Close the circuit."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        logger.info(f"Circuit {self.name}: Transitioning to CLOSED")
    
    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics."""
        slow_rate = (self.slow_calls / self.total_calls * 100) if self.total_calls > 0 else 0
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "slow_calls": self.slow_calls,
            "slow_call_rate": slow_rate,
            "last_failure_time": self.last_failure_time
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class LoadBalancer(ABC):
    """Abstract base class for load balancers."""
    
    @abstractmethod
    def select(self, instances: list[ServiceInstance], context: dict[str, Any] | None = None) -> ServiceInstance | None:
        """Select an instance from the list."""
        pass


class RoundRobinBalancer(LoadBalancer):
    """Round-robin load balancer."""
    
    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
    
    def select(self, instances: list[ServiceInstance], context: dict[str, Any] | None = None) -> ServiceInstance | None:
        healthy = [i for i in instances if i.is_healthy()]
        if not healthy:
            return None
        
        service_name = healthy[0].name
        index = self._counters[service_name] % len(healthy)
        self._counters[service_name] += 1
        return healthy[index]


class WeightedRoundRobinBalancer(LoadBalancer):
    """Weighted round-robin load balancer."""
    
    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
    
    def select(self, instances: list[ServiceInstance], context: dict[str, Any] | None = None) -> ServiceInstance | None:
        healthy = [i for i in instances if i.is_healthy()]
        if not healthy:
            return None
        
        service_name = healthy[0].name
        total_weight = sum(i.weight for i in healthy)
        index = self._counters[service_name] % total_weight
        
        current_weight = 0
        for instance in healthy:
            current_weight += instance.weight
            if index < current_weight:
                self._counters[service_name] += 1
                return instance
        
        return healthy[-1]


class LeastConnectionsBalancer(LoadBalancer):
    """Least connections load balancer."""
    
    def select(self, instances: list[ServiceInstance], context: dict[str, Any] | None = None) -> ServiceInstance | None:
        healthy = [i for i in instances if i.is_healthy()]
        if not healthy:
            return None
        return min(healthy, key=lambda i: i.connection_count)


class ConsistentHashBalancer(LoadBalancer):
    """Consistent hash load balancer for session affinity."""
    
    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
    
    def select(self, instances: list[ServiceInstance], context: dict[str, Any] | None = None) -> ServiceInstance | None:
        healthy = [i for i in instances if i.is_healthy()]
        if not healthy:
            return None
        
        key = context.get("key", "") if context else ""
        if not key:
            return random.choice(healthy)
        
        # Build hash ring
        ring: dict[int, ServiceInstance] = {}
        for instance in healthy:
            for i in range(self.virtual_nodes):
                hash_key = self._hash(f"{instance.id}:{i}")
                ring[hash_key] = instance
        
        # Find closest node
        key_hash = self._hash(key)
        sorted_hashes = sorted(ring.keys())
        
        for hash_val in sorted_hashes:
            if hash_val >= key_hash:
                return ring[hash_val]
        
        return ring[sorted_hashes[0]]
    
    def _hash(self, key: str) -> int:
        """Generate hash for key."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)


class LatencyBasedBalancer(LoadBalancer):
    """Latency-based load balancer using EWMA."""
    
    def select(self, instances: list[ServiceInstance], context: dict[str, Any] | None = None) -> ServiceInstance | None:
        healthy = [i for i in instances if i.is_healthy()]
        if not healthy:
            return None
        
        # Weight inversely proportional to latency
        weights = []
        for instance in healthy:
            # Add small constant to avoid division by zero
            weight = 1.0 / (instance.avg_latency_ms + 1)
            weights.append(weight)
        
        total = sum(weights)
        normalized = [w / total for w in weights]
        
        # Weighted random selection
        r = random.random()
        cumulative = 0
        for i, weight in enumerate(normalized):
            cumulative += weight
            if r <= cumulative:
                return healthy[i]
        
        return healthy[-1]


class RandomBalancer(LoadBalancer):
    """Random load balancer."""
    
    def select(self, instances: list[ServiceInstance], context: dict[str, Any] | None = None) -> ServiceInstance | None:
        healthy = [i for i in instances if i.is_healthy()]
        if not healthy:
            return None
        return random.choice(healthy)


class ServiceMesh:
    """
    Enterprise Service Mesh for DragonScope.
    
    Coordinates service discovery, load balancing, circuit breaking,
    health checking, and retry policies across all microservices.
    """
    
    def __init__(
        self,
        consul_host: str = "localhost",
        consul_port: int = 8500,
        etcd_endpoints: list[str] | None = None
    ):
        self.services: dict[str, list[ServiceInstance]] = defaultdict(list)
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.balancers: dict[LoadBalanceStrategy, LoadBalancer] = {
            LoadBalanceStrategy.ROUND_ROBIN: RoundRobinBalancer(),
            LoadBalanceStrategy.WEIGHTED_ROUND_ROBIN: WeightedRoundRobinBalancer(),
            LoadBalanceStrategy.LEAST_CONNECTIONS: LeastConnectionsBalancer(),
            LoadBalanceStrategy.CONSISTENT_HASH: ConsistentHashBalancer(),
            LoadBalanceStrategy.LATENCY_BASED: LatencyBasedBalancer(),
            LoadBalanceStrategy.RANDOM: RandomBalancer(),
        }
        self.default_strategy = LoadBalanceStrategy.ROUND_ROBIN
        self.service_strategies: dict[str, LoadBalanceStrategy] = {}
        
        # Consul client
        self.consul_host = consul_host
        self.consul_port = consul_port
        self.consul: consul.aio.Consul | None = None
        
        # Health check polling
        self._health_check_task: asyncio.Task | None = None
        self._health_check_interval = 10.0
        self._running = False
        
        # HTTP session for health checks
        self._session: ClientSession | None = None
        
        # Event handlers
        self._on_service_up: list[Callable[[ServiceInstance], Coroutine]] = []
        self._on_service_down: list[Callable[[ServiceInstance], Coroutine]] = []
        
        logger.info("ServiceMesh initialized")
    
    async def start(self) -> None:
        """Start the service mesh."""
        self._running = True
        self._session = ClientSession(timeout=ClientTimeout(total=5))
        
        # Connect to Consul
        try:
            self.consul = consul.aio.Consul(host=self.consul_host, port=self.consul_port)
            logger.info(f"Connected to Consul at {self.consul_host}:{self.consul_port}")
        except Exception as e:
            logger.warning(f"Could not connect to Consul: {e}")
            self.consul = None
        
        # Start health check polling
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("ServiceMesh started")
    
    async def stop(self) -> None:
        """Stop the service mesh."""
        self._running = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._session:
            await self._session.close()
        
        if self.consul:
            await self.consul.close()
        
        logger.info("ServiceMesh stopped")
    
    def register_service(
        self,
        name: str,
        instance_id: str,
        host: str,
        port: int,
        metadata: dict[str, Any] | None = None,
        weight: int = 1,
        tags: list[str] | None = None,
        strategy: LoadBalanceStrategy | None = None
    ) -> ServiceInstance:
        """
        Register a new service instance.
        
        Args:
            name: Service name
            instance_id: Unique instance identifier
            host: Service host
            port: Service port
            metadata: Optional service metadata
            weight: Load balancing weight
            tags: Service tags
            strategy: Load balancing strategy for this service
        
        Returns:
            Registered service instance
        """
        instance = ServiceInstance(
            id=instance_id,
            name=name,
            host=host,
            port=port,
            metadata=metadata or {},
            weight=weight,
            tags=tags or [],
            status=ServiceStatus.HEALTHY
        )
        
        # Remove existing instance with same ID
        self.services[name] = [i for i in self.services[name] if i.id != instance_id]
        self.services[name].append(instance)
        
        if strategy:
            self.service_strategies[name] = strategy
        
        # Register with Consul if available
        if self.consul:
            asyncio.create_task(self._register_with_consul(instance))
        
        logger.info(f"Registered service: {name}/{instance_id} at {host}:{port}")
        
        # Notify handlers
        for handler in self._on_service_up:
            asyncio.create_task(handler(instance))
        
        return instance
    
    async def _register_with_consul(self, instance: ServiceInstance) -> None:
        """Register service with Consul."""
        if not self.consul:
            return
        
        try:
            check = consul.Check.http(
                url=f"{instance.url}/health",
                interval="10s",
                timeout="5s"
            )
            
            await self.consul.agent.service.register(
                name=instance.name,
                service_id=instance.id,
                address=instance.host,
                port=instance.port,
                tags=instance.tags,
                check=check
            )
        except Exception as e:
            logger.error(f"Failed to register with Consul: {e}")
    
    def deregister_service(self, name: str, instance_id: str) -> bool:
        """
        Deregister a service instance.
        
        Args:
            name: Service name
            instance_id: Instance identifier
        
        Returns:
            True if instance was found and removed
        """
        original_count = len(self.services[name])
        instance = next((i for i in self.services[name] if i.id == instance_id), None)
        
        self.services[name] = [i for i in self.services[name] if i.id != instance_id]
        
        if len(self.services[name]) < original_count:
            logger.info(f"Deregistered service: {name}/{instance_id}")
            
            # Deregister from Consul
            if self.consul and instance:
                asyncio.create_task(self._deregister_from_consul(instance_id))
            
            # Notify handlers
            if instance:
                for handler in self._on_service_down:
                    asyncio.create_task(handler(instance))
            
            return True
        
        return False
    
    async def _deregister_from_consul(self, instance_id: str) -> None:
        """Deregister service from Consul."""
        if not self.consul:
            return
        
        try:
            await self.consul.agent.service.deregister(instance_id)
        except Exception as e:
            logger.error(f"Failed to deregister from Consul: {e}")
    
    def get_instances(self, name: str) -> list[ServiceInstance]:
        """Get all instances of a service."""
        return self.services.get(name, [])
    
    def get_healthy_instances(self, name: str) -> list[ServiceInstance]:
        """Get healthy instances of a service."""
        return [i for i in self.get_instances(name) if i.is_healthy()]
    
    def select_instance(
        self,
        name: str,
        strategy: LoadBalanceStrategy | None = None,
        context: dict[str, Any] | None = None
    ) -> ServiceInstance | None:
        """
        Select a service instance using load balancing.
        
        Args:
            name: Service name
            strategy: Load balancing strategy (overrides default)
            context: Routing context (for consistent hashing)
        
        Returns:
            Selected service instance or None
        """
        instances = self.get_instances(name)
        if not instances:
            return None
        
        strategy = strategy or self.service_strategies.get(name, self.default_strategy)
        balancer = self.balancers[strategy]
        
        instance = balancer.select(instances, context)
        if instance:
            instance.connection_count += 1
        
        return instance
    
    @asynccontextmanager
    async def with_instance(
        self,
        name: str,
        strategy: LoadBalanceStrategy | None = None,
        context: dict[str, Any] | None = None
    ):
        """Context manager for using a service instance."""
        instance = self.select_instance(name, strategy, context)
        if not instance:
            raise ServiceUnavailableError(f"No available instances for {name}")
        
        try:
            yield instance
        finally:
            instance.connection_count = max(0, instance.connection_count - 1)
    
    def get_or_create_circuit_breaker(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    async def call_with_retry(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        retry_policy: RetryPolicy | None = None,
        *args,
        **kwargs
    ) -> T:
        """
        Execute function with retry logic.
        
        Args:
            func: Async function to call
            retry_policy: Retry configuration
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: After all retries exhausted
        """
        policy = retry_policy or RetryPolicy()
        last_exception: Exception | None = None
        
        for attempt in range(policy.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # Check if exception is retryable
                if not any(isinstance(e, exc_type) for exc_type in policy.retryable_exceptions):
                    raise
                
                if attempt < policy.max_retries:
                    delay = policy.get_delay(attempt)
                    logger.warning(
                        f"Retry {attempt + 1}/{policy.max_retries} after {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
        
        raise last_exception or Exception("All retries exhausted")
    
    async def call_service(
        self,
        service_name: str,
        path: str = "/",
        method: str = "GET",
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        strategy: LoadBalanceStrategy | None = None,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make HTTP call to a service with full resilience patterns.
        
        Args:
            service_name: Target service name
            path: API path
            method: HTTP method
            data: Request body
            headers: Request headers
            retry_policy: Retry configuration
            circuit_breaker_config: Circuit breaker configuration
            strategy: Load balancing strategy
            context: Routing context
        
        Returns:
            Response data
        """
        circuit_breaker = self.get_or_create_circuit_breaker(
            service_name, circuit_breaker_config
        )
        
        async def _make_request() -> dict[str, Any]:
            async with self.with_instance(service_name, strategy, context) as instance:
                if not self._session:
                    raise RuntimeError("ServiceMesh not started")
                
                url = f"{instance.url}{path}"
                start_time = time.time()
                
                try:
                    async with self._session.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=headers
                    ) as response:
                        latency_ms = (time.time() - start_time) * 1000
                        instance.update_latency(latency_ms)
                        
                        response.raise_for_status()
                        return await response.json()
                        
                except aiohttp.ClientResponseError as e:
                    latency_ms = (time.time() - start_time) * 1000
                    instance.update_latency(latency_ms)
                    
                    # Check if status code is retryable
                    policy = retry_policy or RetryPolicy()
                    if e.status in policy.retryable_statuses:
                        raise  # Will be caught by retry logic
                    raise
        
        # Apply circuit breaker and retry
        return await circuit_breaker.call(
            self.call_with_retry,
            _make_request,
            retry_policy
        )
    
    async def _health_check_loop(self) -> None:
        """Background health check polling."""
        while self._running:
            try:
                await self._run_health_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            await asyncio.sleep(self._health_check_interval)
    
    async def _run_health_checks(self) -> None:
        """Run health checks for all services."""
        tasks = []
        
        for service_name, instances in self.services.items():
            for instance in instances:
                task = asyncio.create_task(
                    self._check_instance_health(instance),
                    name=f"health-check-{instance.id}"
                )
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_instance_health(self, instance: ServiceInstance) -> None:
        """Check health of a single instance."""
        if not self._session:
            return
        
        health_url = f"{instance.url}/health"
        start_time = time.time()
        
        try:
            async with self._session.get(health_url) as response:
                latency_ms = (time.time() - start_time) * 1000
                instance.update_latency(latency_ms)
                instance.last_heartbeat = time.time()
                
                if response.status == 200:
                    data = await response.json()
                    status = data.get("status", "healthy")
                    
                    if status == "healthy":
                        instance.status = ServiceStatus.HEALTHY
                        instance.health_score = 100.0
                    elif status == "degraded":
                        instance.status = ServiceStatus.DEGRADED
                        instance.health_score = 50.0
                    else:
                        instance.status = ServiceStatus.UNHEALTHY
                        instance.health_score = 10.0
                        
                else:
                    instance.status = ServiceStatus.UNHEALTHY
                    instance.health_score = max(0, instance.health_score - 20)
                    
        except asyncio.TimeoutError:
            instance.status = ServiceStatus.DEGRADED
            instance.health_score = max(0, instance.health_score - 10)
            logger.warning(f"Health check timeout for {instance.name}/{instance.id}")
            
        except Exception as e:
            instance.status = ServiceStatus.UNHEALTHY
            instance.health_score = max(0, instance.health_score - 30)
            logger.error(f"Health check failed for {instance.name}/{instance.id}: {e}")
        
        # Update error rate
        if instance.status != ServiceStatus.HEALTHY:
            instance.error_rate = min(100, instance.error_rate + 5)
        else:
            instance.error_rate = max(0, instance.error_rate - 1)
    
    def on_service_up(self, handler: Callable[[ServiceInstance], Coroutine]) -> None:
        """Register handler for service up events."""
        self._on_service_up.append(handler)
    
    def on_service_down(self, handler: Callable[[ServiceInstance], Coroutine]) -> None:
        """Register handler for service down events."""
        self._on_service_down.append(handler)
    
    def get_service_stats(self, name: str) -> dict[str, Any]:
        """Get statistics for a service."""
        instances = self.get_instances(name)
        healthy = [i for i in instances if i.is_healthy()]
        
        return {
            "name": name,
            "total_instances": len(instances),
            "healthy_instances": len(healthy),
            "health_percentage": (len(healthy) / len(instances) * 100) if instances else 0,
            "avg_latency_ms": sum(i.avg_latency_ms for i in instances) / len(instances) if instances else 0,
            "avg_health_score": sum(i.health_score for i in instances) / len(instances) if instances else 0,
            "circuit_breaker": self.circuit_breakers.get(name, CircuitBreaker(name)).get_metrics()
        }
    
    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all services."""
        return {
            name: self.get_service_stats(name)
            for name in self.services.keys()
        }


class ServiceUnavailableError(Exception):
    """Raised when no service instances are available."""
    pass


# Singleton instance
_mesh_instance: ServiceMesh | None = None


def get_mesh() -> ServiceMesh:
    """Get singleton ServiceMesh instance."""
    global _mesh_instance
    if _mesh_instance is None:
        _mesh_instance = ServiceMesh()
    return _mesh_instance


def set_mesh(mesh: ServiceMesh) -> None:
    """Set singleton ServiceMesh instance."""
    global _mesh_instance
    _mesh_instance = mesh
