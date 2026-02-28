"""
Example Strategies for DragonScope Backtesting Engine.

This package contains example trading strategies demonstrating
various approaches and patterns.
"""

from .moving_average_crossover import MACrossoverStrategy
from .rsi_mean_reversion import RSIMeanReversionStrategy
from .momentum_strategy import MomentumStrategy

__all__ = [
    "MACrossoverStrategy",
    "RSIMeanReversionStrategy",
    "MomentumStrategy",
]
