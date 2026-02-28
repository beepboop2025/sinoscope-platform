"""Pydantic schemas for alternative data endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ── Insider Trades ────────────────────────────────────────────────────────────

class InsiderTradeResponse(BaseModel):
    id: str
    symbol: str
    filer_name: str
    transaction_type: str
    shares: float
    price: float | None = None
    value: float | None = None
    filing_date: date
    source_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Short Interest ────────────────────────────────────────────────────────────

class ShortInterestResponse(BaseModel):
    id: str
    symbol: str
    short_interest: float
    short_ratio: float | None = None
    days_to_cover: float | None = None
    report_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Google Trends ─────────────────────────────────────────────────────────────

class GoogleTrendResponse(BaseModel):
    id: str
    keyword: str
    interest_score: int
    date: date
    region: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Government Contracts ──────────────────────────────────────────────────────

class GovernmentContractResponse(BaseModel):
    id: str
    agency: str
    vendor: str
    amount: float
    description: str | None = None
    award_date: date
    naics_code: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Patent Filings ────────────────────────────────────────────────────────────

class PatentFilingResponse(BaseModel):
    id: str
    assignee: str
    title: str
    abstract: str | None = None
    filing_date: date
    patent_number: str | None = None
    classification: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Job Postings ──────────────────────────────────────────────────────────────

class JobPostingResponse(BaseModel):
    id: str
    company: str
    title: str
    location: str | None = None
    seniority: str | None = None
    department: str | None = None
    posted_date: date | None = None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Weather Impact ────────────────────────────────────────────────────────────

class WeatherImpactResponse(BaseModel):
    id: str
    region: str
    event_type: str
    severity: str
    affected_sectors_json: str | None = None
    start_date: date
    end_date: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Aggregated Summary ────────────────────────────────────────────────────────

class AltDataSummary(BaseModel):
    symbol: str
    insider_trades_count: int = 0
    short_interest_latest: float | None = None
    trend_score: int | None = None
    recent_contracts: int = 0
