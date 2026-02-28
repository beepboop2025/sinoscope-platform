import logging
from dataclasses import dataclass

import jwt
import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserPreference

logger = logging.getLogger(__name__)
settings = get_settings()

_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    """Fetch and cache Clerk's JWKS keys."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            settings.CLERK_JWKS_URL,
            headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
        )
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


async def _resolve_user(session: AsyncSession, clerk_id: str, email: str) -> User:
    """Find or create user by clerk_id."""
    result = await session.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(clerk_id=clerk_id, email=email)
        session.add(user)
        await session.flush()
        prefs = UserPreference(user_id=user.id)
        session.add(prefs)
        await session.flush()

    return user


@dataclass
class AuthUser:
    user_id: str
    clerk_id: str
    email: str


async def require_auth(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> AuthUser:
    """Verify Clerk JWT and resolve user. Dev mode if no CLERK_SECRET_KEY."""
    # Dev mode
    if not settings.CLERK_SECRET_KEY:
        user = await _resolve_user(session, "dev-user", "dev@localhost")
        return AuthUser(user_id=user.id, clerk_id="dev-user", email="dev@localhost")

    # Production: verify JWT
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth_header[7:]
    try:
        jwks = await _get_jwks()
        # Get the signing key
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        signing_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break

        if signing_key is None:
            # Invalidate cache and retry once
            global _jwks_cache
            _jwks_cache = None
            jwks = await _get_jwks()
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                    break

        if signing_key is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        payload = jwt.decode(token, signing_key, algorithms=["RS256"])
        clerk_id = payload.get("sub")
        email = payload.get("email") or ""

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user = await _resolve_user(session, clerk_id, email or f"{clerk_id}@local")
        return AuthUser(user_id=user.id, clerk_id=clerk_id, email=email)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def optional_auth(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> AuthUser | None:
    """Optional auth — returns None if no valid token."""
    if not settings.CLERK_SECRET_KEY:
        user = await _resolve_user(session, "dev-user", "dev@localhost")
        return AuthUser(user_id=user.id, clerk_id="dev-user", email="dev@localhost")

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    try:
        return await require_auth(request, session)
    except HTTPException:
        return None
