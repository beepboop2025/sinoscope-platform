import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.user import User, UserPreference
from app.schemas.user import PreferencesResponse, PreferencesUpdate, UserResponse, UserSync

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/users/me", response_model=UserResponse)
async def get_me(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(User)
        .where(User.clerk_id == auth.clerk_id)
        .options(selectinload(User.preferences))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users/sync", response_model=UserResponse)
async def sync_user(
    body: UserSync,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(User)
        .where(User.clerk_id == auth.clerk_id)
        .options(selectinload(User.preferences))
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            clerk_id=auth.clerk_id,
            email=body.email or auth.email,
            display_name=body.display_name,
            avatar_url=body.avatar_url,
        )
        session.add(user)
        await session.flush()
        prefs = UserPreference(user_id=user.id)
        session.add(prefs)
        await session.flush()
        await session.refresh(user, ["preferences"])
    else:
        if body.email:
            user.email = body.email
        if body.display_name:
            user.display_name = body.display_name
        if body.avatar_url:
            user.avatar_url = body.avatar_url
        await session.flush()
        await session.refresh(user, ["preferences"])

    return user


@router.patch("/users/preferences", response_model=PreferencesResponse)
async def update_preferences(
    body: PreferencesUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(User).where(User.clerk_id == auth.clerk_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get or create preferences
    result = await session.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        prefs = UserPreference(user_id=user.id)
        session.add(prefs)
        await session.flush()

    if body.default_workspace is not None:
        prefs.default_workspace = body.default_workspace
    if body.theme is not None:
        prefs.theme = body.theme
    if body.refresh_interval is not None:
        prefs.refresh_interval = body.refresh_interval
    if body.notifications is not None:
        prefs.notifications = body.notifications

    await session.flush()
    await session.refresh(prefs)
    return prefs
