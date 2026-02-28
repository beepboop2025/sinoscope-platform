"""Pydantic v2 schemas for backtesting framework."""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------
class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    dsl_config: dict = Field(
        ...,
        examples=[
            {
                "rules": [
                    {"indicator": "sma_cross", "params": {"fast": 10, "slow": 30}, "action": "buy"},
                    {"indicator": "sma_cross", "params": {"fast": 10, "slow": 30}, "action": "sell"},
                ],
                "stop_loss": 0.05,
                "take_profit": 0.10,
            }
        ],
    )
    is_public: bool = False


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    dsl_config: dict | None = None
    is_public: bool | None = None


class StrategyResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    dsl_config: str  # JSON string from DB
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Backtest Run
# ---------------------------------------------------------------------------
class BacktestRunCreate(BaseModel):
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: float = Field(default=100000.0, gt=0)


class BacktestRunResponse(BaseModel):
    id: str
    strategy_id: str
    user_id: str
    status: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float | None = None
    total_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    total_trades: int | None = None
    win_rate: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Backtest Trade
# ---------------------------------------------------------------------------
class BacktestTradeResponse(BaseModel):
    id: str
    backtest_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    commission: float
    slippage: float
    timestamp: datetime
    pnl: float | None = None

    model_config = {"from_attributes": True}
