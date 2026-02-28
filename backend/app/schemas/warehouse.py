"""Pydantic v2 schemas for data warehouse."""

from datetime import date, datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Dimension tables
# ---------------------------------------------------------------------------
class DimAssetResponse(BaseModel):
    id: str
    symbol: str
    name: str
    asset_type: str
    sector: str | None = None
    exchange: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DimTimeResponse(BaseModel):
    id: str
    date: date
    year: int
    quarter: int
    month: int
    day_of_week: int
    is_trading_day: bool

    model_config = {"from_attributes": True}


class DimSourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    reliability_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Fact table
# ---------------------------------------------------------------------------
class FactPriceResponse(BaseModel):
    id: str
    asset_id: str
    time_id: str
    source_id: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------
class DataLineageResponse(BaseModel):
    id: str
    table_name: str
    record_id: str
    source_table: str | None = None
    transformation: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ETL Health
# ---------------------------------------------------------------------------
class EtlHealthResponse(BaseModel):
    id: str
    pipeline_name: str
    status: str
    last_run: datetime
    records_processed: int
    error_count: int
    checked_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Data Quality Score
# ---------------------------------------------------------------------------
class DataQualityScoreResponse(BaseModel):
    id: str
    table_name: str
    freshness_score: float
    completeness_score: float
    validity_score: float
    overall_score: float
    checked_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
class EtlHealthSummary(BaseModel):
    healthy: int = 0
    degraded: int = 0
    failed: int = 0


class QualitySummary(BaseModel):
    average_score: float = 0.0
    tables_checked: int = 0


class WarehouseOverview(BaseModel):
    total_assets: int
    total_fact_records: int
    etl_health_summary: EtlHealthSummary
    quality_summary: QualitySummary
