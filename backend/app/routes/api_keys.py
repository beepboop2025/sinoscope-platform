import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse
from app.services.audit import write_audit_log
from app.utils.crypto import hash_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(ApiKey).where(ApiKey.user_id == auth.user_id)
    )
    return list(result.scalars().all())


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
async def save_api_key(
    body: ApiKeyCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Upsert: check if exists for this user+provider
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == auth.user_id,
            ApiKey.provider == body.provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.key_hash = hash_api_key(body.key)
        existing.label = body.label or body.provider
        await session.flush()
        await session.refresh(existing)
        return existing
    else:
        api_key = ApiKey(
            user_id=auth.user_id,
            provider=body.provider,
            key_hash=hash_api_key(body.key),
            label=body.label or body.provider,
        )
        session.add(api_key)
        await session.flush()
        await write_audit_log(session, auth.user_id, "create", "api_key", {"provider": body.provider})
        return api_key


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == auth.user_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="Resource not found")

    await session.delete(api_key)
    await write_audit_log(session, auth.user_id, "delete", "api_key", {"id": key_id})
