"""Routes for notifications — channels, templates, delivery, digests, reports."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.notification import (
    DigestConfig,
    NotificationChannel,
    NotificationDelivery,
    NotificationTemplate,
    ScheduledReport,
)
from app.schemas.notification import (
    DigestConfigCreate,
    DigestConfigResponse,
    DigestConfigUpdate,
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationDeliveryResponse,
    NotificationTemplateCreate,
    NotificationTemplateResponse,
    NotificationTemplateUpdate,
    ScheduledReportCreate,
    ScheduledReportResponse,
    ScheduledReportUpdate,
    SendNotificationRequest,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Channels CRUD
# ---------------------------------------------------------------------------


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_channels(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(NotificationChannel)
        .where(NotificationChannel.user_id == auth.user_id)
        .order_by(NotificationChannel.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_channel(
    body: NotificationChannelCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    channel = NotificationChannel(
        user_id=auth.user_id,
        channel_type=body.channel_type,
        config_json=body.config_json,
        is_active=body.is_active,
    )
    session.add(channel)
    await session.flush()
    return channel


@router.patch("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: str,
    body: NotificationChannelUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(NotificationChannel)
        .where(NotificationChannel.id == channel_id, NotificationChannel.user_id == auth.user_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if body.config_json is not None:
        channel.config_json = body.config_json
    if body.is_active is not None:
        channel.is_active = body.is_active

    await session.flush()
    await session.refresh(channel)
    return channel


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(NotificationChannel)
        .where(NotificationChannel.id == channel_id, NotificationChannel.user_id == auth.user_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await session.delete(channel)


# ---------------------------------------------------------------------------
# Send notification
# ---------------------------------------------------------------------------


@router.post("/send", response_model=NotificationDeliveryResponse, status_code=201)
async def send_notification(
    body: SendNotificationRequest,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Verify channel belongs to user
    result = await session.execute(
        select(NotificationChannel)
        .where(NotificationChannel.id == body.channel_id, NotificationChannel.user_id == auth.user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        if body.template_id and body.template_vars:
            delivery = await NotificationService.send_with_template(
                session, body.channel_id, body.template_id, body.template_vars,
            )
        else:
            delivery = await NotificationService.send(
                session, body.channel_id, body.subject, body.body,
            )
        return delivery
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------


@router.get("/deliveries", response_model=list[NotificationDeliveryResponse])
async def list_deliveries(
    status: str | None = Query(None),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(NotificationDelivery)
        .join(NotificationChannel, NotificationDelivery.channel_id == NotificationChannel.id)
        .where(NotificationChannel.user_id == auth.user_id)
        .order_by(NotificationDelivery.created_at.desc())
    )
    if status:
        query = query.where(NotificationDelivery.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Templates CRUD
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[NotificationTemplateResponse])
async def list_templates(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(NotificationTemplate).order_by(NotificationTemplate.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/templates", response_model=NotificationTemplateResponse, status_code=201)
async def create_template(
    body: NotificationTemplateCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    template = NotificationTemplate(
        name=body.name,
        subject=body.subject,
        body_template=body.body_template,
        channel_type=body.channel_type,
    )
    session.add(template)
    await session.flush()
    return template


@router.patch("/templates/{template_id}", response_model=NotificationTemplateResponse)
async def update_template(
    template_id: str,
    body: NotificationTemplateUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if body.name is not None:
        template.name = body.name
    if body.subject is not None:
        template.subject = body.subject
    if body.body_template is not None:
        template.body_template = body.body_template
    if body.channel_type is not None:
        template.channel_type = body.channel_type

    await session.flush()
    await session.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    await session.delete(template)


# ---------------------------------------------------------------------------
# Digest Configs CRUD
# ---------------------------------------------------------------------------


@router.get("/digests", response_model=list[DigestConfigResponse])
async def list_digests(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(DigestConfig)
        .where(DigestConfig.user_id == auth.user_id)
        .order_by(DigestConfig.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/digests", response_model=DigestConfigResponse, status_code=201)
async def create_digest(
    body: DigestConfigCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    digest = DigestConfig(
        user_id=auth.user_id,
        frequency=body.frequency,
        include_portfolio=body.include_portfolio,
        include_alerts=body.include_alerts,
        include_market_summary=body.include_market_summary,
        is_active=body.is_active,
    )
    session.add(digest)
    await session.flush()
    return digest


@router.patch("/digests/{digest_id}", response_model=DigestConfigResponse)
async def update_digest(
    digest_id: str,
    body: DigestConfigUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(DigestConfig)
        .where(DigestConfig.id == digest_id, DigestConfig.user_id == auth.user_id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest config not found")

    if body.frequency is not None:
        digest.frequency = body.frequency
    if body.include_portfolio is not None:
        digest.include_portfolio = body.include_portfolio
    if body.include_alerts is not None:
        digest.include_alerts = body.include_alerts
    if body.include_market_summary is not None:
        digest.include_market_summary = body.include_market_summary
    if body.is_active is not None:
        digest.is_active = body.is_active

    await session.flush()
    await session.refresh(digest)
    return digest


@router.delete("/digests/{digest_id}", status_code=204)
async def delete_digest(
    digest_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(DigestConfig)
        .where(DigestConfig.id == digest_id, DigestConfig.user_id == auth.user_id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest config not found")
    await session.delete(digest)


# ---------------------------------------------------------------------------
# Scheduled Reports CRUD
# ---------------------------------------------------------------------------


@router.get("/reports", response_model=list[ScheduledReportResponse])
async def list_reports(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(ScheduledReport)
        .where(ScheduledReport.user_id == auth.user_id)
        .order_by(ScheduledReport.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/reports", response_model=ScheduledReportResponse, status_code=201)
async def create_report(
    body: ScheduledReportCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    report = ScheduledReport(
        user_id=auth.user_id,
        report_type=body.report_type,
        schedule_cron=body.schedule_cron,
        format=body.format,
        is_active=body.is_active,
    )
    session.add(report)
    await session.flush()
    return report


@router.patch("/reports/{report_id}", response_model=ScheduledReportResponse)
async def update_report(
    report_id: str,
    body: ScheduledReportUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(ScheduledReport)
        .where(ScheduledReport.id == report_id, ScheduledReport.user_id == auth.user_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")

    if body.report_type is not None:
        report.report_type = body.report_type
    if body.schedule_cron is not None:
        report.schedule_cron = body.schedule_cron
    if body.format is not None:
        report.format = body.format
    if body.is_active is not None:
        report.is_active = body.is_active

    await session.flush()
    await session.refresh(report)
    return report


@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(
    report_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(ScheduledReport)
        .where(ScheduledReport.id == report_id, ScheduledReport.user_id == auth.user_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    await session.delete(report)
