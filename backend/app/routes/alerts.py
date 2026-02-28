import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertResponse, AlertUpdate
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Alert)
        .where(Alert.user_id == auth.user_id)
        .order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/alerts", response_model=AlertResponse, status_code=201)
async def create_alert(
    body: AlertCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    alert = Alert(
        user_id=auth.user_id,
        symbol=body.symbol.upper(),
        condition=body.condition,
        threshold=body.threshold,
    )
    session.add(alert)
    await session.flush()
    await write_audit_log(session, auth.user_id, "create", "alert", {"id": alert.id})
    return alert


@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    body: AlertUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == auth.user_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Resource not found")

    if body.is_active is not None:
        alert.is_active = body.is_active
    if body.condition is not None:
        alert.condition = body.condition
    if body.threshold is not None:
        alert.threshold = body.threshold

    await session.flush()
    await session.refresh(alert)
    return alert


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == auth.user_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Resource not found")

    await session.delete(alert)
    await write_audit_log(session, auth.user_id, "delete", "alert", {"id": alert_id})
