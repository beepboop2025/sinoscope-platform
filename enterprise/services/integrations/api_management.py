"""
API Management System for DragonScope Enterprise.

Provides comprehensive API governance including:
- API key management with secure storage
- Usage tracking and quota enforcement
- Rate limiting per client
- Developer portal endpoints
- SDK generation

Example:
    >>> from dragonscope.enterprise.integrations.api_management import APIManager
    >>> 
    >>> api_mgr = APIManager()
    >>> 
    >>> # Create API key
    >>> api_key = api_mgr.create_key(
    ...     owner="enterprise_client_123",
    ...     tier="enterprise",
    ...     allowed_ips=["192.168.1.0/24"]
    ... )
    >>> 
    >>> # Validate and track usage
    >>> if api_mgr.validate_request(api_key.key, endpoint="/market/quote"):
    ...     api_mgr.record_usage(api_key.key, endpoint="/market/quote")
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict
import base64

# Configure logging
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API management errors."""
    pass


class APIKeyError(APIError):
    """API key related error."""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded error."""
    pass


class QuotaExceededError(APIError):
    """Quota exceeded error."""
    pass


class APIKeyStatus(Enum):
    """API key status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APITier(Enum):
    """API access tiers."""
    DEVELOPER = "developer"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    PARTNER = "partner"


@dataclass
class APIKey:
    """API key data model."""
    id: str
    key: str  # The actual API key (hashed in storage)
    hashed_key: str  # SHA-256 hash of key for lookup
    owner: str
    tier: APITier
    status: APIKeyStatus
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    allowed_ips: Optional[List[str]]
    allowed_origins: Optional[List[str]]
    metadata: Dict[str, Any]
    
    # Quota tracking
    quota_reset_at: datetime
    requests_this_period: int = 0
    
    def to_dict(self, include_key: bool = False) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "owner": self.owner,
            "tier": self.tier.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "quota_reset_at": self.quota_reset_at.isoformat(),
            "requests_this_period": self.requests_this_period,
            "allowed_ips": self.allowed_ips,
            "allowed_origins": self.allowed_origins,
            "metadata": self.metadata,
        }
        if include_key:
            result["key"] = self.key
        return result


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: int
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "requests_per_second": self.requests_per_second,
            "requests_per_minute": self.requests_per_minute,
            "requests_per_hour": self.requests_per_hour,
            "requests_per_day": self.requests_per_day,
            "burst_size": self.burst_size,
        }


@dataclass
class QuotaConfig:
    """Quota configuration per tier."""
    requests_per_month: int
    websocket_connections: int
    historical_data_years: int
    real_time_symbols: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "requests_per_month": self.requests_per_month,
            "websocket_connections": self.websocket_connections,
            "historical_data_years": self.historical_data_years,
            "real_time_symbols": self.real_time_symbols,
        }


@dataclass
class UsageRecord:
    """API usage record."""
    id: str
    key_id: str
    endpoint: str
    method: str
    timestamp: datetime
    status_code: int
    response_time_ms: int
    bytes_in: int
    bytes_out: int
    ip_address: Optional[str]
    user_agent: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key_id": self.key_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "timestamp": self.timestamp.isoformat(),
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


# Tier configurations
TIER_RATE_LIMITS: Dict[APITier, RateLimitConfig] = {
    APITier.DEVELOPER: RateLimitConfig(
        requests_per_second=2,
        requests_per_minute=100,
        requests_per_hour=1000,
        requests_per_day=10000,
        burst_size=5,
    ),
    APITier.PROFESSIONAL: RateLimitConfig(
        requests_per_second=20,
        requests_per_minute=1000,
        requests_per_hour=10000,
        requests_per_day=100000,
        burst_size=50,
    ),
    APITier.ENTERPRISE: RateLimitConfig(
        requests_per_second=100,
        requests_per_minute=10000,
        requests_per_hour=100000,
        requests_per_day=1000000,
        burst_size=200,
    ),
    APITier.PARTNER: RateLimitConfig(
        requests_per_second=200,
        requests_per_minute=20000,
        requests_per_hour=200000,
        requests_per_day=5000000,
        burst_size=500,
    ),
}

TIER_QUOTAS: Dict[APITier, QuotaConfig] = {
    APITier.DEVELOPER: QuotaConfig(
        requests_per_month=10000,
        websocket_connections=1,
        historical_data_years=1,
        real_time_symbols=10,
    ),
    APITier.PROFESSIONAL: QuotaConfig(
        requests_per_month=100000,
        websocket_connections=10,
        historical_data_years=5,
        real_time_symbols=100,
    ),
    APITier.ENTERPRISE: QuotaConfig(
        requests_per_month=10000000,
        websocket_connections=100,
        historical_data_years=20,
        real_time_symbols=1000,
    ),
    APITier.PARTNER: QuotaConfig(
        requests_per_month=100000000,
        websocket_connections=500,
        historical_data_years=50,
        real_time_symbols=10000,
    ),
}


class TokenBucket:
    """Token bucket for rate limiting."""
    
    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        refill_period: float = 1.0
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_period = refill_period
        
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Attempt to consume tokens.
        
        Returns:
            Tuple of (success, retry_after_seconds)
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            
            # Refill tokens
            self.tokens = min(
                self.capacity,
                self.tokens + (elapsed / self.refill_period) * self.refill_rate
            )
            self.last_refill = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = (tokens_needed / self.refill_rate) * self.refill_period
            
            return False, wait_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bucket statistics."""
        return {
            "capacity": self.capacity,
            "tokens_available": self.tokens,
            "refill_rate": self.refill_rate,
        }


class APIManager:
    """
    API key management and access control for DragonScope Enterprise.
    
    Features:
    - Secure API key generation and storage
    - Tier-based rate limiting
    - Usage quotas and tracking
    - IP and origin allowlisting
    - SDK generation
    - Developer portal endpoints
    
    Args:
        storage_backend: Optional persistent storage
        enable_rate_limiting: Enable rate limiting (default: True)
        enable_quotas: Enable quota enforcement (default: True)
        quota_reset_day: Day of month for quota reset (default: 1)
    
    Example:
        >>> api_mgr = APIManager()
        >>> 
        >>> # Create API key
        >>> api_key = api_mgr.create_key(
        ...     owner="hedgefund@example.com",
        ...     tier=APITier.ENTERPRISE,
        ...     expires_in_days=365
        ... )
        >>> print(f"Key: {api_key.key}")  # Show only once
        >>> 
        >>> # Validate request
        >>> if api_mgr.validate_request(api_key.key, ip="192.168.1.100"):
        ...     api_mgr.record_usage(api_key.id, "/market/quote", "GET", 200, 45)
    """
    
    # Standard endpoints
    ENDPOINTS = {
        # Market Data
        "/api/v1/market/quote": {"methods": ["GET"], "tier": APITier.DEVELOPER},
        "/api/v1/market/history": {"methods": ["GET"], "tier": APITier.PROFESSIONAL},
        "/api/v1/market/chain": {"methods": ["GET"], "tier": APITier.PROFESSIONAL},
        "/api/v1/market/screener": {"methods": ["POST"], "tier": APITier.PROFESSIONAL},
        "/api/v1/market/options": {"methods": ["GET"], "tier": APITier.PROFESSIONAL},
        
        # Analytics
        "/api/v1/analytics/signals": {"methods": ["GET"], "tier": APITier.PROFESSIONAL},
        "/api/v1/analytics/risk": {"methods": ["POST"], "tier": APITier.ENTERPRISE},
        "/api/v1/analytics/backtest": {"methods": ["POST"], "tier": APITier.ENTERPRISE},
        "/api/v1/analytics/ai/insights": {"methods": ["GET"], "tier": APITier.ENTERPRISE},
        
        # Portfolio
        "/api/v1/portfolio": {"methods": ["GET", "POST"], "tier": APITier.PROFESSIONAL},
        "/api/v1/portfolio/positions": {"methods": ["GET", "POST", "DELETE"], "tier": APITier.PROFESSIONAL},
        "/api/v1/orders": {"methods": ["GET", "POST"], "tier": APITier.ENTERPRISE},
        
        # WebSocket
        "/ws/v1/market": {"methods": ["WS"], "tier": APITier.PROFESSIONAL},
        "/ws/v1/portfolio": {"methods": ["WS"], "tier": APITier.ENTERPRISE},
        
        # Admin
        "/api/v1/account/usage": {"methods": ["GET"], "tier": APITier.DEVELOPER},
        "/api/v1/account/quota": {"methods": ["GET"], "tier": APITier.DEVELOPER},
        "/api/v1/webhooks": {"methods": ["GET", "POST"], "tier": APITier.PROFESSIONAL},
    }
    
    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        enable_rate_limiting: bool = True,
        enable_quotas: bool = True,
        quota_reset_day: int = 1,
    ):
        self.storage = storage_backend
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_quotas = enable_quotas
        self.quota_reset_day = quota_reset_day
        
        # In-memory storage
        self._keys: Dict[str, APIKey] = {}  # key_id -> APIKey
        self._key_lookup: Dict[str, str] = {}  # hashed_key -> key_id
        self._usage_records: List[UsageRecord] = []
        
        # Rate limiting buckets
        self._rate_buckets: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)
        
        # Statistics
        self._stats = {
            "keys_created": 0,
            "keys_active": 0,
            "requests_total": 0,
            "requests_blocked": 0,
            "rate_limits_hit": 0,
            "quotas_exceeded": 0,
        }
    
    # API Key Management
    
    def create_key(
        self,
        owner: str,
        tier: Union[APITier, str] = APITier.DEVELOPER,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> APIKey:
        """
        Create a new API key.
        
        Args:
            owner: Owner identifier (email, org ID, etc.)
            tier: Access tier
            description: Human-readable description
            expires_in_days: Key expiration (None for no expiration)
            allowed_ips: Allowed IP ranges (CIDR notation)
            allowed_origins: Allowed CORS origins
            metadata: Custom metadata
        
        Returns:
            APIKey (key is only exposed here)
        
        Raises:
            APIKeyError: If validation fails
        """
        # Convert tier string to enum
        if isinstance(tier, str):
            tier = APITier(tier.lower())
        
        # Generate key
        key_value = self._generate_key()
        hashed_key = self._hash_key(key_value)
        key_id = f"key_{uuid.uuid4().hex[:16]}"
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create key object
        api_key = APIKey(
            id=key_id,
            key=key_value,
            hashed_key=hashed_key,
            owner=owner,
            tier=tier,
            status=APIKeyStatus.ACTIVE,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            last_used_at=None,
            allowed_ips=allowed_ips,
            allowed_origins=allowed_origins,
            metadata={
                "description": description,
                **(metadata or {}),
            },
            quota_reset_at=self._get_next_quota_reset(),
        )
        
        # Store key
        self._keys[key_id] = api_key
        self._key_lookup[hashed_key] = key_id
        
        # Initialize rate limit buckets
        if self.enable_rate_limiting:
            self._init_rate_buckets(key_id, tier)
        
        self._stats["keys_created"] += 1
        self._stats["keys_active"] += 1
        
        logger.info(f"Created API key {key_id} for {owner} (tier: {tier.value})")
        
        return api_key
    
    def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: Key to revoke
        
        Returns:
            True if revoked, False if not found
        """
        key = self._keys.get(key_id)
        if not key:
            return False
        
        key.status = APIKeyStatus.REVOKED
        self._stats["keys_active"] -= 1
        
        logger.info(f"Revoked API key {key_id}")
        return True
    
    def suspend_key(self, key_id: str, reason: Optional[str] = None) -> bool:
        """
        Suspend an API key temporarily.
        
        Args:
            key_id: Key to suspend
            reason: Suspension reason
        
        Returns:
            True if suspended, False if not found
        """
        key = self._keys.get(key_id)
        if not key:
            return False
        
        key.status = APIKeyStatus.SUSPENDED
        if reason:
            key.metadata["suspension_reason"] = reason
        
        logger.info(f"Suspended API key {key_id}: {reason}")
        return True
    
    def activate_key(self, key_id: str) -> bool:
        """
        Activate a suspended API key.
        
        Args:
            key_id: Key to activate
        
        Returns:
            True if activated, False if not found
        """
        key = self._keys.get(key_id)
        if not key:
            return False
        
        if key.status == APIKeyStatus.SUSPENDED:
            key.status = APIKeyStatus.ACTIVE
            key.metadata.pop("suspension_reason", None)
            logger.info(f"Activated API key {key_id}")
            return True
        
        return False
    
    def get_key(self, key_id: str) -> Optional[APIKey]:
        """
        Get API key by ID (key value not exposed).
        
        Args:
            key_id: Key identifier
        
        Returns:
            APIKey without key value, or None
        """
        key = self._keys.get(key_id)
        if key:
            # Return copy without actual key
            result = APIKey(
                id=key.id,
                key="***",
                hashed_key=key.hashed_key,
                owner=key.owner,
                tier=key.tier,
                status=key.status,
                created_at=key.created_at,
                expires_at=key.expires_at,
                last_used_at=key.last_used_at,
                allowed_ips=key.allowed_ips,
                allowed_origins=key.allowed_origins,
                metadata=key.metadata,
                quota_reset_at=key.quota_reset_at,
                requests_this_period=key.requests_this_period,
            )
            return result
        return None
    
    def list_keys(
        self,
        owner: Optional[str] = None,
        tier: Optional[APITier] = None,
        status: Optional[APIKeyStatus] = None,
    ) -> List[APIKey]:
        """
        List API keys with optional filtering.
        
        Args:
            owner: Filter by owner
            tier: Filter by tier
            status: Filter by status
        
        Returns:
            List of API keys (without key values)
        """
        keys = list(self._keys.values())
        
        if owner:
            keys = [k for k in keys if k.owner == owner]
        if tier:
            keys = [k for k in keys if k.tier == tier]
        if status:
            keys = [k for k in keys if k.status == status]
        
        return [self.get_key(k.id) for k in keys]
    
    def update_key(
        self,
        key_id: str,
        **updates
    ) -> Optional[APIKey]:
        """
        Update API key properties.
        
        Args:
            key_id: Key to update
            **updates: Fields to update
        
        Returns:
            Updated key or None if not found
        """
        key = self._keys.get(key_id)
        if not key:
            return None
        
        allowed_fields = {
            "tier", "allowed_ips", "allowed_origins", 
            "expires_at", "metadata"
        }
        
        for field_name, value in updates.items():
            if field_name in allowed_fields:
                if field_name == "tier" and isinstance(value, str):
                    value = APITier(value.lower())
                setattr(key, field_name, value)
        
        key.metadata["updated_at"] = datetime.utcnow().isoformat()
        
        return self.get_key(key_id)
    
    # Validation and Rate Limiting
    
    def validate_request(
        self,
        api_key: str,
        endpoint: Optional[str] = None,
        method: str = "GET",
        ip: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an API request.
        
        Args:
            api_key: The API key from request header
            endpoint: Request endpoint
            method: HTTP method
            ip: Client IP address
            origin: Request origin
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Hash key for lookup
        hashed_key = self._hash_key(api_key)
        key_id = self._key_lookup.get(hashed_key)
        
        if not key_id:
            self._stats["requests_blocked"] += 1
            return False, "Invalid API key"
        
        key = self._keys.get(key_id)
        if not key:
            return False, "Key not found"
        
        # Check status
        if key.status == APIKeyStatus.REVOKED:
            self._stats["requests_blocked"] += 1
            return False, "API key has been revoked"
        
        if key.status == APIKeyStatus.SUSPENDED:
            self._stats["requests_blocked"] += 1
            return False, "API key is suspended"
        
        # Check expiration
        if key.expires_at and datetime.utcnow() > key.expires_at:
            key.status = APIKeyStatus.EXPIRED
            self._stats["requests_blocked"] += 1
            return False, "API key has expired"
        
        # Check IP allowlist
        if key.allowed_ips and ip:
            if not self._ip_in_ranges(ip, key.allowed_ips):
                self._stats["requests_blocked"] += 1
                return False, "IP address not allowed"
        
        # Check origin
        if key.allowed_origins and origin:
            if origin not in key.allowed_origins:
                self._stats["requests_blocked"] += 1
                return False, "Origin not allowed"
        
        # Check endpoint access
        if endpoint:
            endpoint_info = self.ENDPOINTS.get(endpoint)
            if endpoint_info:
                min_tier = endpoint_info.get("tier", APITier.DEVELOPER)
                if self._tier_rank(key.tier) < self._tier_rank(min_tier):
                    return False, f"Endpoint requires {min_tier.value} tier or higher"
        
        return True, None
    
    async def check_rate_limit(
        self,
        api_key: str,
        endpoint: Optional[str] = None
    ) -> Tuple[bool, Optional[float]]:
        """
        Check rate limit for request.
        
        Args:
            api_key: The API key
            endpoint: Request endpoint (for endpoint-specific limits)
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        if not self.enable_rate_limiting:
            return True, None
        
        hashed_key = self._hash_key(api_key)
        key_id = self._key_lookup.get(hashed_key)
        
        if not key_id:
            return False, None
        
        key = self._keys.get(key_id)
        if not key:
            return False, None
        
        # Check and reset quota if needed
        self._check_quota_reset(key)
        
        # Get rate limit config
        config = TIER_RATE_LIMITS.get(key.tier)
        if not config:
            return True, None
        
        # Check per-second bucket
        bucket = self._rate_buckets[key_id].get("per_second")
        if bucket:
            allowed, retry_after = await bucket.consume(1)
            if not allowed:
                self._stats["rate_limits_hit"] += 1
                return False, retry_after
        
        # Check per-minute bucket
        bucket = self._rate_buckets[key_id].get("per_minute")
        if bucket:
            allowed, retry_after = await bucket.consume(1)
            if not allowed:
                self._stats["rate_limits_hit"] += 1
                return False, retry_after
        
        return True, None
    
    def record_usage(
        self,
        key_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
        bytes_in: int = 0,
        bytes_out: int = 0,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UsageRecord:
        """
        Record API usage.
        
        Args:
            key_id: API key ID
            endpoint: Request endpoint
            method: HTTP method
            status_code: Response status code
            response_time_ms: Response time in milliseconds
            bytes_in: Request size
            bytes_out: Response size
            ip: Client IP
            user_agent: Client user agent
        
        Returns:
            UsageRecord
        """
        key = self._keys.get(key_id)
        if key:
            key.last_used_at = datetime.utcnow()
            key.requests_this_period += 1
        
        record = UsageRecord(
            id=f"use_{uuid.uuid4().hex[:12]}",
            key_id=key_id,
            endpoint=endpoint,
            method=method,
            timestamp=datetime.utcnow(),
            status_code=status_code,
            response_time_ms=response_time_ms,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            ip_address=ip,
            user_agent=user_agent,
        )
        
        self._usage_records.append(record)
        self._stats["requests_total"] += 1
        
        return record
    
    def get_usage_stats(
        self,
        key_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics.
        
        Args:
            key_id: Filter by key
            start_time: Start of period
            end_time: End of period
        
        Returns:
            Usage statistics
        """
        records = self._usage_records
        
        if key_id:
            records = [r for r in records if r.key_id == key_id]
        if start_time:
            records = [r for r in records if r.timestamp >= start_time]
        if end_time:
            records = [r for r in records if r.timestamp <= end_time]
        
        if not records:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "error_requests": 0,
                "avg_response_time_ms": 0,
                "total_bytes_in": 0,
                "total_bytes_out": 0,
            }
        
        total = len(records)
        successful = sum(1 for r in records if 200 <= r.status_code < 300)
        errors = total - successful
        
        avg_response_time = sum(r.response_time_ms for r in records) / total
        total_bytes_in = sum(r.bytes_in for r in records)
        total_bytes_out = sum(r.bytes_out for r in records)
        
        # Endpoint breakdown
        endpoint_counts: Dict[str, int] = defaultdict(int)
        for r in records:
            endpoint_counts[r.endpoint] += 1
        
        return {
            "total_requests": total,
            "successful_requests": successful,
            "error_requests": errors,
            "avg_response_time_ms": round(avg_response_time, 2),
            "total_bytes_in": total_bytes_in,
            "total_bytes_out": total_bytes_out,
            "endpoint_breakdown": dict(endpoint_counts),
        }
    
    def get_quota_status(self, key_id: str) -> Optional[Dict[str, Any]]:
        """
        Get quota status for an API key.
        
        Args:
            key_id: API key ID
        
        Returns:
            Quota status or None if key not found
        """
        key = self._keys.get(key_id)
        if not key:
            return None
        
        self._check_quota_reset(key)
        
        quota = TIER_QUOTAS.get(key.tier)
        if not quota:
            return None
        
        return {
            "tier": key.tier.value,
            "requests_per_month": quota.requests_per_month,
            "requests_used": key.requests_this_period,
            "requests_remaining": max(0, quota.requests_per_month - key.requests_this_period),
            "reset_at": key.quota_reset_at.isoformat(),
            "websocket_connections": quota.websocket_connections,
            "historical_data_years": quota.historical_data_years,
            "real_time_symbols": quota.real_time_symbols,
        }
    
    # SDK Generation
    
    def generate_sdk(
        self,
        language: str,
        tier: APITier = APITier.DEVELOPER,
        include_examples: bool = True,
    ) -> str:
        """
        Generate client SDK code.
        
        Args:
            language: Target language (python, javascript, go, rust)
            tier: API tier (determines available endpoints)
            include_examples: Include example code
        
        Returns:
            Generated SDK code
        """
        generators = {
            "python": self._generate_python_sdk,
            "javascript": self._generate_javascript_sdk,
            "go": self._generate_go_sdk,
            "rust": self._generate_rust_sdk,
        }
        
        generator = generators.get(language.lower())
        if not generator:
            raise ValueError(f"Unsupported language: {language}")
        
        return generator(tier, include_examples)
    
    def _generate_python_sdk(
        self,
        tier: APITier,
        include_examples: bool
    ) -> str:
        """Generate Python SDK."""
        code = '''"""
DragonScope Python SDK

Generated SDK for DragonScope Enterprise API
"""

import requests
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Quote:
    """Market quote data."""
    symbol: str
    price: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime


class DragonScopeClient:
    """DragonScope API Client."""
    
    BASE_URL = "https://api.dragonscope.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-DS-API-Key": api_key,
            "Content-Type": "application/json",
        })
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make API request."""
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_quote(self, symbol: str) -> Quote:
        """Get current market quote."""
        data = self._request("GET", f"/api/v1/market/quote/{symbol}")
        return Quote(
            symbol=data["symbol"],
            price=data["price"],
            bid=data["bid"],
            ask=data["ask"],
            volume=data["volume"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
    
    def get_history(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d"
    ) -> List[Dict]:
        """Get historical price data."""
        return self._request(
            "GET",
            f"/api/v1/market/history/{symbol}",
            params={"start": start, "end": end, "interval": interval}
        )
    
    def get_account_usage(self) -> Dict[str, Any]:
        """Get account usage statistics."""
        return self._request("GET", "/api/v1/account/usage")
'''
        
        if include_examples:
            code += '''


# Example Usage
if __name__ == "__main__":
    client = DragonScopeClient(api_key="your_api_key_here")
    
    # Get quote
    quote = client.get_quote("AAPL")
    print(f"AAPL: ${quote.price}")
    
    # Get history
    history = client.get_history(
        "AAPL",
        start="2024-01-01",
        end="2024-01-31"
    )
    print(f"Retrieved {len(history)} bars")
    
    # Get usage
    usage = client.get_account_usage()
    print(f"Requests this month: {usage['requests_this_period']}")
'''
        
        return code
    
    def _generate_javascript_sdk(
        self,
        tier: APITier,
        include_examples: bool
    ) -> str:
        """Generate JavaScript/TypeScript SDK."""
        code = '''/**
 * DragonScope JavaScript SDK
 * 
 * Generated SDK for DragonScope Enterprise API
 */

class DragonScopeClient {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.baseUrl = "https://api.dragonscope.com";
  }

  async _request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        "X-DS-API-Key": this.apiKey,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return response.json();
  }

  /**
   * Get current market quote
   * @param {string} symbol - Stock symbol
   * @returns {Promise<Object>} Quote data
   */
  async getQuote(symbol) {
    return this._request(`/api/v1/market/quote/${symbol}`);
  }

  /**
   * Get historical price data
   * @param {string} symbol - Stock symbol
   * @param {string} start - Start date (YYYY-MM-DD)
   * @param {string} end - End date (YYYY-MM-DD)
   * @param {string} interval - Data interval (1d, 1h, etc.)
   * @returns {Promise<Array>} Historical bars
   */
  async getHistory(symbol, start, end, interval = "1d") {
    const params = new URLSearchParams({ start, end, interval });
    return this._request(`/api/v1/market/history/${symbol}?${params}`);
  }

  /**
   * Get account usage statistics
   * @returns {Promise<Object>} Usage data
   */
  async getAccountUsage() {
    return this._request("/api/v1/account/usage");
  }

  /**
   * Create WebSocket connection for real-time data
   * @param {string} stream - Stream type (market, portfolio, alerts)
   * @returns {WebSocket} WebSocket connection
   */
  connectWebSocket(stream = "market") {
    const ws = new WebSocket(`wss://api.dragonscope.com/ws/v1/${stream}`);
    
    ws.onopen = () => {
      // Authenticate
      ws.send(JSON.stringify({
        type: "auth",
        api_key: this.apiKey
      }));
    };
    
    return ws;
  }
}

module.exports = { DragonScopeClient };
'''
        
        if include_examples:
            code += '''

// Example Usage
async function example() {
  const client = new DragonScopeClient("your_api_key_here");
  
  try {
    // Get quote
    const quote = await client.getQuote("AAPL");
    console.log(`AAPL: $${quote.price}`);
    
    // Get history
    const history = await client.getHistory("AAPL", "2024-01-01", "2024-01-31");
    console.log(`Retrieved ${history.length} bars`);
    
    // WebSocket streaming
    const ws = client.connectWebSocket("market");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("Price update:", data);
    };
    
  } catch (error) {
    console.error("API error:", error);
  }
}

example();
'''
        
        return code
    
    def _generate_go_sdk(self, tier: APITier, include_examples: bool) -> str:
        """Generate Go SDK."""
        code = '''package dragonscope

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

const (
	BaseURL = "https://api.dragonscope.com"
)

// Client represents a DragonScope API client
type Client struct {
	APIKey     string
	HTTPClient *http.Client
	BaseURL    string
}

// Quote represents a market quote
type Quote struct {
	Symbol    string    `json:"symbol"`
	Price     float64   `json:"price"`
	Bid       float64   `json:"bid"`
	Ask       float64   `json:"ask"`
	Volume    int64     `json:"volume"`
	Timestamp time.Time `json:"timestamp"`
}

// NewClient creates a new DragonScope client
func NewClient(apiKey string) *Client {
	return &Client{
		APIKey: apiKey,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		BaseURL: BaseURL,
	}
}

// GetQuote retrieves current market quote
func (c *Client) GetQuote(symbol string) (*Quote, error) {
	url := fmt.Sprintf("%s/api/v1/market/quote/%s", c.BaseURL, symbol)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("X-DS-API-Key", c.APIKey)
	
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var quote Quote
	if err := json.NewDecoder(resp.Body).Decode(&quote); err != nil {
		return nil, err
	}
	
	return &quote, nil
}
'''
        return code
    
    def _generate_rust_sdk(self, tier: APITier, include_examples: bool) -> str:
        """Generate Rust SDK."""
        code = '''use reqwest::header::{HeaderMap, HeaderValue};
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

const BASE_URL: &str = "https://api.dragonscope.com";

/// DragonScope API Client
pub struct Client {
    api_key: String,
    http_client: reqwest::Client,
}

/// Market quote data
#[derive(Debug, Deserialize)]
pub struct Quote {
    pub symbol: String,
    pub price: f64,
    pub bid: f64,
    pub ask: f64,
    pub volume: i64,
    pub timestamp: DateTime<Utc>,
}

impl Client {
    /// Create a new DragonScope client
    pub fn new(api_key: impl Into<String>) -> Self {
        let api_key = api_key.into();
        
        let mut headers = HeaderMap::new();
        headers.insert(
            "X-DS-API-Key",
            HeaderValue::from_str(&api_key).unwrap(),
        );
        
        let http_client = reqwest::Client::builder()
            .default_headers(headers)
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .unwrap();
        
        Self {
            api_key,
            http_client,
        }
    }
    
    /// Get current market quote
    pub async fn get_quote(&self, symbol: &str) -> Result<Quote, reqwest::Error> {
        let url = format!("{}/api/v1/market/quote/{}", BASE_URL, symbol);
        let response = self.http_client.get(&url).send().await?;
        let quote = response.json::<Quote>().await?;
        Ok(quote)
    }
}
'''
        return code
    
    # Developer Portal Endpoints
    
    def get_developer_portal_data(self, key_id: str) -> Dict[str, Any]:
        """
        Get data for developer portal dashboard.
        
        Args:
            key_id: API key ID
        
        Returns:
            Portal dashboard data
        """
        key = self._keys.get(key_id)
        if not key:
            raise APIKeyError("Key not found")
        
        quota_status = self.get_quota_status(key_id)
        usage_stats = self.get_usage_stats(key_id)
        
        # Get available endpoints for tier
        available_endpoints = [
            {
                "path": path,
                "methods": info["methods"],
                "description": self._get_endpoint_description(path),
            }
            for path, info in self.ENDPOINTS.items()
            if self._tier_rank(key.tier) >= self._tier_rank(info.get("tier", APITier.DEVELOPER))
        ]
        
        return {
            "api_key": {
                "id": key.id,
                "tier": key.tier.value,
                "status": key.status.value,
                "created_at": key.created_at.isoformat(),
            },
            "quota": quota_status,
            "usage": usage_stats,
            "available_endpoints": available_endpoints,
            "sdks": ["python", "javascript", "go", "rust"],
        }
    
    def _get_endpoint_description(self, endpoint: str) -> str:
        """Get description for endpoint."""
        descriptions = {
            "/api/v1/market/quote": "Get real-time market quote",
            "/api/v1/market/history": "Get historical price data",
            "/api/v1/market/chain": "Get option chain data",
            "/api/v1/market/screener": "Run equity screener",
            "/api/v1/analytics/signals": "Get trading signals",
            "/api/v1/portfolio": "Portfolio management",
            "/api/v1/orders": "Order management",
        }
        return descriptions.get(endpoint, "API endpoint")
    
    # Helper methods
    
    def _generate_key(self) -> str:
        """Generate secure API key."""
        # Format: ds_live_xxxxxxxxxxxx (48 chars total)
        prefix = "ds_live_"
        random_part = secrets.token_urlsafe(32)
        return prefix + random_part[:40]
    
    def _hash_key(self, key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def _init_rate_buckets(self, key_id: str, tier: APITier) -> None:
        """Initialize rate limit token buckets."""
        config = TIER_RATE_LIMITS.get(tier)
        if not config:
            return
        
        self._rate_buckets[key_id] = {
            "per_second": TokenBucket(
                capacity=config.burst_size,
                refill_rate=config.requests_per_second,
            ),
            "per_minute": TokenBucket(
                capacity=config.requests_per_minute,
                refill_rate=config.requests_per_minute / 60,
            ),
        }
    
    def _check_quota_reset(self, key: APIKey) -> None:
        """Check and reset quota if needed."""
        now = datetime.utcnow()
        if now >= key.quota_reset_at:
            key.requests_this_period = 0
            key.quota_reset_at = self._get_next_quota_reset()
    
    def _get_next_quota_reset(self) -> datetime:
        """Calculate next quota reset date."""
        now = datetime.utcnow()
        
        # Reset on specified day of next month
        if now.day >= self.quota_reset_day:
            # Next month
            if now.month == 12:
                reset = now.replace(year=now.year + 1, month=1, day=self.quota_reset_day)
            else:
                reset = now.replace(month=now.month + 1, day=self.quota_reset_day)
        else:
            # This month
            reset = now.replace(day=self.quota_reset_day)
        
        return reset
    
    def _tier_rank(self, tier: APITier) -> int:
        """Get numeric rank for tier comparison."""
        ranks = {
            APITier.DEVELOPER: 1,
            APITier.PROFESSIONAL: 2,
            APITier.ENTERPRISE: 3,
            APITier.PARTNER: 4,
        }
        return ranks.get(tier, 0)
    
    def _ip_in_ranges(self, ip: str, ranges: List[str]) -> bool:
        """Check if IP is in allowed ranges."""
        # Simplified implementation - in production use ipaddress module
        import ipaddress
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            for range_str in ranges:
                if "/" in range_str:
                    network = ipaddress.ip_network(range_str, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    if str(ip_obj) == range_str:
                        return True
        except ValueError:
            pass
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            **self._stats,
            "total_keys": len(self._keys),
            "active_keys": sum(1 for k in self._keys.values() if k.status == APIKeyStatus.ACTIVE),
            "total_usage_records": len(self._usage_records),
        }
    
    def clear_old_usage(self, days: int = 90) -> int:
        """
        Clear old usage records.
        
        Args:
            days: Age threshold
        
        Returns:
            Number of records removed
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        original_count = len(self._usage_records)
        
        self._usage_records = [
            r for r in self._usage_records
            if r.timestamp >= cutoff
        ]
        
        return original_count - len(self._usage_records)


# Middleware for web frameworks

class APIKeyMiddleware:
    """
    Example middleware for validating API keys.
    
    Usage with FastAPI:
        from fastapi import Request, HTTPException
        
        @app.middleware("http")
        async def api_key_validation(request: Request, call_next):
            middleware = APIKeyMiddleware(api_manager)
            valid, error = await middleware.validate(request)
            if not valid:
                raise HTTPException(status_code=401, detail=error)
            return await call_next(request)
    """
    
    def __init__(self, api_manager: APIManager):
        self.api_manager = api_manager
    
    async def validate(self, request: Any) -> Tuple[bool, Optional[str]]:
        """Validate request API key."""
        # Extract API key from header
        api_key = request.headers.get("X-DS-API-Key")
        if not api_key:
            return False, "Missing API key"
        
        # Extract other info
        ip = request.client.host if hasattr(request, "client") else None
        origin = request.headers.get("Origin")
        endpoint = request.url.path if hasattr(request, "url") else None
        method = request.method if hasattr(request, "method") else "GET"
        
        # Validate
        valid, error = self.api_manager.validate_request(
            api_key=api_key,
            endpoint=endpoint,
            method=method,
            ip=ip,
            origin=origin,
        )
        
        if not valid:
            return False, error
        
        # Check rate limit
        allowed, retry_after = await self.api_manager.check_rate_limit(api_key, endpoint)
        if not allowed:
            return False, f"Rate limit exceeded. Retry after {retry_after}s"
        
        return True, None
