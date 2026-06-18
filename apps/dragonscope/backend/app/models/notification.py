"""Notification models — channels, templates, deliveries, digests, reports."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_type: Mapped[str] = mapped_column(String(20))  # email, telegram, discord, webhook, sms
    config_json: Mapped[str] = mapped_column(Text)  # JSON with channel-specific config
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True)
    subject: Mapped[str] = mapped_column(String(500))
    body_template: Mapped[str] = mapped_column(Text)  # supports {{variable}} substitution
    channel_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("notification_channels.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("notification_templates.id", ondelete="SET NULL"), nullable=True)
    subject: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, sent, failed, bounced
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DigestConfig(Base):
    __tablename__ = "digest_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    frequency: Mapped[str] = mapped_column(String(20))  # daily, weekly, monthly
    include_portfolio: Mapped[bool] = mapped_column(Boolean, default=True)
    include_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    include_market_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    report_type: Mapped[str] = mapped_column(String(50))  # portfolio, market, research
    schedule_cron: Mapped[str] = mapped_column(String(100))
    format: Mapped[str] = mapped_column(String(10), default="json")  # json, csv, pdf
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sent: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
