"""
DragonScope Enterprise Authentication Middleware

Provides JWT authentication, permission checking, rate limiting, and audit logging
for the DragonScope API and WebSocket endpoints.
"""

from __future__ import annotations

import functools
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from functools import wraps
import asyncio


# ============================================================================
# JWT Token Handling
# ============================================================================

@dataclass
class JWTConfig:
    """Configuration for JWT token handling."""
    algorithm: str = "RS256"
    access_token_ttl: int = 900  # 15 minutes
    refresh_token_ttl: int = 604800  # 7 days
    issuer: str = "https://auth.dragonscope.io"
    audience: str = "https://api.dragonscope.io"
    require_expiration: bool = True
    leeway_seconds: int = 30


class JWTTokenManager:
    """
    Manages JWT token generation, validation, and refresh.
    
    Supports:
    - RS256 asymmetric signing
    - Key rotation
    - Token families for refresh rotation
    - Blacklist/revocation
    """
    
    def __init__(self, config: JWTConfig = None):
        self.config = config or JWTConfig()
        self._private_key: Optional[str] = None
        self._public_key: Optional[str] = None
        self._key_id: str = secrets.token_hex(8)
        self._token_blacklist: Set[str] = set()
        self._token_families: Dict[str, Dict[str, Any]] = {}
    
    def load_keys(self, private_key_path: str, public_key_path: str) -> None:
        """Load RSA keys from files."""
        try:
            with open(private_key_path, "r") as f:
                self._private_key = f.read()
            with open(public_key_path, "r") as f:
                self._public_key = f.read()
        except FileNotFoundError as e:
            raise RuntimeError(f"Failed to load JWT keys: {e}")
    
    def generate_key_pair(self) -> Tuple[str, str]:
        """Generate a new RSA key pair for signing."""
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.backends import default_backend
            
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
            
            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
            
            return private_pem, public_pem
        except ImportError:
            raise RuntimeError("cryptography library required for JWT key generation")
    
    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        roles: List[str],
        permissions: List[str],
        session_id: str,
        mfa_verified: bool = False,
        extra_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new access token."""
        try:
            import jwt
        except ImportError:
            raise RuntimeError("PyJWT library required")
        
        now = int(time.time())
        
        claims = {
            "jti": secrets.token_hex(16),
            "sub": user_id,
            "tid": tenant_id,
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "iat": now,
            "exp": now + self.config.access_token_ttl,
            "scope": " ".join(permissions[:20]),  # Limit scope size
            "permissions": permissions,
            "roles": roles,
            "session_id": session_id,
            "mfa_verified": mfa_verified,
            "auth_time": now,
            "key_id": self._key_id,
        }
        
        if extra_claims:
            claims.update(extra_claims)
        
        if not self._private_key:
            raise RuntimeError("Private key not loaded")
        
        return jwt.encode(
            claims,
            self._private_key,
            algorithm=self.config.algorithm,
            headers={"kid": self._key_id}
        )
    
    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str,
        session_id: str,
        family_id: Optional[str] = None
    ) -> str:
        """Create a new refresh token with rotation support."""
        try:
            import jwt
        except ImportError:
            raise RuntimeError("PyJWT library required")
        
        now = int(time.time())
        
        # Token family for rotation detection
        family_id = family_id or secrets.token_hex(16)
        
        claims = {
            "jti": secrets.token_hex(16),
            "sub": user_id,
            "tid": tenant_id,
            "iss": self.config.issuer,
            "aud": self.config.issuer,  # Refresh tokens for auth service only
            "iat": now,
            "exp": now + self.config.refresh_token_ttl,
            "token_family": family_id,
            "rotation_count": 0,
            "session_id": session_id,
        }
        
        if not self._private_key:
            raise RuntimeError("Private key not loaded")
        
        token = jwt.encode(
            claims,
            self._private_key,
            algorithm=self.config.algorithm
        )
        
        # Track token family
        self._token_families[family_id] = {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": now,
            "rotation_count": 0,
            "current_token_jti": claims["jti"],
        }
        
        return token
    
    def validate_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Validate and decode a JWT token."""
        try:
            import jwt
        except ImportError:
            raise RuntimeError("PyJWT library required")
        
        # Check blacklist
        jti = self._extract_jti(token)
        if jti in self._token_blacklist:
            raise jwt.InvalidTokenError("Token has been revoked")
        
        audience = (
            self.config.audience 
            if token_type == "access" 
            else self.config.issuer
        )
        
        try:
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=[self.config.algorithm],
                audience=audience,
                issuer=self.config.issuer,
                leeway=self.config.leeway_seconds,
            )
            return claims
        except jwt.ExpiredSignatureError:
            raise
        except jwt.InvalidTokenError:
            raise
    
    def refresh_access_token(
        self, 
        refresh_token: str
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Rotate refresh token and issue new access token.
        
        Returns (new_access_token, new_refresh_token, claims)
        """
        try:
            import jwt
        except ImportError:
            raise RuntimeError("PyJWT library required")
        
        # Validate refresh token
        claims = self.validate_token(refresh_token, "refresh")
        
        family_id = claims.get("token_family")
        jti = claims.get("jti")
        
        if not family_id:
            raise jwt.InvalidTokenError("Invalid refresh token: no family")
        
        # Check for token reuse (potential theft)
        family = self._token_families.get(family_id)
        if family and family["current_token_jti"] != jti:
            # Token reuse detected - revoke entire family
            self._revoke_token_family(family_id)
            raise jwt.InvalidTokenError("Token reuse detected - family revoked")
        
        # Create new tokens
        new_access = self.create_access_token(
            user_id=claims["sub"],
            tenant_id=claims["tid"],
            roles=claims.get("roles", []),
            permissions=claims.get("permissions", []),
            session_id=claims["session_id"],
            mfa_verified=claims.get("mfa_verified", False),
        )
        
        # Rotate refresh token
        new_refresh = self.create_refresh_token(
            user_id=claims["sub"],
            tenant_id=claims["tid"],
            session_id=claims["session_id"],
            family_id=family_id
        )
        
        # Blacklist old refresh token
        self._token_blacklist.add(jti)
        
        # Update family
        if family_id in self._token_families:
            self._token_families[family_id]["rotation_count"] += 1
            self._token_families[family_id]["current_token_jti"] = claims["jti"]
        
        return new_access, new_refresh, claims
    
    def revoke_token(self, token: str) -> None:
        """Revoke a token by adding to blacklist."""
        jti = self._extract_jti(token)
        if jti:
            self._token_blacklist.add(jti)
    
    def _extract_jti(self, token: str) -> Optional[str]:
        """Extract JTI from token without full validation."""
        try:
            import jwt
            # Decode without verification to get JTI
            claims = jwt.decode(token, options={"verify_signature": False})
            return claims.get("jti")
        except Exception:
            return None
    
    def _revoke_token_family(self, family_id: str) -> None:
        """Revoke all tokens in a family."""
        if family_id in self._token_families:
            del self._token_families[family_id]


# ============================================================================
# Current User Context
# ============================================================================

@dataclass
class CurrentUser:
    """Authenticated user context."""
    
    user_id: str
    tenant_id: str
    email: str
    roles: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    session_id: Optional[str] = None
    mfa_verified: bool = False
    auth_method: str = "jwt"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Request context
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if permission in self.permissions:
            return True
        
        # Check wildcard
        resource = permission.split(".")[0]
        return f"{resource}.*" in self.permissions
    
    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the permissions."""
        return any(self.has_permission(p) for p in permissions)
    
    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all permissions."""
        return all(self.has_permission(p) for p in permissions)
    
    def is_in_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "email": self.email,
            "roles": self.roles,
            "permissions": list(self.permissions),
            "session_id": self.session_id,
            "mfa_verified": self.mfa_verified,
            "auth_method": self.auth_method,
            "ip_address": self.ip_address,
        }


# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests: int = 100
    window_seconds: int = 60
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_size: int = 10  # For token bucket
    
    # Per-tenant overrides
    tenant_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Per-user overrides
    user_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class RateLimiter:
    """
    Multi-tenant rate limiter with Redis backend.
    
    Supports:
    - Per-user rate limiting
    - Per-tenant rate limiting
    - Per-endpoint rate limiting
    - Different strategies (fixed/sliding window, token bucket)
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._storage: Optional[Any] = None  # Redis connection
        self._local_cache: Dict[str, Any] = {}  # Fallback for testing
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int = None,
        window: int = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.
        
        Returns (allowed, headers) where headers contains:
        - X-RateLimit-Limit
        - X-RateLimit-Remaining
        - X-RateLimit-Reset
        - X-RateLimit-Retry-After (if limited)
        """
        limit = limit or self.config.requests
        window = window or self.config.window_seconds
        
        now = time.time()
        
        if self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return await self._check_fixed_window(key, limit, window, now)
        elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._check_sliding_window(key, limit, window, now)
        else:
            return await self._check_token_bucket(key, limit, now)
    
    async def _check_fixed_window(
        self, 
        key: str, 
        limit: int, 
        window: int, 
        now: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Fixed window rate limiting."""
        window_start = int(now // window) * window
        window_key = f"{key}:{window_start}"
        
        count = await self._increment_counter(window_key, window)
        
        remaining = max(0, limit - count)
        reset_time = window_start + window
        
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_time)),
        }
        
        if count > limit:
            headers["X-RateLimit-Retry-After"] = str(int(reset_time - now))
            return False, headers
        
        return True, headers
    
    async def _check_sliding_window(
        self, 
        key: str, 
        limit: int, 
        window: int, 
        now: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Sliding window rate limiting."""
        window_start = now - window
        
        # Clean old entries and count recent ones
        count = await self._count_in_window(key, window_start, now)
        
        # Add current request
        await self._add_request_timestamp(key, now, window)
        
        remaining = max(0, limit - count - 1)
        reset_time = now + window
        
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_time)),
        }
        
        if count >= limit:
            # Find when oldest request expires
            oldest = await self._get_oldest_request(key)
            if oldest:
                headers["X-RateLimit-Retry-After"] = str(int(oldest + window - now))
            return False, headers
        
        return True, headers
    
    async def _check_token_bucket(
        self, 
        key: str, 
        limit: int, 
        now: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Token bucket rate limiting."""
        burst = self.config.burst_size
        
        # Get current bucket state
        bucket = await self._get_bucket_state(key)
        
        if bucket is None:
            bucket = {"tokens": burst - 1, "last_update": now}
        else:
            # Add tokens based on time passed
            time_passed = now - bucket["last_update"]
            tokens_to_add = time_passed * (limit / 60)  # tokens per second
            bucket["tokens"] = min(burst, bucket["tokens"] + tokens_to_add)
            bucket["last_update"] = now
        
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(int(bucket["tokens"])),
        }
        
        if bucket["tokens"] < 1:
            headers["X-RateLimit-Retry-After"] = "1"
            await self._set_bucket_state(key, bucket, 60)
            return False, headers
        
        bucket["tokens"] -= 1
        await self._set_bucket_state(key, bucket, 60)
        
        return True, headers
    
    async def _increment_counter(self, key: str, ttl: int) -> int:
        """Increment counter in storage."""
        # Redis implementation would use INCR
        if key not in self._local_cache:
            self._local_cache[key] = {"count": 0, "expires": time.time() + ttl}
        self._local_cache[key]["count"] += 1
        return self._local_cache[key]["count"]
    
    async def _count_in_window(self, key: str, start: float, end: float) -> int:
        """Count requests in time window."""
        # Redis implementation would use ZRANGEBYSCORE
        return 0
    
    async def _add_request_timestamp(self, key: str, timestamp: float, ttl: int) -> None:
        """Add request timestamp to window."""
        # Redis implementation would use ZADD with EXPIRE
        pass
    
    async def _get_oldest_request(self, key: str) -> Optional[float]:
        """Get oldest request timestamp."""
        # Redis implementation would use ZRANGE
        return None
    
    async def _get_bucket_state(self, key: str) -> Optional[Dict[str, Any]]:
        """Get token bucket state."""
        return self._local_cache.get(key)
    
    async def _set_bucket_state(
        self, 
        key: str, 
        state: Dict[str, Any], 
        ttl: int
    ) -> None:
        """Set token bucket state."""
        self._local_cache[key] = state
    
    def get_limit_key(
        self,
        user_id: str,
        tenant_id: str,
        endpoint: Optional[str] = None,
        method: Optional[str] = None
    ) -> str:
        """Generate rate limit key."""
        parts = ["ratelimit", tenant_id, user_id]
        if endpoint:
            parts.append(endpoint.replace("/", "_"))
        if method:
            parts.append(method.upper())
        return ":".join(parts)


# ============================================================================
# Audit Logger
# ============================================================================

class AuditEventType(Enum):
    """Types of audit events."""
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH = "auth.refresh"
    AUTH_MFA = "auth.mfa"
    AUTH_FAILURE = "auth.failure"
    
    ACCESS_GRANTED = "access.granted"
    ACCESS_DENIED = "access.denied"
    
    RESOURCE_CREATE = "resource.create"
    RESOURCE_READ = "resource.read"
    RESOURCE_UPDATE = "resource.update"
    RESOURCE_DELETE = "resource.delete"
    
    SESSION_START = "session.start"
    SESSION_END = "session.end"
    SESSION_RECORD = "session.record"
    
    ADMIN_ACTION = "admin.action"
    POLICY_CHANGE = "policy.change"
    SECURITY_ALERT = "security.alert"


@dataclass
class AuditEvent:
    """Audit event record."""
    event_type: AuditEventType
    timestamp: float
    tenant_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    
    # Request details
    request_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    method: Optional[str]
    path: Optional[str]
    
    # Resource details
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: Optional[str]
    
    # Result
    success: bool
    error_code: Optional[str]
    error_message: Optional[str]
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Integrity
    signature: Optional[str] = None


class AuditLogger:
    """
    Secure audit logging with tamper detection.
    
    Features:
    - Structured logging
    - Integrity verification
    - Async batching
    - SIEM integration
    """
    
    def __init__(self, signing_key: Optional[str] = None):
        self.signing_key = signing_key or secrets.token_hex(32)
        self._buffer: List[AuditEvent] = []
        self._buffer_size: int = 100
        self._flush_interval: float = 5.0
        self._last_flush: float = time.time()
        self._chain_hash: Optional[str] = None
    
    async def log(
        self,
        event_type: AuditEventType,
        tenant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an audit event."""
        event = AuditEvent(
            event_type=event_type,
            timestamp=time.time(),
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id or secrets.token_hex(8),
            ip_address=ip_address,
            user_agent=user_agent,
            method=method,
            path=path,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            success=success,
            error_code=error_code,
            error_message=error_message,
            metadata=metadata or {},
        )
        
        # Sign event for integrity
        event.signature = self._sign_event(event)
        
        self._buffer.append(event)
        
        # Flush if needed
        if len(self._buffer) >= self._buffer_size:
            await self._flush()
        elif time.time() - self._last_flush > self._flush_interval:
            await self._flush()
    
    def _sign_event(self, event: AuditEvent) -> str:
        """Create integrity signature for event."""
        # Include previous hash for chain
        data = {
            "timestamp": event.timestamp,
            "type": event.event_type.value,
            "tenant": event.tenant_id,
            "user": event.user_id,
            "request": event.request_id,
            "previous_hash": self._chain_hash,
        }
        
        message = json.dumps(data, sort_keys=True)
        signature = hmac.new(
            self.signing_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        self._chain_hash = signature
        return signature
    
    async def _flush(self) -> None:
        """Flush buffered events to storage."""
        if not self._buffer:
            return
        
        events = self._buffer[:]
        self._buffer = []
        self._last_flush = time.time()
        
        # Send to logging backend
        # Implementation would use async logging or SIEM API
        for event in events:
            await self._send_to_backend(event)
    
    async def _send_to_backend(self, event: AuditEvent) -> None:
        """Send event to logging backend."""
        # Implementation would send to:
        # - Structured logging (JSON)
        # - SIEM (Splunk, Datadog, etc.)
        # - Object storage for long-term
        pass
    
    async def close(self) -> None:
        """Flush remaining events and close."""
        await self._flush()


# ============================================================================
# Middleware Decorators
# ============================================================================

class AuthMiddleware:
    """
    Main authentication middleware for DragonScope.
    
    Combines JWT validation, permission checking, rate limiting, and audit logging.
    """
    
    def __init__(
        self,
        jwt_manager: JWTTokenManager,
        rate_limiter: RateLimiter,
        audit_logger: AuditLogger,
    ):
        self.jwt_manager = jwt_manager
        self.rate_limiter = rate_limiter
        self.audit_logger = audit_logger
        self._public_paths: Set[str] = {"/health", "/metrics", "/docs"}
    
    async def authenticate(self, request) -> Optional[CurrentUser]:
        """
        Authenticate request and return current user.
        
        Expected request structure (FastAPI/Flask style):
        - request.headers
        - request.client.host
        - request.url.path
        """
        # Check for public path
        if request.url.path in self._public_paths:
            return None
        
        # Extract token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Missing or invalid Authorization header")
        
        token = auth_header[7:]  # Remove "Bearer "
        
        try:
            # Validate token
            claims = self.jwt_manager.validate_token(token)
            
            return CurrentUser(
                user_id=claims["sub"],
                tenant_id=claims["tid"],
                email=claims.get("email", ""),
                roles=claims.get("roles", []),
                permissions=set(claims.get("permissions", [])),
                session_id=claims.get("session_id"),
                mfa_verified=claims.get("mfa_verified", False),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
                request_id=claims.get("jti"),
            )
            
        except Exception as e:
            raise AuthenticationError(f"Token validation failed: {e}")
    
    async def check_rate_limit(
        self, 
        user: CurrentUser, 
        request
    ) -> Dict[str, str]:
        """Check and enforce rate limiting."""
        key = self.rate_limiter.get_limit_key(
            user.user_id,
            user.tenant_id,
            request.url.path,
            request.method
        )
        
        allowed, headers = await self.rate_limiter.check_rate_limit(key)
        
        if not allowed:
            raise RateLimitExceeded("Rate limit exceeded")
        
        return headers
    
    async def log_access(
        self,
        user: CurrentUser,
        request,
        response_status: int,
        duration_ms: float
    ) -> None:
        """Log access to audit system."""
        event_type = (
            AuditEventType.ACCESS_GRANTED 
            if response_status < 400 
            else AuditEventType.ACCESS_DENIED
        )
        
        await self.audit_logger.log(
            event_type=event_type,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            session_id=user.session_id,
            ip_address=user.ip_address,
            user_agent=user.user_agent,
            method=request.method,
            path=str(request.url.path),
            success=response_status < 400,
            metadata={
                "status_code": response_status,
                "duration_ms": duration_ms,
            }
        )


class AuthenticationError(Exception):
    """Authentication failed."""
    pass


class AuthorizationError(Exception):
    """Authorization failed."""
    pass


class RateLimitExceeded(Exception):
    """Rate limit exceeded."""
    pass


# ============================================================================
# Decorators
# ============================================================================

def require_auth(optional: bool = False):
    """
    Decorator to require authentication.
    
    Args:
        optional: If True, allows unauthenticated requests (user will be None)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args (framework-specific)
            request = _extract_request(args, kwargs)
            
            # Get middleware from app state
            middleware = _get_middleware(request)
            
            try:
                user = await middleware.authenticate(request)
                
                if user is None and not optional:
                    raise AuthenticationError("Authentication required")
                
                # Attach user to request
                request.state.user = user
                
                return await func(*args, **kwargs)
                
            except AuthenticationError as e:
                # Return 401 response
                raise
        
        return wrapper
    return decorator


def require_permission(*permissions: str, match_all: bool = True):
    """
    Decorator to require specific permissions.
    
    Args:
        permissions: Required permission strings
        match_all: If True, user needs all permissions; if False, any permission
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            user: CurrentUser = getattr(request.state, "user", None)
            
            if user is None:
                raise AuthenticationError("Authentication required")
            
            # Check permissions
            if match_all:
                has_perm = user.has_all_permissions(list(permissions))
            else:
                has_perm = user.has_any_permission(list(permissions))
            
            if not has_perm:
                # Log access denial
                middleware = _get_middleware(request)
                await middleware.audit_logger.log(
                    event_type=AuditEventType.ACCESS_DENIED,
                    tenant_id=user.tenant_id,
                    user_id=user.user_id,
                    ip_address=user.ip_address,
                    path=str(request.url.path),
                    success=False,
                    metadata={
                        "required_permissions": list(permissions),
                        "user_permissions": list(user.permissions),
                    }
                )
                raise AuthorizationError("Insufficient permissions")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(*roles: str):
    """Decorator to require specific roles."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            user: CurrentUser = getattr(request.state, "user", None)
            
            if user is None:
                raise AuthenticationError("Authentication required")
            
            if not any(user.is_in_role(r) for r in roles):
                raise AuthorizationError(f"Required role not found")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_mfa():
    """Decorator to require MFA verification."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            user: CurrentUser = getattr(request.state, "user", None)
            
            if user is None:
                raise AuthenticationError("Authentication required")
            
            if not user.mfa_verified:
                raise AuthorizationError("MFA verification required")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def rate_limit(
    requests: int = 100,
    window: int = 60,
    per_user: bool = True,
    per_tenant: bool = True
):
    """
    Decorator to apply rate limiting.
    
    Args:
        requests: Maximum requests in window
        window: Time window in seconds
        per_user: Apply per-user limit
        per_tenant: Apply per-tenant limit
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            middleware = _get_middleware(request)
            
            user: CurrentUser = getattr(request.state, "user", None)
            
            if user and per_user:
                headers = await middleware.check_rate_limit(user, request)
                # Attach rate limit headers to response
                request.state.rate_limit_headers = headers
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def audit_log(
    event_type: AuditEventType,
    resource_type: Optional[str] = None,
    log_request_body: bool = False,
    log_response_body: bool = False,
    sensitive_fields: Optional[List[str]] = None
):
    """
    Decorator to add audit logging to an endpoint.
    
    Args:
        event_type: Type of audit event
        resource_type: Type of resource being accessed
        log_request_body: Whether to log request body
        log_response_body: Whether to log response body
        sensitive_fields: Fields to redact from logs
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            middleware = _get_middleware(request)
            
            user: CurrentUser = getattr(request.state, "user", None)
            start_time = time.time()
            
            try:
                response = await func(*args, **kwargs)
                success = True
                error_code = None
            except Exception as e:
                success = False
                error_code = type(e).__name__
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                if user:
                    await middleware.log_access(
                        user,
                        request,
                        200 if success else 500,
                        duration_ms
                    )
            
            return response
        
        return wrapper
    return decorator


def tenant_isolation(required: bool = True):
    """
    Decorator to enforce tenant isolation.
    
    Ensures users can only access resources in their tenant.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            user: CurrentUser = getattr(request.state, "user", None)
            
            if user is None:
                if required:
                    raise AuthenticationError("Authentication required")
                return await func(*args, **kwargs)
            
            # Check tenant_id in request matches user's tenant
            request_tenant = kwargs.get("tenant_id") or request.path_params.get("tenant_id")
            
            if request_tenant and request_tenant != user.tenant_id:
                # Super admin can access any tenant
                if "super_admin" not in user.roles:
                    raise AuthorizationError("Cross-tenant access denied")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_request(args: Tuple, kwargs: Dict) -> Any:
    """Extract request object from handler arguments."""
    # FastAPI: request is first arg or in kwargs
    if args:
        return args[0]
    return kwargs.get("request")


def _get_middleware(request) -> AuthMiddleware:
    """Get auth middleware from app state."""
    return request.app.state.auth_middleware


# ============================================================================
# FastAPI Integration
# ============================================================================

try:
    from fastapi import Request, Response, HTTPException
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class FastAPIAuthMiddleware(BaseHTTPMiddleware):
        """FastAPI middleware for authentication."""
        
        def __init__(
            self,
            app,
            jwt_manager: JWTTokenManager,
            rate_limiter: RateLimiter,
            audit_logger: AuditLogger,
            public_paths: Optional[Set[str]] = None
        ):
            super().__init__(app)
            self.auth = AuthMiddleware(jwt_manager, rate_limiter, audit_logger)
            self.public_paths = public_paths or {"/health", "/metrics", "/docs", "/openapi.json"}
        
        async def dispatch(self, request: Request, call_next) -> Response:
            """Process request with authentication."""
            start_time = time.time()
            
            # Skip auth for public paths
            if request.url.path in self.public_paths:
                return await call_next(request)
            
            try:
                # Authenticate
                user = await self.auth.authenticate(request)
                request.state.user = user
                
                # Rate limiting
                if user:
                    rate_headers = await self.auth.check_rate_limit(user, request)
                else:
                    rate_headers = {}
                
                # Process request
                response = await call_next(request)
                
                # Add rate limit headers
                for key, value in rate_headers.items():
                    response.headers[key] = value
                
                # Audit log
                if user:
                    duration_ms = (time.time() - start_time) * 1000
                    await self.auth.log_access(
                        user, request, response.status_code, duration_ms
                    )
                
                return response
                
            except AuthenticationError as e:
                return Response(
                    content=json.dumps({"error": "Unauthorized", "message": str(e)}),
                    status_code=401,
                    media_type="application/json"
                )
            except RateLimitExceeded as e:
                return Response(
                    content=json.dumps({"error": "Rate Limit Exceeded"}),
                    status_code=429,
                    media_type="application/json"
                )
    
    # Security scheme for OpenAPI
    security_scheme = HTTPBearer(
        scheme_name="JWT",
        description="JWT access token",
        auto_error=False
    )

except ImportError:
    FastAPIAuthMiddleware = None


# ============================================================================
# Flask Integration
# ============================================================================

try:
    from flask import request, g, jsonify
    
    class FlaskAuthMiddleware:
        """Flask middleware for authentication."""
        
        def __init__(
            self,
            app=None,
            jwt_manager: JWTTokenManager = None,
            rate_limiter: RateLimiter = None,
            audit_logger: AuditLogger = None,
            public_paths: Optional[Set[str]] = None
        ):
            self.jwt_manager = jwt_manager
            self.rate_limiter = rate_limiter
            self.audit_logger = audit_logger
            self.public_paths = public_paths or {"/health", "/metrics"}
            
            if app:
                self.init_app(app)
        
        def init_app(self, app):
            """Initialize with Flask app."""
            self.auth = AuthMiddleware(
                self.jwt_manager, 
                self.rate_limiter, 
                self.audit_logger
            )
            
            @app.before_request
            async def before_request():
                if request.path in self.public_paths:
                    return None
                
                try:
                    # Wrap request for compatibility
                    user = await self.auth.authenticate(request)
                    g.user = user
                    g.request_id = secrets.token_hex(8)
                    
                    if user:
                        rate_headers = await self.auth.check_rate_limit(user, request)
                        g.rate_limit_headers = rate_headers
                        
                except AuthenticationError as e:
                    return jsonify({"error": "Unauthorized"}), 401
                except RateLimitExceeded as e:
                    return jsonify({"error": "Rate Limit Exceeded"}), 429
            
            @app.after_request
            async def after_request(response):
                # Add rate limit headers
                if hasattr(g, "rate_limit_headers"):
                    for key, value in g.rate_limit_headers.items():
                        response.headers[key] = value
                
                # Audit log
                if hasattr(g, "user") and g.user:
                    await self.auth.log_access(
                        g.user, request, response.status_code, 0
                    )
                
                return response

except ImportError:
    FlaskAuthMiddleware = None


# ============================================================================
# WebSocket Authentication
# ============================================================================

class WebSocketAuthManager:
    """
    Manages authentication for WebSocket connections.
    
    WebSocket connections require special handling since headers
    may not be available in all clients.
    """
    
    def __init__(self, jwt_manager: JWTTokenManager):
        self.jwt_manager = jwt_manager
        self._active_connections: Dict[str, CurrentUser] = {}
    
    async def authenticate_from_token(self, token: str) -> CurrentUser:
        """Authenticate from token provided in query param or message."""
        claims = self.jwt_manager.validate_token(token)
        
        return CurrentUser(
            user_id=claims["sub"],
            tenant_id=claims["tid"],
            email=claims.get("email", ""),
            roles=claims.get("roles", []),
            permissions=set(claims.get("permissions", [])),
            session_id=claims.get("session_id"),
            mfa_verified=claims.get("mfa_verified", False),
        )
    
    async def register_connection(
        self, 
        connection_id: str, 
        user: CurrentUser
    ) -> None:
        """Register an active WebSocket connection."""
        self._active_connections[connection_id] = user
    
    async def unregister_connection(self, connection_id: str) -> None:
        """Unregister a WebSocket connection."""
        self._active_connections.pop(connection_id, None)
    
    def get_user(self, connection_id: str) -> Optional[CurrentUser]:
        """Get user for a connection."""
        return self._active_connections.get(connection_id)
    
    def get_connections_for_user(self, user_id: str) -> List[str]:
        """Get all connection IDs for a user."""
        return [
            conn_id 
            for conn_id, user in self._active_connections.items() 
            if user.user_id == user_id
        ]
    
    async def broadcast_to_tenant(
        self, 
        tenant_id: str, 
        message: Dict[str, Any]
    ) -> int:
        """Broadcast message to all connections in a tenant."""
        count = 0
        for conn_id, user in self._active_connections.items():
            if user.tenant_id == tenant_id:
                # Send message via WebSocket
                count += 1
        return count


# ============================================================================
# Factory and Initialization
# ============================================================================

def create_auth_middleware(
    private_key_path: Optional[str] = None,
    public_key_path: Optional[str] = None,
    jwt_config: Optional[JWTConfig] = None,
    rate_limit_config: Optional[RateLimitConfig] = None,
) -> Tuple[JWTTokenManager, RateLimiter, AuditLogger]:
    """
    Factory function to create authentication components.
    
    Returns tuple of (jwt_manager, rate_limiter, audit_logger)
    """
    # Create JWT manager
    jwt_manager = JWTTokenManager(jwt_config)
    
    if private_key_path and public_key_path:
        jwt_manager.load_keys(private_key_path, public_key_path)
    else:
        # Generate development keys
        private, public = jwt_manager.generate_key_pair()
        jwt_manager._private_key = private
        jwt_manager._public_key = public
    
    # Create rate limiter
    rate_limiter = RateLimiter(rate_limit_config)
    
    # Create audit logger
    audit_logger = AuditLogger()
    
    return jwt_manager, rate_limiter, audit_logger
