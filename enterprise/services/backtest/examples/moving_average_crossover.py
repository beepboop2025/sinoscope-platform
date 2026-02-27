"""
Moving Average Crossover Strategy Example.

A classic trend-following strategy that generates buy/sell signals
based on the crossover of fast and slow moving averages.
"""

from typing import Optional
from collections import deque

import numpy as np


try:
    from ..engine import Signal, Portfolio, MarketEvent
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from engine import Signal, Portfolio, MarketEvent


class MACrossoverStrategy:
    """
    Moving Average Crossover Strategy.
    
    Generates BUY signals when the fast moving average crosses above
    the slow moving average, and SELL signals when it crosses below.
    
    Parameters:
    -----------
    fast_period : int
        Period for fast moving average (default: 20)
    slow_period : int
        Period for slow moving average (default: 50)
    ma_type : str
        Type of moving average: 'sma', 'ema' (default: 'sma')
    """
    
    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        ma_type: str = "sma",
    ):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")
        
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.ma_type = ma_type
        
        # Price history storage
        self.price_history: dict = {}
        self.ma_history: dict = {}
    
    def _calculate_ma(self, prices: list, period: int) -> float:
        """Calculate moving average of specified type."""
        if len(prices) < period:
            return np.mean(prices) if prices else 0.0
        
        if self.ma_type == "sma":
            return np.mean(prices[-period:])
        elif self.ma_type == "ema":
            # EMA calculation
            multiplier = 2 / (period + 1)
            ema = prices[0]
            for price in prices[1:]:
                ema = (price - ema) * multiplier + ema
            return ema
        else:
            raise ValueError(f"Unknown MA type: {self.ma_type}")
    
    def on_bar(self, bar: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """
        Process a bar event and generate trading signals.
        
        Parameters:
        -----------
        bar : MarketEvent
            Current bar data
        portfolio : Portfolio
            Current portfolio state
            
        Returns:
        --------
        Signal or None
            Trading signal if conditions are met
        """
        symbol = bar.symbol
        close_price = bar.close_price
        
        if close_price is None or close_price <= 0:
            return None
        
        # Initialize price history for symbol
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.ma_history[symbol] = {'fast': [], 'slow': []}
        
        # Update price history
        self.price_history[symbol].append(close_price)
        
        # Wait for enough data
        if len(self.price_history[symbol]) < self.slow_period + 1:
            return None
        
        prices = self.price_history[symbol]
        
        # Calculate moving averages
        fast_ma = self._calculate_ma(prices, self.fast_period)
        slow_ma = self._calculate_ma(prices, self.slow_period)
        
        # Store MA history
        self.ma_history[symbol]['fast'].append(fast_ma)
        self.ma_history[symbol]['slow'].append(slow_ma)
        
        # Need at least 2 MA values to detect crossover
        if len(self.ma_history[symbol]['fast']) < 2:
            return None
        
        fast_prev = self.ma_history[symbol]['fast'][-2]
        slow_prev = self.ma_history[symbol]['slow'][-2]
        
        # Detect crossover
        # Golden Cross: Fast MA crosses above Slow MA
        if fast_ma > slow_ma and fast_prev <= slow_prev:
            return Signal.BUY
        
        # Death Cross: Fast MA crosses below Slow MA
        if fast_ma < slow_ma and fast_prev >= slow_prev:
            return Signal.SELL
        
        return Signal.HOLD
    
    def on_tick(self, tick: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """Process tick data (not typically used for MA strategies)."""
        # MA strategies typically work on bars, not ticks
        return None
    
    def on_order_fill(self, fill, portfolio: Portfolio) -> None:
        """Handle order fill notifications."""
        # Could implement position management here
        pass
    
    def get_state(self) -> dict:
        """Get current strategy state for serialization."""
        return {
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'ma_type': self.ma_type,
            'price_history': {k: list(v)[-100:] for k, v in self.price_history.items()},
            'ma_history': {k: {'fast': list(v['fast'])[-100:], 
                              'slow': list(v['slow'])[-100:]} 
                          for k, v in self.ma_history.items()},
        }
    
    @classmethod
    def from_state(cls, state: dict) -> 'MACrossoverStrategy':
        """Restore strategy from serialized state."""
        strategy = cls(
            fast_period=state['fast_period'],
            slow_period=state['slow_period'],
            ma_type=state['ma_type'],
        )
        strategy.price_history = state.get('price_history', {})
        strategy.ma_history = state.get('ma_history', {})
        return strategy


# Example usage and backtest script
if __name__ == "__main__":
    import pandas as pd
    import sys
    from pathlib import Path
    
    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from engine import BacktestEngine, BacktestConfig
    
    # Create sample data
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, len(dates))
    prices = 100 * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.001, len(dates))),
        'high': prices * (1 + abs(np.random.normal(0, 0.01, len(dates)))),
        'low': prices * (1 - abs(np.random.normal(0, 0.01, len(dates)))),
        'close': prices,
        'volume': np.random.randint(1_000_000, 10_000_000, len(dates)),
    }, index=dates)
    
    # Configure backtest
    config = BacktestConfig(
        initial_capital=100_000,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=['AAPL'],
        commission_rate=0.001,
        slippage_bps=1.0,
    )
    
    # Run backtest
    engine = BacktestEngine(config)
    engine.load_data(data)
    
    strategy = MACrossoverStrategy(fast_period=20, slow_period=50)
    results = engine.run(strategy)
    
    # Print results
    print("\n" + "="*60)
    print("MOVING AVERAGE CROSSOVER STRATEGY BACKTEST RESULTS")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Fast Period: {strategy.fast_period}")
    print(f"  Slow Period: {strategy.slow_period}")
    print(f"  MA Type: {strategy.ma_type}")
    print(f"\nPerformance:")
    print(f"  Total Return: {results.metrics.total_return:.2%}")
    print(f"  Sharpe Ratio: {results.metrics.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {results.metrics.max_drawdown:.2%}")
    print(f"  Total Trades: {results.trade_stats.total_trades}")
    print(f"  Win Rate: {results.trade_stats.win_rate:.1%}")
    print("="*60)
