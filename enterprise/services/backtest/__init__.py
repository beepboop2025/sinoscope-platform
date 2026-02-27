"""
DragonScope Enterprise Backtesting Engine

A professional-grade, event-driven backtesting framework for quantitative trading strategies.
"""

from .engine import BacktestEngine, BacktestConfig, BacktestResults
from .analytics import PerformanceMetrics, DrawdownAnalyzer, TradeStatistics
from .execution_models import (
    BaseExecutionModel,
    MarketOrderModel,
    LimitOrderModel,
    StopOrderModel,
    SmartOrderRouterModel,
)
from .market_impact import (
    MarketImpactModel,
    LinearImpactModel,
    SquareRootImpactModel,
)

__version__ = "2.0.0"
__author__ = "DragonScope Enterprise"

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResults",
    "PerformanceMetrics",
    "DrawdownAnalyzer",
    "TradeStatistics",
    "BaseExecutionModel",
    "MarketOrderModel",
    "LimitOrderModel",
    "StopOrderModel",
    "SmartOrderRouterModel",
    "MarketImpactModel",
    "LinearImpactModel",
    "SquareRootImpactModel",
]
