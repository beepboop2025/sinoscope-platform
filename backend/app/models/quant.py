"""Quantitative analytics models — yield curves, options, VaR, covariance."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class YieldCurve(Base):
    __tablename__ = "yield_curves"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date: Mapped[date] = mapped_column(Date, index=True)
    tenor: Mapped[str] = mapped_column(String(10))  # "1M","3M","6M","1Y","2Y","5Y","10Y","30Y"
    rate: Mapped[float] = mapped_column(Numeric(10, 6))
    source: Mapped[str] = mapped_column(String(50), default="FRED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_yield_curve_date_tenor", "date", "tenor", unique=True),
    )


class OptionChain(Base):
    __tablename__ = "option_chains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    expiry: Mapped[date] = mapped_column(Date, index=True)
    strike: Mapped[float] = mapped_column(Numeric(14, 4))
    option_type: Mapped[str] = mapped_column(String(4))  # "call" or "put"
    bid: Mapped[float] = mapped_column(Numeric(14, 4))
    ask: Mapped[float] = mapped_column(Numeric(14, 4))
    volume: Mapped[int] = mapped_column(Integer, default=0)
    open_interest: Mapped[int] = mapped_column(Integer, default=0)
    implied_vol: Mapped[float] = mapped_column(Numeric(10, 6))
    delta: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    gamma: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    theta: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    vega: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_option_chain_symbol_expiry", "symbol", "expiry"),
    )


class VarResult(Base):
    __tablename__ = "var_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    method: Mapped[str] = mapped_column(String(20))  # "historical", "parametric", "monte_carlo"
    confidence: Mapped[float] = mapped_column(Numeric(5, 4))
    horizon_days: Mapped[int] = mapped_column(Integer, default=1)
    var_value: Mapped[float] = mapped_column(Numeric(16, 4))
    cvar_value: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CovarianceMatrix(Base):
    __tablename__ = "covariance_matrices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbols: Mapped[str] = mapped_column(Text)  # comma-separated symbol list
    window_days: Mapped[int] = mapped_column(Integer, default=252)
    matrix_data: Mapped[str] = mapped_column(Text)  # JSON-encoded 2D array
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
