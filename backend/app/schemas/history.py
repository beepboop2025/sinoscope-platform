from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TickResponse(BaseModel):
    time: datetime
    symbol: str
    category: str
    price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    market_cap: float | None = None
    change_pct: float | None = None
    extra: dict[str, Any] | None = None


class CandleResponse(BaseModel):
    bucket: datetime
    symbol: str
    category: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    market_cap: float | None = None
    tick_count: int = 0


class SnapshotResponse(BaseModel):
    time: datetime
    category: str
    snapshot: dict[str, Any]
    record_count: int | None = None


class SymbolInfo(BaseModel):
    symbol: str
    category: str
    latest_price: float | None = None
    latest_time: datetime | None = None
    data_points: int = 0


class TimeSeriesResponse(BaseModel):
    data: list[TickResponse] | list[CandleResponse]
    count: int
    symbol: str | None = None
    interval: str | None = None


class StatsResponse(BaseModel):
    timescaledb_version: str | None = None
    hypertables: list[dict[str, Any]] = []
    total_chunks: int = 0
    total_size_bytes: int = 0
    compression_ratio: float | None = None
