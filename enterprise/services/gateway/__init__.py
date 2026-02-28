"""
DragonScope Enterprise API Gateway

A high-performance, enterprise-grade API gateway with:
- Load balancing (round-robin, least-connections, weighted)
- Circuit breaker pattern for fault tolerance
- Retry with exponential backoff
- Request/response transformation
- API versioning support
- OpenAPI aggregation
"""

from .api_gateway import (
    APIGateway,
    ServiceRegistry,
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryConfig,
    RouteConfig,
    RoundRobinStrategy,
    WeightedRoundRobinStrategy,
    LeastConnectionsStrategy,
    LeastResponseTimeStrategy,
    IPHashStrategy,
    create_gateway,
)

from .rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitAlgorithm,
    TieredRateLimiter,
    RateLimitMiddleware,
    create_rate_limiter,
    create_enterprise_tiered_limiter,
)

from .cache import (
    MultiTierCache,
    CacheConfig,
    CacheStrategy,
    InMemoryCache,
    RedisCache,
    CDNCache,
    CacheWarmer,
    create_cache,
    create_enterprise_cache,
    cached,
    cache_evict,
)

__version__ = "2.0.0"
__all__ = [
    # Gateway
    "APIGateway",
    "ServiceRegistry",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "RetryConfig",
    "RouteConfig",
    # Load Balancers
    "RoundRobinStrategy",
    "WeightedRoundRobinStrategy",
    "LeastConnectionsStrategy",
    "LeastResponseTimeStrategy",
    "IPHashStrategy",
    # Rate Limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitAlgorithm",
    "TieredRateLimiter",
    "RateLimitMiddleware",
    # Cache
    "MultiTierCache",
    "CacheConfig",
    "CacheStrategy",
    "InMemoryCache",
    "RedisCache",
    "CDNCache",
    "CacheWarmer",
    # Decorators
    "cached",
    "cache_evict",
    # Factories
    "create_gateway",
    "create_rate_limiter",
    "create_enterprise_tiered_limiter",
    "create_cache",
    "create_enterprise_cache",
]
