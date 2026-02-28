"""
DragonScope Enterprise Rate Limiter
Distributed rate limiting with Redis support.
Supports: Token Bucket, Sliding Window, Fixed Window algorithms.
"""

import asyncio
import time
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Callable, Any, Tuple
from functools import wraps

import redis.asyncio as redis
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("rate_limiter")


# =============================================================================
# Data Models
# =============================================================================

class RateLimitAlgorithm(Enum):
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW_COUNTER = "sliding_window_counter"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: float = 10.0
    burst_size: int = 20
    window_size: int = 60  # seconds for window-based algorithms
    quota: int = 1000  # requests per window
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    key_prefix: str = "rl"
    block_duration: int = 300  # seconds to block after exceeding limit
    
    # Per-tenant overrides
    tenant_limits: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Per-endpoint overrides
    endpoint_limits: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    window: Optional[str] = None


# =============================================================================
# Rate Limit Algorithms
# =============================================================================

class RateLimiterAlgorithm(ABC):
    """Abstract base class for rate limiting algorithms."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    @abstractmethod
    async def is_allowed(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        """Check if request is allowed."""
        pass
    
    @abstractmethod
    async def reset(self, key: str):
        """Reset rate limit for key."""
        pass


class TokenBucketAlgorithm(RateLimiterAlgorithm):
    """
    Token Bucket Algorithm
    
    - Bucket has a fixed capacity (burst_size)
    - Tokens are added at a constant rate (requests_per_second)
    - Each request consumes one token
    - If no tokens available, request is rejected
    
    Pros: Allows bursts, smooth rate limiting
    Cons: Requires Redis atomic operations
    """
    
    async def is_allowed(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        bucket_key = f"{config.key_prefix}:bucket:{key}"
        tokens_key = f"{bucket_key}:tokens"
        last_update_key = f"{bucket_key}:last_update"
        
        pipe = self.redis.pipeline()
        
        # Get current state
        now = time.time()
        pipe.get(tokens_key)
        pipe.get(last_update_key)
        results = await pipe.execute()
        
        tokens = float(results[0]) if results[0] else config.burst_size
        last_update = float(results[1]) if results[1] else now
        
        # Calculate tokens to add based on time passed
        time_passed = now - last_update
        tokens_to_add = time_passed * config.requests_per_second
        tokens = min(config.burst_size, tokens + tokens_to_add)
        
        # Check if request can be processed
        if tokens >= 1:
            tokens -= 1
            allowed = True
            remaining = int(tokens)
        else:
            allowed = False
            remaining = 0
        
        # Update state atomically
        pipe = self.redis.pipeline()
        pipe.set(tokens_key, tokens)
        pipe.set(last_update_key, now)
        pipe.expire(tokens_key, 3600)  # 1 hour TTL
        pipe.expire(last_update_key, 3600)
        await pipe.execute()
        
        # Calculate reset time
        if tokens < config.burst_size:
            reset_time = int(now + (config.burst_size - tokens) / config.requests_per_second)
        else:
            reset_time = int(now)
        
        retry_after = None
        if not allowed:
            retry_after = int(1 / config.requests_per_second) + 1
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.burst_size,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after
        )
    
    async def reset(self, key: str):
        bucket_key = f"bucket:{key}"
        await self.redis.delete(f"{bucket_key}:tokens", f"{bucket_key}:last_update")


class SlidingWindowAlgorithm(RateLimiterAlgorithm):
    """
    Sliding Window Log Algorithm
    
    - Stores timestamp of each request in a sorted set
    - Removes entries outside the window
    - Counts requests in current window
    
    Pros: Very accurate
    Cons: Higher memory usage (stores all request timestamps)
    """
    
    async def is_allowed(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        window_key = f"{config.key_prefix}:sw:{key}"
        now = time.time()
        window_start = now - config.window_size
        
        pipe = self.redis.pipeline()
        
        # Remove old entries outside window
        pipe.zremrangebyscore(window_key, 0, window_start)
        
        # Count current requests in window
        pipe.zcard(window_key)
        
        # Add current request
        pipe.zadd(window_key, {str(now): now})
        
        # Set expiry on the key
        pipe.expire(window_key, config.window_size + 1)
        
        results = await pipe.execute()
        current_count = results[1]  # Count before adding current request
        
        # Check if adding this request exceeds limit
        if current_count >= config.quota:
            # Remove the request we just added
            await self.redis.zrem(window_key, str(now))
            allowed = False
            remaining = 0
        else:
            allowed = True
            remaining = config.quota - current_count - 1
        
        # Get oldest request in window for reset time
        oldest = await self.redis.zrange(window_key, 0, 0, withscores=True)
        if oldest:
            reset_time = int(oldest[0][1] + config.window_size)
        else:
            reset_time = int(now + config.window_size)
        
        retry_after = None
        if not allowed:
            retry_after = reset_time - int(now)
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.quota,
            remaining=max(0, remaining),
            reset_time=reset_time,
            retry_after=retry_after,
            window=f"{config.window_size}s"
        )
    
    async def reset(self, key: str):
        await self.redis.delete(f"sw:{key}")


class FixedWindowAlgorithm(RateLimiterAlgorithm):
    """
    Fixed Window Algorithm
    
    - Time is divided into fixed windows
    - Counter is reset at the start of each window
    - Simple and memory efficient
    
    Pros: Very efficient, low memory
    Cons: Can allow bursts at window boundaries
    """
    
    async def is_allowed(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        now = int(time.time())
        window = now // config.window_size
        window_key = f"{config.key_prefix}:fw:{key}:{window}"
        
        pipe = self.redis.pipeline()
        
        # Increment counter
        pipe.incr(window_key)
        
        # Set expiry if new key
        pipe.expire(window_key, config.window_size + 1)
        
        results = await pipe.execute()
        current_count = results[0]
        
        allowed = current_count <= config.quota
        remaining = max(0, config.quota - current_count)
        
        # Calculate window reset time
        reset_time = (window + 1) * config.window_size
        
        retry_after = None
        if not allowed:
            retry_after = reset_time - now
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.quota,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            window=f"{config.window_size}s"
        )
    
    async def reset(self, key: str):
        now = int(time.time())
        window = now // 60  # Assuming 60s window, would need to iterate all possible windows
        await self.redis.delete(f"fw:{key}:{window}")


class SlidingWindowCounterAlgorithm(RateLimiterAlgorithm):
    """
    Sliding Window Counter Algorithm
    
    - Combines current window count with weighted previous window count
    - More accurate than fixed window, more efficient than sliding window log
    
    estimate = prev_count * (1 - elapsed/window) + current_count
    """
    
    async def is_allowed(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        now = time.time()
        current_window = int(now) // config.window_size
        previous_window = current_window - 1
        
        current_key = f"{config.key_prefix}:swc:{key}:{current_window}"
        previous_key = f"{config.key_prefix}:swc:{key}:{previous_window}"
        
        pipe = self.redis.pipeline()
        pipe.get(previous_key)
        pipe.incr(current_key)
        pipe.expire(current_key, config.window_size * 2)
        
        results = await pipe.execute()
        previous_count = int(results[0]) if results[0] else 0
        current_count = results[1]
        
        # Calculate weighted estimate
        elapsed_in_window = now % config.window_size
        weight = 1 - (elapsed_in_window / config.window_size)
        estimated = int(previous_count * weight) + current_count
        
        allowed = estimated <= config.quota
        remaining = max(0, config.quota - estimated)
        
        reset_time = (current_window + 1) * config.window_size
        
        retry_after = None
        if not allowed:
            retry_after = reset_time - int(now)
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.quota,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            window=f"{config.window_size}s"
        )
    
    async def reset(self, key: str):
        now = int(time.time())
        current_window = now // 60
        await self.redis.delete(f"swc:{key}:{current_window}")


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """Distributed rate limiter with multiple algorithm support."""
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client or redis.from_url("redis://localhost:6379")
        self.algorithms: Dict[RateLimitAlgorithm, RateLimiterAlgorithm] = {
            RateLimitAlgorithm.TOKEN_BUCKET: TokenBucketAlgorithm(self.redis),
            RateLimitAlgorithm.SLIDING_WINDOW: SlidingWindowAlgorithm(self.redis),
            RateLimitAlgorithm.FIXED_WINDOW: FixedWindowAlgorithm(self.redis),
            RateLimitAlgorithm.SLIDING_WINDOW_COUNTER: SlidingWindowCounterAlgorithm(self.redis),
        }
        self.default_config = RateLimitConfig()
        self._local_cache: Dict[str, Tuple[bool, float]] = {}
        self._cache_ttl = 0.1  # 100ms local cache
    
    async def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig = None
    ) -> RateLimitResult:
        """Check if request is within rate limit."""
        config = config or self.default_config
        algorithm = self.algorithms.get(config.algorithm, self.algorithms[RateLimitAlgorithm.TOKEN_BUCKET])
        return await algorithm.is_allowed(key, config)
    
    async def check_burst(
        self,
        key: str,
        burst_size: int,
        window: int = 1
    ) -> RateLimitResult:
        """Check burst rate limit (simplified token bucket)."""
        config = RateLimitConfig(
            requests_per_second=burst_size / window,
            burst_size=burst_size,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        return await self.check_rate_limit(key, config)
    
    def generate_key(
        self,
        request: Request,
        limit_by: str = "ip",
        user_id: str = None,
        tenant_id: str = None,
        endpoint: str = None
    ) -> str:
        """Generate rate limit key based on criteria."""
        parts = []
        
        if limit_by == "ip":
            client_ip = request.client.host if request.client else "unknown"
            parts.append(f"ip:{client_ip}")
        elif limit_by == "user" and user_id:
            parts.append(f"user:{user_id}")
        elif limit_by == "tenant" and tenant_id:
            parts.append(f"tenant:{tenant_id}")
        elif limit_by == "global":
            parts.append("global")
        
        if endpoint:
            parts.append(f"ep:{endpoint}")
        
        return ":".join(parts) if parts else "global"
    
    async def reset_limit(self, key: str, algorithm: RateLimitAlgorithm = None):
        """Reset rate limit for a key."""
        algo = algorithm or self.default_config.algorithm
        rate_limiter = self.algorithms.get(algo)
        if rate_limiter:
            await rate_limiter.reset(key)
    
    async def get_limit_status(self, key: str, config: RateLimitConfig = None) -> Dict:
        """Get current rate limit status without consuming quota."""
        config = config or self.default_config
        # Temporarily set high quota to get current count
        temp_config = RateLimitConfig(
            quota=999999999,
            window_size=config.window_size,
            algorithm=config.algorithm
        )
        result = await self.check_rate_limit(key, temp_config)
        
        return {
            "limit": result.limit,
            "remaining": result.remaining,
            "reset_time": result.reset_time,
            "window": result.window
        }
    
    def add_headers(self, response: Response, result: RateLimitResult):
        """Add rate limit headers to response."""
        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(result.reset_time),
        }
        
        if result.window:
            headers["X-RateLimit-Window"] = result.window
        
        if result.retry_after:
            headers["Retry-After"] = str(result.retry_after)
        
        for name, value in headers.items():
            response.headers[name] = value


# =============================================================================
# Decorators and Middleware
# =============================================================================

def rate_limit(
    limiter: RateLimiter,
    requests: int = 100,
    window: int = 60,
    key_func: Callable = None,
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW,
    burst: int = None
):
    """Decorator to rate limit a function."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"func:{func.__name__}"
            
            config = RateLimitConfig(
                quota=requests,
                window_size=window,
                algorithm=algorithm,
                burst_size=burst or requests
            )
            
            result = await limiter.check_rate_limit(key, config)
            
            if not result.allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(result.retry_after)}
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""
    
    def __init__(
        self,
        app,
        limiter: RateLimiter,
        default_config: RateLimitConfig = None,
        key_func: Callable = None,
        exclude_paths: List[str] = None
    ):
        self.app = app
        self.limiter = limiter
        self.default_config = default_config or RateLimitConfig()
        self.key_func = key_func
        self.exclude_paths = exclude_paths or ["/health", "/metrics"]
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        path = request.url.path
        
        # Check excluded paths
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            await self.app(scope, receive, send)
            return
        
        # Generate rate limit key
        if self.key_func:
            key = self.key_func(request)
        else:
            key = self.limiter.generate_key(request, limit_by="ip", endpoint=path)
        
        # Get config for this endpoint/tenant
        config = await self._get_config(request, path)
        
        # Check rate limit
        result = await self.limiter.check_rate_limit(key, config)
        
        if not result.allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": result.retry_after,
                    "limit": result.limit,
                    "window": result.window
                },
                headers={"Retry-After": str(result.retry_after)}
            )
            self.limiter.add_headers(response, result)
            await response(scope, receive, send)
            return
        
        # Store result for response headers
        scope["rate_limit_result"] = result
        
        # Create wrapper for send to add headers
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                headers.append((b"X-RateLimit-Limit", str(result.limit).encode()))
                headers.append((b"X-RateLimit-Remaining", str(result.remaining).encode()))
                headers.append((b"X-RateLimit-Reset", str(result.reset_time).encode()))
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_with_headers)
    
    async def _get_config(self, request: Request, path: str) -> RateLimitConfig:
        """Get rate limit config for request."""
        # Check for tenant-specific config
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id and tenant_id in self.default_config.tenant_limits:
            tenant_config = self.default_config.tenant_limits[tenant_id]
            return RateLimitConfig(
                quota=tenant_config.get("quota", self.default_config.quota),
                window_size=tenant_config.get("window", self.default_config.window_size),
                algorithm=RateLimitAlgorithm(tenant_config.get("algorithm", self.default_config.algorithm.value))
            )
        
        # Check for endpoint-specific config
        if path in self.default_config.endpoint_limits:
            ep_config = self.default_config.endpoint_limits[path]
            return RateLimitConfig(
                quota=ep_config.get("quota", self.default_config.quota),
                window_size=ep_config.get("window", self.default_config.window_size),
                algorithm=RateLimitAlgorithm(ep_config.get("algorithm", self.default_config.algorithm.value))
            )
        
        return self.default_config


# =============================================================================
# Multi-Tier Rate Limiting
# =============================================================================

class TieredRateLimiter:
    """
    Multi-tier rate limiting for enterprise use cases.
    
    Tiers (in order of check):
    1. Global - Protect the entire API
    2. Tenant - Per-organization limits
    3. User - Per-user limits
    4. Endpoint - Specific endpoint limits
    """
    
    def __init__(self, limiter: RateLimiter):
        self.limiter = limiter
        self.tier_configs: Dict[str, RateLimitConfig] = {}
    
    def set_tier_config(self, tier: str, config: RateLimitConfig):
        """Set configuration for a tier."""
        self.tier_configs[tier] = config
    
    async def check_all_tiers(
        self,
        request: Request,
        user_id: str = None,
        tenant_id: str = None,
        endpoint: str = None
    ) -> Tuple[bool, List[RateLimitResult]]:
        """Check all rate limit tiers."""
        results = []
        
        # Global tier
        if "global" in self.tier_configs:
            key = self.limiter.generate_key(request, limit_by="global")
            result = await self.limiter.check_rate_limit(key, self.tier_configs["global"])
            results.append(("global", result))
            if not result.allowed:
                return False, results
        
        # Tenant tier
        if tenant_id and "tenant" in self.tier_configs:
            key = self.limiter.generate_key(request, limit_by="tenant", tenant_id=tenant_id)
            config = self._get_tenant_config(tenant_id)
            result = await self.limiter.check_rate_limit(key, config)
            results.append((f"tenant:{tenant_id}", result))
            if not result.allowed:
                return False, results
        
        # User tier
        if user_id and "user" in self.tier_configs:
            key = self.limiter.generate_key(request, limit_by="user", user_id=user_id)
            result = await self.limiter.check_rate_limit(key, self.tier_configs["user"])
            results.append((f"user:{user_id}", result))
            if not result.allowed:
                return False, results
        
        # Endpoint tier
        if endpoint and "endpoint" in self.tier_configs:
            key = self.limiter.generate_key(request, limit_by="ip", endpoint=endpoint)
            result = await self.limiter.check_rate_limit(key, self.tier_configs["endpoint"])
            results.append((f"endpoint:{endpoint}", result))
            if not result.allowed:
                return False, results
        
        return True, results
    
    def _get_tenant_config(self, tenant_id: str) -> RateLimitConfig:
        """Get config for specific tenant."""
        base_config = self.tier_configs.get("tenant", RateLimitConfig())
        
        # Check for tenant override
        if tenant_id in base_config.tenant_limits:
            override = base_config.tenant_limits[tenant_id]
            return RateLimitConfig(
                quota=override.get("quota", base_config.quota),
                window_size=override.get("window_size", base_config.window_size),
                algorithm=override.get("algorithm", base_config.algorithm),
                burst_size=override.get("burst_size", base_config.burst_size)
            )
        
        return base_config


# =============================================================================
# Rate Limit Warming
# =============================================================================

class RateLimitWarmer:
    """Pre-warm rate limit buckets for expected traffic."""
    
    def __init__(self, limiter: RateLimiter):
        self.limiter = limiter
        self.warmed_keys: set = set()
    
    async def warm_bucket(self, key: str, config: RateLimitConfig, fill_percent: float = 0.8):
        """Pre-fill a token bucket."""
        if key in self.warmed_keys:
            return
        
        if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            bucket_key = f"{config.key_prefix}:bucket:{key}:tokens"
            tokens = int(config.burst_size * fill_percent)
            await self.limiter.redis.set(bucket_key, tokens, ex=3600)
            self.warmed_keys.add(key)
            logger.info(f"Warmed bucket for key: {key} with {tokens} tokens")
    
    async def warm_tenant_buckets(self, tenant_ids: List[str], config: RateLimitConfig):
        """Warm buckets for multiple tenants."""
        for tenant_id in tenant_ids:
            key = f"tenant:{tenant_id}"
            await self.warm_bucket(key, config)
    
    async def warm_endpoint_buckets(self, endpoints: List[str], config: RateLimitConfig):
        """Warm buckets for multiple endpoints."""
        for endpoint in endpoints:
            key = f"ep:{endpoint}"
            await self.warm_bucket(key, config)


# =============================================================================
# Factory and Configuration
# =============================================================================

def create_rate_limiter(
    redis_url: str = "redis://localhost:6379",
    default_algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW,
    default_quota: int = 1000,
    default_window: int = 60
) -> RateLimiter:
    """Create configured rate limiter."""
    redis_client = redis.from_url(redis_url)
    limiter = RateLimiter(redis_client)
    limiter.default_config = RateLimitConfig(
        algorithm=default_algorithm,
        quota=default_quota,
        window_size=default_window
    )
    return limiter


def create_enterprise_tiered_limiter(redis_url: str = None) -> TieredRateLimiter:
    """Create enterprise tiered rate limiter with sensible defaults."""
    limiter = create_rate_limiter(redis_url)
    tiered = TieredRateLimiter(limiter)
    
    # Global protection: 10,000 req/min
    tiered.set_tier_config("global", RateLimitConfig(
        quota=10000,
        window_size=60,
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    ))
    
    # Tenant tier: 1,000 req/min default
    tiered.set_tier_config("tenant", RateLimitConfig(
        quota=1000,
        window_size=60,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_size=100,
        tenant_limits={
            "premium": {"quota": 5000, "burst_size": 500},
            "enterprise": {"quota": 10000, "burst_size": 1000},
            "basic": {"quota": 100, "burst_size": 10}
        }
    ))
    
    # User tier: 100 req/min
    tiered.set_tier_config("user", RateLimitConfig(
        quota=100,
        window_size=60,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_size=20
    ))
    
    # Endpoint tier: specific limits for expensive operations
    tiered.set_tier_config("endpoint", RateLimitConfig(
        quota=10,
        window_size=60,
        algorithm=RateLimitAlgorithm.FIXED_WINDOW
    ))
    
    return tiered


# =============================================================================
# Usage Examples
# =============================================================================

"""
# Basic usage with FastAPI

from fastapi import FastAPI
from rate_limiter import create_rate_limiter, RateLimitMiddleware

app = FastAPI()
limiter = create_rate_limiter()

# Add middleware
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    default_config=RateLimitConfig(quota=100, window_size=60)
)

# Decorator usage
@app.get("/api/data")
@rate_limit(limiter, requests=10, window=60)
async def get_data():
    return {"data": "value"}

# Tiered usage
from rate_limiter import create_enterprise_tiered_limiter

tiered = create_enterprise_tiered_limiter()

@app.get("/api/expensive")
async def expensive_operation(request: Request):
    user_id = request.headers.get("X-User-ID")
    tenant_id = request.headers.get("X-Tenant-ID")
    
    allowed, results = await tiered.check_all_tiers(
        request,
        user_id=user_id,
        tenant_id=tenant_id,
        endpoint="/api/expensive"
    )
    
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return {"result": "expensive data"}
"""


if __name__ == "__main__":
    # Test the rate limiter
    async def test():
        limiter = create_rate_limiter()
        
        # Test token bucket
        config = RateLimitConfig(
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            requests_per_second=10.0,
            burst_size=5
        )
        
        print("Testing Token Bucket:")
        for i in range(10):
            result = await limiter.check_rate_limit("test:bucket", config)
            print(f"Request {i+1}: allowed={result.allowed}, remaining={result.remaining}")
            await asyncio.sleep(0.05)
        
        # Test sliding window
        config = RateLimitConfig(
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            quota=5,
            window_size=10
        )
        
        print("\nTesting Sliding Window:")
        for i in range(8):
            result = await limiter.check_rate_limit("test:sw", config)
            print(f"Request {i+1}: allowed={result.allowed}, remaining={result.remaining}")
    
    asyncio.run(test())
