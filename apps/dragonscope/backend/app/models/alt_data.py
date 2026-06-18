"""Alternative data models — insider trades, short interest, trends, patents, etc."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InsiderTrade(Base):
    """SEC insider trading filings."""

    __tablename__ = "insider_trades"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    filer_name: Mapped[str] = mapped_column(String(255))
    transaction_type: Mapped[str] = mapped_column(String(10))  # "buy", "sell", "grant"
    shares: Mapped[float] = mapped_column(Numeric(16, 4))
    price: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    filing_date: Mapped[date] = mapped_column(Date, index=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_insider_trades_symbol_date", "symbol", "filing_date"),
    )


class ShortInterest(Base):
    """FINRA short interest reports."""

    __tablename__ = "short_interest"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    short_interest: Mapped[float] = mapped_column(Numeric(16, 4))
    short_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    days_to_cover: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_short_interest_symbol_date", "symbol", "report_date"),
    )


class GoogleTrend(Base):
    """Google Trends interest scores for keywords."""

    __tablename__ = "google_trends"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    keyword: Mapped[str] = mapped_column(String(255), index=True)
    interest_score: Mapped[int] = mapped_column(Integer)
    date: Mapped[date] = mapped_column(Date, index=True)
    region: Mapped[str] = mapped_column(String(10), default="US")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_google_trends_keyword_date", "keyword", "date"),
    )


class GovernmentContract(Base):
    """Federal government contract awards."""

    __tablename__ = "government_contracts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    agency: Mapped[str] = mapped_column(String(255))
    vendor: Mapped[str] = mapped_column(String(255), index=True)
    amount: Mapped[float] = mapped_column(Numeric(16, 4))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    award_date: Mapped[date] = mapped_column(Date, index=True)
    naics_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_gov_contracts_vendor_date", "vendor", "award_date"),
    )


class PatentFiling(Base):
    """USPTO patent filings."""

    __tablename__ = "patent_filings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    assignee: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(512))
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    filing_date: Mapped[date] = mapped_column(Date, index=True)
    patent_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_patent_filings_assignee_date", "assignee", "filing_date"),
    )


class JobPosting(Base):
    """Job postings from various sources."""

    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(512))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_job_postings_company", "company"),
    )


class WeatherImpact(Base):
    """Weather events with potential market impact."""

    __tablename__ = "weather_impacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    region: Mapped[str] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(50))  # "hurricane", "drought", "flood", etc.
    severity: Mapped[str] = mapped_column(String(20))  # "low", "moderate", "high", "extreme"
    affected_sectors_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_weather_impacts_region_date", "region", "start_date"),
    )
