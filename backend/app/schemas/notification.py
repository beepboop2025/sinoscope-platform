"""Pydantic v2 schemas for notifications."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# NotificationChannel
# ---------------------------------------------------------------------------
class NotificationChannelCreate(BaseModel):
    channel_type: str = Field(pattern=r"^(email|telegram|discord|webhook|sms)$")
    config_json: str  # JSON with channel-specific config
    is_active: bool = True


class NotificationChannelUpdate(BaseModel):
    config_json: str | None = None
    is_active: bool | None = None


class NotificationChannelResponse(BaseModel):
    id: str
    user_id: str
    channel_type: str
    config_json: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# NotificationTemplate
# ---------------------------------------------------------------------------
class NotificationTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=500)
    body_template: str  # supports {{variable}} substitution
    channel_type: str = Field(pattern=r"^(email|telegram|discord|webhook|sms)$")


class NotificationTemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_template: str | None = None
    channel_type: str | None = None


class NotificationTemplateResponse(BaseModel):
    id: str
    name: str
    subject: str
    body_template: str
    channel_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# NotificationDelivery
# ---------------------------------------------------------------------------
class NotificationDeliveryResponse(BaseModel):
    id: str
    channel_id: str
    template_id: str | None = None
    subject: str
    body: str
    status: str
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Send request
# ---------------------------------------------------------------------------
class SendNotificationRequest(BaseModel):
    channel_id: str
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    template_id: str | None = None
    template_vars: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# DigestConfig
# ---------------------------------------------------------------------------
class DigestConfigCreate(BaseModel):
    frequency: str = Field(pattern=r"^(daily|weekly|monthly)$")
    include_portfolio: bool = True
    include_alerts: bool = True
    include_market_summary: bool = True
    is_active: bool = True


class DigestConfigUpdate(BaseModel):
    frequency: str | None = None
    include_portfolio: bool | None = None
    include_alerts: bool | None = None
    include_market_summary: bool | None = None
    is_active: bool | None = None


class DigestConfigResponse(BaseModel):
    id: str
    user_id: str
    frequency: str
    include_portfolio: bool
    include_alerts: bool
    include_market_summary: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ScheduledReport
# ---------------------------------------------------------------------------
class ScheduledReportCreate(BaseModel):
    report_type: str = Field(pattern=r"^(portfolio|market|research)$")
    schedule_cron: str = Field(min_length=1, max_length=100)
    format: str = Field(default="json", pattern=r"^(json|csv|pdf)$")
    is_active: bool = True


class ScheduledReportUpdate(BaseModel):
    report_type: str | None = None
    schedule_cron: str | None = None
    format: str | None = None
    is_active: bool | None = None


class ScheduledReportResponse(BaseModel):
    id: str
    user_id: str
    report_type: str
    schedule_cron: str
    format: str
    is_active: bool
    last_sent: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
