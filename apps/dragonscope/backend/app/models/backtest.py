"""Backtesting framework models — strategies, runs, trades."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dsl_config: Mapped[str] = mapped_column(Text)  # JSON strategy DSL
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    backtest_runs: Mapped[list["BacktestRun"]] = relationship(
        back_populates="strategy", cascade="all, delete-orphan"
    )


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    strategy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/completed/failed
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    initial_capital: Mapped[float] = mapped_column(Numeric(16, 4))
    final_capital: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    total_return: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    strategy: Mapped["Strategy"] = relationship(back_populates="backtest_runs")
    trades: Mapped[list["BacktestTrade"]] = relationship(
        back_populates="backtest_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_backtest_run_user_status", "user_id", "status"),
    )


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    backtest_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("backtest_runs.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(4))  # "buy" or "sell"
    quantity: Mapped[float] = mapped_column(Numeric(16, 8))
    price: Mapped[float] = mapped_column(Numeric(14, 4))
    commission: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    slippage: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pnl: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)

    backtest_run: Mapped["BacktestRun"] = relationship(back_populates="trades")
