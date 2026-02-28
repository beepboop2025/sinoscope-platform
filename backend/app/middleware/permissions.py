import logging
from typing import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.role import ROLE_PERMISSIONS

logger = logging.getLogger(__name__)

# Default role assigned when a user has no explicit role.
_DEFAULT_ROLE = "user"


def _user_role(request: Request) -> str:
    """Return the role string stored on the request/user, falling back to default."""
    role: str | None = getattr(request.state, "user_role", None)
    return role if role and role in ROLE_PERMISSIONS else _DEFAULT_ROLE


def _has_permission(role: str, permission: str) -> bool:
    """Check if a role includes the given permission."""
    perms = ROLE_PERMISSIONS.get(role, [])
    return permission in perms


# ---------------------------------------------------------------------------
# Public dependency factories
# ---------------------------------------------------------------------------


def require_permission(permission: str) -> Callable:
    """Return a FastAPI dependency that enforces a single permission.

    Usage::

        @router.get("/quant/signals")
        async def signals(user: AuthUser = Depends(require_permission("read:quant"))):
            ...
    """

    async def _dependency(
        request: Request,
        auth_user: AuthUser = Depends(require_auth),
        session: AsyncSession = Depends(get_db),
    ) -> AuthUser:
        role = _user_role(request)
        if not _has_permission(role, permission):
            logger.warning(
                "Permission denied: user=%s role=%s required=%s",
                auth_user.user_id,
                role,
                permission,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied. Required: {permission}",
            )
        return auth_user

    return _dependency


def require_any_permission(*permissions: str) -> Callable:
    """Return a FastAPI dependency that passes if the user has ANY of the
    listed permissions.

    Usage::

        @router.get("/reports")
        async def reports(
            user: AuthUser = Depends(require_any_permission("read:quant", "read:compliance")),
        ):
            ...
    """

    async def _dependency(
        request: Request,
        auth_user: AuthUser = Depends(require_auth),
        session: AsyncSession = Depends(get_db),
    ) -> AuthUser:
        role = _user_role(request)
        for perm in permissions:
            if _has_permission(role, perm):
                return auth_user

        logger.warning(
            "Permission denied: user=%s role=%s required_any=%s",
            auth_user.user_id,
            role,
            permissions,
        )
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied. Required one of: {', '.join(permissions)}",
        )

    return _dependency


async def require_admin(
    request: Request,
    auth_user: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> AuthUser:
    """Convenience dependency that requires the ``admin:system`` permission.

    Usage::

        @router.delete("/admin/users/{user_id}")
        async def delete_user(user: AuthUser = Depends(require_admin)):
            ...
    """
    role = _user_role(request)
    if not _has_permission(role, "admin:system"):
        logger.warning(
            "Admin access denied: user=%s role=%s",
            auth_user.user_id,
            role,
        )
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )
    return auth_user
