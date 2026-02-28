"""Data warehouse models — star schema dimensions, facts, lineage, quality."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DimAsset(Base):
    __tablename__ = "dim_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(50))  # stock, crypto, forex, bond, commodity
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DimTime(Base):
    __tablename__ = "dim_time"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Monday, 6=Sunday
    is_trading_day: Mapped[bool] = mapped_column(Boolean, default=True)


class DimSource(Base):
    __tablename__ = "dim_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50))  # api, scraper, manual, derived
    reliability_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FactPrice(Base):
    __tablename__ = "fact_prices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("dim_assets.id", ondelete="CASCADE"), index=True)
    time_id: Mapped[str] = mapped_column(String(36), ForeignKey("dim_time.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("dim_sources.id", ondelete="CASCADE"), index=True)
    open: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    high: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    close: Mapped[float] = mapped_column(Numeric(14, 4))
    volume: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_fact_price_asset_time", "asset_id", "time_id"),
    )


class DataLineage(Base):
    __tablename__ = "data_lineage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_name: Mapped[str] = mapped_column(String(100), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    source_table: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transformation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EtlHealth(Base):
    __tablename__ = "etl_health"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_name: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20))  # healthy, degraded, failed
    last_run: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataQualityScore(Base):
    __tablename__ = "data_quality_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_name: Mapped[str] = mapped_column(String(100), index=True)
    freshness_score: Mapped[float] = mapped_column(Numeric(5, 4))
    completeness_score: Mapped[float] = mapped_column(Numeric(5, 4))
    validity_score: Mapped[float] = mapped_column(Numeric(5, 4))
    overall_score: Mapped[float] = mapped_column(Numeric(5, 4))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
