from datetime import datetime

from sqlalchemy import DateTime, Double, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketTick(Base):
    """Individual price ticks — converted to a TimescaleDB hypertable via migration."""

    __tablename__ = "market_ticks"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[float | None] = mapped_column(Double, nullable=True)
    open: Mapped[float | None] = mapped_column(Double, nullable=True)
    high: Mapped[float | None] = mapped_column(Double, nullable=True)
    low: Mapped[float | None] = mapped_column(Double, nullable=True)
    volume: Mapped[float | None] = mapped_column(Double, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Double, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Double, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_market_ticks_category_symbol_time", "category", "symbol", "time"),
    )


class SnapshotLog(Base):
    """Full JSON snapshots for categories without per-symbol ticks."""

    __tablename__ = "snapshot_logs"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_snapshot_logs_category_time", "category", "time"),
    )
