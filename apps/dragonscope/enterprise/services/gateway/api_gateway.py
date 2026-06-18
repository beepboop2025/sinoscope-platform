"""
DragonScope Enterprise API Gateway
FastAPI-based gateway with load balancing, circuit breaker, and request routing.
"""

import asyncio
import hashlib
import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from collections import deque
import random

import httpx
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import redis.asyncio as redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_gateway")


# =============================================================================
# Data Models
# =============================================================================

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class ServiceInstance:
    """Represents a microservice instance."""
    id: str
    host: str
    port: int
    health_check_path: str = "/health"
    weight: int = 1
    active_connections: int = 0
    last_health_check: float = 0.0
    healthy: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    success_threshold: int = 2


@dataclass
class RetryConfig:
    """Retry configuration with exponential backoff."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_status_codes: List[int] = field(default_factory=lambda: [500, 502, 503, 504])
    retryable_exceptions: List[type] = field(default_factory=lambda: [httpx.NetworkError, httpx.TimeoutException])


@dataclass
class RouteConfig:
    """API route configuration."""
    path: str
    service: str
    methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH"])
    strip_prefix: bool = True
    timeout: float = 30.0
    require_auth: bool = True
    allowed_versions: List[str] = field(default_factory=lambda: ["v1"])
    transformers: List[str] = field(default_factory=list)


# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()
        self._half_open_calls = 0
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            await self._update_state()
            
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is OPEN")
            
            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' HALF_OPEN limit reached")
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _update_state(self):
        """Update circuit state based on time and conditions."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self.success_count = 0
                logger.info(f"Circuit '{self.name}' moved to HALF_OPEN")
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._reset()
                    logger.info(f"Circuit '{self.name}' moved to CLOSED")
            else:
                self.failure_count = max(0, self.failure_count - 1)
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit '{self.name}' moved to OPEN (half-open failure)")
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit '{self.name}' moved to OPEN (threshold: {self.failure_count})")
    
    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self._half_open_calls = 0
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# =============================================================================
# Load Balancer Strategies
# =============================================================================

class LoadBalancerStrategy(ABC):
    """Abstract base class for load balancing strategies."""
    
    @abstractmethod
    def select_instance(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        """Select a service instance from the pool."""
        pass


class RoundRobinStrategy(LoadBalancerStrategy):
    """Round-robin load balancing."""
    
    def __init__(self):
        self._counter = 0
        self._lock = asyncio.Lock()
    
    async def select_instance(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        healthy = [i for i in instances if i.healthy]
        if not healthy:
            return None
        
        async with self._lock:
            instance = healthy[self._counter % len(healthy)]
            self._counter += 1
            return instance


class WeightedRoundRobinStrategy(LoadBalancerStrategy):
    """Weighted round-robin load balancing."""
    
    def __init__(self):
        self._current_index = 0
        self._current_weight = 0
        self._max_weight = 0
        self._gcd_weight = 0
        self._lock = asyncio.Lock()
    
    async def select_instance(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        healthy = [i for i in instances if i.healthy]
        if not healthy:
            return None
        
        async with self._lock:
            if self._max_weight == 0:
                self._max_weight = max(i.weight for i in healthy)
                self._gcd_weight = self._gcd([i.weight for i in healthy])
            
            while True:
                self._current_index = (self._current_index + 1) % len(healthy)
                if self._current_index == 0:
                    self._current_weight -= self._gcd_weight
                    if self._current_weight <= 0:
                        self._current_weight = self._max_weight
                
                if healthy[self._current_index].weight >= self._current_weight:
                    return healthy[self._current_index]
    
    def _gcd(self, numbers: List[int]) -> int:
        """Calculate greatest common divisor."""
        from math import gcd
        from functools import reduce
        return reduce(gcd, numbers)


class LeastConnectionsStrategy(LoadBalancerStrategy):
    """Least connections load balancing."""
    
    def select_instance(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        healthy = [i for i in instances if i.healthy]
        if not healthy:
            return None
        return min(healthy, key=lambda i: i.active_connections)


class LeastResponseTimeStrategy(LoadBalancerStrategy):
    """Least response time load balancing."""
    
    def __init__(self):
        self._response_times: Dict[str, deque] = {}
        self._max_samples = 10
    
    def select_instance(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        healthy = [i for i in instances if i.healthy]
        if not healthy:
            return None
        
        def avg_response_time(instance: ServiceInstance) -> float:
            times = self._response_times.get(instance.id, deque(maxlen=self._max_samples))
            return sum(times) / len(times) if times else float('inf')
        
        return min(healthy, key=avg_response_time)
    
    def record_response_time(self, instance_id: str, response_time: float):
        """Record response time for an instance."""
        if instance_id not in self._response_times:
            self._response_times[instance_id] = deque(maxlen=self._max_samples)
        self._response_times[instance_id].append(response_time)


class IPHashStrategy(LoadBalancerStrategy):
    """IP hash load balancing for session affinity."""
    
    def __init__(self):
        self._hash_ring: Dict[int, ServiceInstance] = {}
        self._virtual_nodes = 150
    
    def build_ring(self, instances: List[ServiceInstance]):
        """Build consistent hash ring."""
        self._hash_ring = {}
        for instance in instances:
            if instance.healthy:
                for i in range(self._virtual_nodes * instance.weight):
                    key = self._hash(f"{instance.id}:{i}")
                    self._hash_ring[key] = instance
        self._sorted_keys = sorted(self._hash_ring.keys())
    
    def select_instance(self, instances: List[ServiceInstance], client_ip: str = None) -> Optional[ServiceInstance]:
        if not self._hash_ring:
            self.build_ring(instances)
        
        if not self._hash_ring or not client_ip:
            healthy = [i for i in instances if i.healthy]
            return healthy[0] if healthy else None
        
        hash_key = self._hash(client_ip)
        for key in self._sorted_keys:
            if key >= hash_key:
                return self._hash_ring[key]
        return self._hash_ring[self._sorted_keys[0]]
    
    def _hash(self, key: str) -> int:
        """Generate hash for key."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)


# =============================================================================
# Service Registry
# =============================================================================

class ServiceRegistry:
    """In-memory service registry with health checking."""
    
    def __init__(self, redis_client: redis.Redis = None):
        self._services: Dict[str, List[ServiceInstance]] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._redis = redis_client
        self._health_check_interval = 10.0
        self._running = False
        self._lock = asyncio.Lock()
    
    def register(self, service_name: str, instance: ServiceInstance):
        """Register a service instance."""
        if service_name not in self._services:
            self._services[service_name] = []
        self._services[service_name].append(instance)
        logger.info(f"Registered instance {instance.id} for service {service_name}")
    
    def unregister(self, service_name: str, instance_id: str):
        """Unregister a service instance."""
        if service_name in self._services:
            self._services[service_name] = [
                i for i in self._services[service_name] if i.id != instance_id
            ]
            logger.info(f"Unregistered instance {instance_id} from service {service_name}")
    
    def get_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get all instances for a service."""
        return self._services.get(service_name, [])
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service_name not in self._circuit_breakers:
            self._circuit_breakers[service_name] = CircuitBreaker(service_name)
        return self._circuit_breakers[service_name]
    
    async def start_health_checks(self):
        """Start background health checking."""
        self._running = True
        while self._running:
            await self._check_health()
            await asyncio.sleep(self._health_check_interval)
    
    async def stop_health_checks(self):
        """Stop health checking."""
        self._running = False
    
    async def _check_health(self):
        """Perform health checks on all instances."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            for service_name, instances in self._services.items():
                for instance in instances:
                    try:
                        response = await client.get(
                            f"{instance.url}{instance.health_check_path}"
                        )
                        instance.healthy = response.status_code == 200
                        instance.last_health_check = time.time()
                    except Exception as e:
                        instance.healthy = False
                        logger.warning(f"Health check failed for {instance.id}: {e}")


# =============================================================================
# Request/Response Transformers
# =============================================================================

class Transformer(ABC):
    """Abstract base class for request/response transformers."""
    
    @abstractmethod
    async def transform(self, data: Union[Request, Response, Dict]) -> Union[Request, Response, Dict]:
        """Transform request or response data."""
        pass


class HeaderTransformer(Transformer):
    """Add/modify headers."""
    
    def __init__(self, headers: Dict[str, str], remove_headers: List[str] = None):
        self.headers = headers
        self.remove_headers = remove_headers or []
    
    async def transform(self, data: Union[Request, Response, Dict]) -> Union[Request, Response, Dict]:
        if isinstance(data, dict):
            data["headers"] = {**data.get("headers", {}), **self.headers}
            for h in self.remove_headers:
                data["headers"].pop(h, None)
        return data


class BodyTransformer(Transformer):
    """Transform request/response body."""
    
    def __init__(self, transform_func: Callable):
        self.transform_func = transform_func
    
    async def transform(self, data: Union[Request, Response, Dict]) -> Union[Request, Response, Dict]:
        if isinstance(data, dict) and "body" in data:
            data["body"] = await self.transform_func(data["body"])
        return data


class VersionTransformer(Transformer):
    """Transform API version in requests/responses."""
    
    def __init__(self, from_version: str, to_version: str):
        self.from_version = from_version
        self.to_version = to_version
    
    async def transform(self, data: Union[Request, Response, Dict]) -> Union[Request, Response, Dict]:
        if isinstance(data, dict) and "path" in data:
            data["path"] = data["path"].replace(f"/{self.from_version}/", f"/{self.to_version}/")
        return data


# =============================================================================
# Retry Handler
# =============================================================================

class RetryHandler:
    """Handle retries with exponential backoff."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e, attempt):
                    raise
                
                delay = self._calculate_delay(attempt)
                logger.warning(f"Retry {attempt + 1}/{self.config.max_retries} after {delay}s: {e}")
                await asyncio.sleep(delay)
        
        raise last_exception
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if request should be retried."""
        if attempt >= self.config.max_retries:
            return False
        
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code in self.config.retryable_status_codes
        
        return type(exception) in self.config.retryable_exceptions
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter


# =============================================================================
# API Gateway
# =============================================================================

class APIGateway:
    """Main API Gateway implementation."""
    
    def __init__(self, redis_client: redis.Redis = None):
        self.app = FastAPI(
            title="DragonScope Enterprise API Gateway",
            description="Enterprise-grade API Gateway with load balancing and circuit breaking",
            version="2.0.0"
        )
        
        self.registry = ServiceRegistry(redis_client)
        self.retry_handler = RetryHandler()
        self.strategies: Dict[str, LoadBalancerStrategy] = {
            "round_robin": RoundRobinStrategy(),
            "weighted_round_robin": WeightedRoundRobinStrategy(),
            "least_connections": LeastConnectionsStrategy(),
            "least_response_time": LeastResponseTimeStrategy(),
            "ip_hash": IPHashStrategy(),
        }
        self.routes: Dict[str, RouteConfig] = {}
        self.transformers: Dict[str, Transformer] = {}
        self._openapi_schemas: Dict[str, Dict] = {}
        
        self._setup_middleware()
        self._setup_routes()
    
    def _setup_middleware(self):
        """Configure middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    def _setup_routes(self):
        """Configure gateway routes."""
        
        @self.app.get("/gateway/health")
        async def gateway_health():
            """Gateway health check."""
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "services": {
                    name: len(instances)
                    for name, instances in self.registry._services.items()
                }
            }
        
        @self.app.get("/gateway/services")
        async def list_services():
            """List registered services."""
            return {
                name: [
                    {
                        "id": i.id,
                        "url": i.url,
                        "healthy": i.healthy,
                        "active_connections": i.active_connections,
                    }
                    for i in instances
                ]
                for name, instances in self.registry._services.items()
            }
        
        @self.app.get("/gateway/openapi.json")
        async def aggregated_openapi():
            """Return aggregated OpenAPI schema from all services."""
            return await self._aggregate_openapi()
        
        @self.app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
        async def proxy_request(request: Request, path: str):
            """Main proxy handler."""
            return await self._handle_request(request, path)
    
    async def _handle_request(self, request: Request, path: str) -> Response:
        """Handle incoming proxy request."""
        # Parse API version from path
        version = self._extract_version(path)
        
        # Find matching route
        route = self._match_route(path)
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        
        # Check version support
        if version and version not in route.allowed_versions:
            raise HTTPException(status_code=400, detail=f"API version {version} not supported")
        
        # Get service instances
        instances = self.registry.get_instances(route.service)
        if not instances:
            raise HTTPException(status_code=503, detail=f"Service '{route.service}' unavailable")
        
        # Select load balancer strategy
        strategy = self.strategies.get("least_connections", RoundRobinStrategy())
        
        # Get circuit breaker
        circuit_breaker = self.registry.get_circuit_breaker(route.service)
        
        # Get client IP for IP hash strategy
        client_ip = request.client.host if request.client else None
        
        # Select instance
        if isinstance(strategy, IPHashStrategy):
            instance = strategy.select_instance(instances, client_ip)
        elif isinstance(strategy, RoundRobinStrategy):
            instance = await strategy.select_instance(instances)
        elif isinstance(strategy, WeightedRoundRobinStrategy):
            instance = await strategy.select_instance(instances)
        else:
            instance = strategy.select_instance(instances)
        
        if not instance:
            raise HTTPException(status_code=503, detail="No healthy instances available")
        
        # Transform request
        transformed_request = await self._transform_request(request, route, version)
        
        # Execute with circuit breaker and retry
        try:
            response = await circuit_breaker.call(
                self._proxy_with_retry,
                instance,
                transformed_request,
                route
            )
            return response
        except CircuitBreakerOpenError:
            # Graceful degradation
            return await self._fallback_response(route, request)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise HTTPException(status_code=502, detail="Bad Gateway")
    
    async def _proxy_with_retry(
        self,
        instance: ServiceInstance,
        request_data: Dict,
        route: RouteConfig
    ) -> Response:
        """Proxy request with retry logic."""
        
        async def do_proxy():
            instance.active_connections += 1
            start_time = time.time()
            
            try:
                async with httpx.AsyncClient(timeout=route.timeout) as client:
                    method = request_data["method"]
                    url = f"{instance.url}{request_data['path']}"
                    
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=request_data.get("headers", {}),
                        content=request_data.get("body"),
                        params=request_data.get("query_params")
                    )
                    
                    # Record response time for least_response_time strategy
                    if isinstance(self.strategies.get("least_response_time"), LeastResponseTimeStrategy):
                        self.strategies["least_response_time"].record_response_time(
                            instance.id,
                            time.time() - start_time
                        )
                    
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        headers=dict(response.headers)
                    )
            finally:
                instance.active_connections -= 1
        
        return await self.retry_handler.execute(do_proxy)
    
    async def _transform_request(self, request: Request, route: RouteConfig, version: str) -> Dict:
        """Transform incoming request."""
        body = await request.body()
        
        data = {
            "method": request.method,
            "path": request.url.path,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "body": body,
        }
        
        # Strip prefix if configured
        if route.strip_prefix:
            # Remove version prefix
            for v in route.allowed_versions:
                data["path"] = data["path"].replace(f"/{v}", "", 1)
        
        # Apply transformers
        for transformer_name in route.transformers:
            if transformer_name in self.transformers:
                data = await self.transformers[transformer_name].transform(data)
        
        # Add gateway headers
        data["headers"]["X-Forwarded-By"] = "dragonscope-gateway"
        data["headers"]["X-API-Version"] = version or "v1"
        data["headers"]["X-Request-ID"] = request.headers.get("X-Request-ID", self._generate_request_id())
        
        # Remove hop-by-hop headers
        hop_by_hop = ["connection", "keep-alive", "proxy-authenticate", "proxy-authorization"]
        for h in hop_by_hop:
            data["headers"].pop(h, None)
            data["headers"].pop(h.title(), None)
        
        return data
    
    async def _fallback_response(self, route: RouteConfig, request: Request) -> Response:
        """Generate fallback response when circuit is open."""
        # Check for cached response
        # Return default response or 503
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service temporarily unavailable",
                "service": route.service,
                "message": "Circuit breaker is open. Please try again later."
            }
        )
    
    def _extract_version(self, path: str) -> Optional[str]:
        """Extract API version from path."""
        parts = path.strip("/").split("/")
        if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
            return parts[0]
        return None
    
    def _match_route(self, path: str) -> Optional[RouteConfig]:
        """Find matching route configuration."""
        for route_path, route in self.routes.items():
            if path.startswith(route_path):
                return route
        return None
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        return hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:16]
    
    async def _aggregate_openapi(self) -> Dict:
        """Aggregate OpenAPI schemas from all services."""
        aggregated = {
            "openapi": "3.0.0",
            "info": {
                "title": "DragonScope Enterprise API",
                "version": "2.0.0",
                "description": "Aggregated API documentation"
            },
            "paths": {},
            "components": {"schemas": {}}
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for service_name, instances in self.registry._services.items():
                if not instances:
                    continue
                
                instance = instances[0]
                if not instance.healthy:
                    continue
                
                try:
                    response = await client.get(f"{instance.url}/openapi.json")
                    if response.status_code == 200:
                        schema = response.json()
                        
                        # Merge paths with service prefix
                        for path, methods in schema.get("paths", {}).items():
                            prefixed_path = f"/{service_name}{path}"
                            aggregated["paths"][prefixed_path] = methods
                        
                        # Merge components
                        for name, definition in schema.get("components", {}).get("schemas", {}).items():
                            aggregated["components"]["schemas"][f"{service_name}_{name}"] = definition
                
                except Exception as e:
                    logger.warning(f"Failed to fetch schema from {service_name}: {e}")
        
        return aggregated
    
    def register_route(self, config: RouteConfig):
        """Register a new route."""
        self.routes[config.path] = config
        logger.info(f"Registered route: {config.path} -> {config.service}")
    
    def register_transformer(self, name: str, transformer: Transformer):
        """Register a request/response transformer."""
        self.transformers[name] = transformer
    
    async def start(self):
        """Start background tasks."""
        asyncio.create_task(self.registry.start_health_checks())
    
    async def stop(self):
        """Stop background tasks."""
        await self.registry.stop_health_checks()


# =============================================================================
# Factory Functions
# =============================================================================

def create_gateway(redis_url: str = None) -> APIGateway:
    """Create and configure API Gateway."""
    redis_client = None
    if redis_url:
        redis_client = redis.from_url(redis_url)
    
    gateway = APIGateway(redis_client)
    
    # Register default routes
    gateway.register_route(RouteConfig(
        path="/v1/users",
        service="user-service",
        methods=["GET", "POST", "PUT", "DELETE"],
        allowed_versions=["v1", "v2"]
    ))
    
    gateway.register_route(RouteConfig(
        path="/v1/analytics",
        service="analytics-service",
        methods=["GET", "POST"],
        allowed_versions=["v1"]
    ))
    
    gateway.register_route(RouteConfig(
        path="/v1/tenants",
        service="tenant-service",
        methods=["GET", "POST", "PUT", "DELETE"],
        allowed_versions=["v1", "v2"]
    ))
    
    # Register transformers
    gateway.register_transformer("headers", HeaderTransformer({
        "X-Gateway-Version": "2.0.0"
    }))
    
    gateway.register_transformer("v1_to_v2", VersionTransformer("v1", "v2"))
    
    return gateway


# =============================================================================
# Application Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    gateway = create_gateway(redis_url="redis://localhost:6379")
    
    # Register some example instances
    gateway.registry.register("user-service", ServiceInstance(
        id="user-1",
        host="localhost",
        port=8001,
        weight=2
    ))
    gateway.registry.register("user-service", ServiceInstance(
        id="user-2",
        host="localhost",
        port=8002,
        weight=1
    ))
    
    uvicorn.run(gateway.app, host="0.0.0.0", port=8080)
