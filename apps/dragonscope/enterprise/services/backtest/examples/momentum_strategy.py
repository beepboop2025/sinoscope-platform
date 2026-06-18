"""
Momentum Strategy Example.

A trend-following strategy based on price momentum.
Includes various momentum measures and position sizing.
"""

from typing import Optional, List
from collections import deque
from enum import Enum

import numpy as np


try:
    from ..engine import Signal, Portfolio, MarketEvent
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from engine import Signal, Portfolio, MarketEvent


class MomentumType(Enum):
    """Types of momentum measurement."""
    PRICE_MOMENTUM = "price"           # Simple price return
    RSI_MOMENTUM = "rsi"               # RSI-based momentum
    MACD_MOMENTUM = "macd"             # MACD-based momentum
    RATE_OF_CHANGE = "roc"             # Rate of change


class MomentumStrategy:
    """
    Multi-factor Momentum Strategy.
    
    Generates signals based on price momentum over a specified lookback period.
    Can use various momentum measures and includes trend filtering.
    
    Parameters:
    -----------
    lookback : int
        Lookback period for momentum calculation (default: 12)
    holding_period : int
        Maximum holding period before re-evaluation (default: 1)
    momentum_type : MomentumType
        Type of momentum measure to use (default: PRICE_MOMENTUM)
    long_threshold : float
        Minimum momentum for long entry (default: 0.0)
    short_threshold : float
        Maximum momentum for short entry (default: 0.0)
    use_trend_filter : bool
        Only trade in direction of longer-term trend (default: True)
    trend_filter_period : int
        Period for trend filter MA (default: 50)
    volatility_filter : bool
        Skip trades in high volatility regimes (default: False)
    volatility_threshold : float
        Annualized volatility threshold (default: 0.30)
    """
    
    def __init__(
        self,
        lookback: int = 12,
        holding_period: int = 1,
        momentum_type: MomentumType = MomentumType.PRICE_MOMENTUM,
        long_threshold: float = 0.0,
        short_threshold: float = 0.0,
        use_trend_filter: bool = True,
        trend_filter_period: int = 50,
        volatility_filter: bool = False,
        volatility_threshold: float = 0.30,
    ):
        self.lookback = lookback
        self.holding_period = holding_period
        self.momentum_type = momentum_type
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.use_trend_filter = use_trend_filter
        self.trend_filter_period = trend_filter_period
        self.volatility_filter = volatility_filter
        self.volatility_threshold = volatility_threshold
        
        # State tracking
        self.price_history: dict = {}
        self.momentum_history: dict = {}
        self.position_entry_time: dict = {}
        self.position_entry_price: dict = {}
        self.current_momentum: dict = {}
        self.volatility_regime: dict = {}
    
    def _calculate_momentum(self, prices: List[float]) -> float:
        """Calculate momentum based on selected type."""
        if len(prices) < self.lookback + 1:
            return 0.0
        
        if self.momentum_type == MomentumType.PRICE_MOMENTUM:
            # Simple price momentum: (P_t - P_{t-n}) / P_{t-n}
            return (prices[-1] - prices[-self.lookback - 1]) / prices[-self.lookback - 1]
        
        elif self.momentum_type == MomentumType.RATE_OF_CHANGE:
            # Rate of change: P_t / P_{t-n} - 1
            return prices[-1] / prices[-self.lookback - 1] - 1
        
        elif self.momentum_type == MomentumType.RSI_MOMENTUM:
            # Use RSI as momentum indicator (50 = neutral)
            return self._calculate_rsi(prices) - 50
        
        elif self.momentum_type == MomentumType.MACD_MOMENTUM:
            # MACD histogram as momentum
            return self._calculate_macd_histogram(prices)
        
        return 0.0
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI for momentum measure."""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses) if np.mean(losses) > 0 else 0.001
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd_histogram(self, prices: List[float]) -> float:
        """Calculate MACD histogram."""
        if len(prices) < 35:
            return 0.0
        
        # Calculate EMAs
        def ema(data, period):
            multiplier = 2 / (period + 1)
            result = [data[0]]
            for price in data[1:]:
                result.append((price - result[-1]) * multiplier + result[-1])
            return result
        
        ema12 = ema(prices, 12)[-1]
        ema26 = ema(prices, 26)[-1]
        macd_line = ema12 - ema26
        
        # Signal line (9-period EMA of MACD)
        macd_history = [ema(prices[:i+1], 12)[-1] - ema(prices[:i+1], 26)[-1] 
                       for i in range(len(prices) - 9, len(prices))]
        signal_line = ema(macd_history, 9)[-1]
        
        return macd_line - signal_line
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate annualized volatility."""
        if len(prices) < 20:
            return 0.0
        
        returns = np.diff(prices[-20:]) / prices[-20:-1]
        return np.std(returns) * np.sqrt(252)
    
    def _check_trend_filter(self, prices: List[float]) -> int:
        """
        Check if price is above/below trend filter MA.
        Returns: 1 (uptrend), -1 (downtrend), 0 (neutral)
        """
        if len(prices) < self.trend_filter_period:
            return 0
        
        ma = np.mean(prices[-self.trend_filter_period:])
        current_price = prices[-1]
        
        if current_price > ma * 1.01:  # 1% buffer
            return 1
        elif current_price < ma * 0.99:
            return -1
        return 0
    
    def _check_exit_conditions(self, symbol: str, current_price: float) -> bool:
        """Check if position should be exited based on holding period."""
        if symbol not in self.position_entry_time:
            return False
        
        # Could add more sophisticated exit logic here
        return False
    
    def on_bar(self, bar: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """
        Process bar and generate momentum signals.
        
        Parameters:
        -----------
        bar : MarketEvent
            Current bar data
        portfolio : Portfolio
            Current portfolio state
            
        Returns:
        --------
        Signal or None
        """
        symbol = bar.symbol
        close_price = bar.close_price
        
        if close_price is None or close_price <= 0:
            return None
        
        # Initialize tracking
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.momentum_history[symbol] = []
            self.current_momentum[symbol] = 0.0
        
        # Update price history
        self.price_history[symbol].append(close_price)
        
        # Need enough data
        min_periods = max(self.lookback, self.trend_filter_period) + 1
        if len(self.price_history[symbol]) < min_periods:
            return None
        
        prices = self.price_history[symbol]
        
        # Calculate momentum
        momentum = self._calculate_momentum(prices)
        self.current_momentum[symbol] = momentum
        self.momentum_history[symbol].append(momentum)
        
        # Volatility filter
        if self.volatility_filter:
            vol = self._calculate_volatility(prices)
            self.volatility_regime[symbol] = vol
            if vol > self.volatility_threshold:
                return Signal.HOLD  # Skip in high volatility
        
        # Trend filter
        trend = 0
        if self.use_trend_filter:
            trend = self._check_trend_filter(prices)
        
        # Generate signals
        signal = Signal.HOLD
        
        # Long signal: Positive momentum above threshold
        if momentum > self.long_threshold:
            if not self.use_trend_filter or trend >= 0:
                signal = Signal.BUY
        
        # Short signal: Negative momentum below threshold
        elif momentum < self.short_threshold:
            if not self.use_trend_filter or trend <= 0:
                signal = Signal.SELL
        
        # Check exit conditions for existing positions
        if self._check_exit_conditions(symbol, close_price):
            # Get current position and exit
            position = portfolio.get_position(symbol)
            if position.quantity > 0:
                return Signal.SELL
            elif position.quantity < 0:
                return Signal.BUY
        
        return signal
    
    def on_tick(self, tick: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """Process tick data."""
        return None
    
    def on_order_fill(self, fill, portfolio: Portfolio) -> None:
        """Handle order fills and track entry."""
        if fill.quantity > 0:
            self.position_entry_time[fill.symbol] = fill.timestamp
            self.position_entry_price[fill.symbol] = fill.fill_price
    
    def get_momentum_ranking(self) -> dict:
        """Get current momentum ranking for all tracked symbols."""
        return {
            symbol: {
                'momentum': momentum,
                'volatility': self.volatility_regime.get(symbol, 0),
            }
            for symbol, momentum in self.current_momentum.items()
        }
    
    def get_state(self) -> dict:
        """Get strategy state for serialization."""
        return {
            'lookback': self.lookback,
            'holding_period': self.holding_period,
            'momentum_type': self.momentum_type.value,
            'long_threshold': self.long_threshold,
            'short_threshold': self.short_threshold,
            'use_trend_filter': self.use_trend_filter,
            'trend_filter_period': self.trend_filter_period,
            'volatility_filter': self.volatility_filter,
            'volatility_threshold': self.volatility_threshold,
            'price_history': {k: list(v)[-100:] for k, v in self.price_history.items()},
            'momentum_history': {k: list(v)[-50:] for k, v in self.momentum_history.items()},
        }
    
    @classmethod
    def from_state(cls, state: dict) -> 'MomentumStrategy':
        """Restore strategy from serialized state."""
        strategy = cls(
            lookback=state['lookback'],
            holding_period=state['holding_period'],
            momentum_type=MomentumType(state['momentum_type']),
            long_threshold=state['long_threshold'],
            short_threshold=state['short_threshold'],
            use_trend_filter=state['use_trend_filter'],
            trend_filter_period=state['trend_filter_period'],
            volatility_filter=state['volatility_filter'],
            volatility_threshold=state['volatility_threshold'],
        )
        strategy.price_history = state.get('price_history', {})
        strategy.momentum_history = state.get('momentum_history', {})
        return strategy


class MultiTimeframeMomentumStrategy:
    """
    Multi-timeframe Momentum Strategy.
    
    Combines momentum signals from multiple timeframes for confirmation.
    
    Parameters:
    -----------
    timeframes : dict
        Dictionary mapping timeframe names to (lookback, weight) tuples
    consensus_threshold : float
        Minimum weighted consensus for signal (0-1)
    """
    
    def __init__(
        self,
        timeframes: Optional[dict] = None,
        consensus_threshold: float = 0.6,
    ):
        self.timeframes = timeframes or {
            'short': (5, 0.3),
            'medium': (12, 0.4),
            'long': (26, 0.3),
        }
        self.consensus_threshold = consensus_threshold
        
        self.price_history: dict = {}
        self.momentum_by_tf: dict = {}
    
    def _calculate_tf_momentum(self, prices: List[float], lookback: int) -> float:
        """Calculate momentum for a specific timeframe."""
        if len(prices) < lookback + 1:
            return 0.0
        return (prices[-1] - prices[-lookback - 1]) / prices[-lookback - 1]
    
    def on_bar(self, bar: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """Generate signal based on multi-timeframe momentum consensus."""
        symbol = bar.symbol
        close_price = bar.close_price
        
        if close_price is None:
            return None
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.momentum_by_tf[symbol] = {}
        
        self.price_history[symbol].append(close_price)
        prices = self.price_history[symbol]
        
        # Calculate momentum for each timeframe
        max_lookback = max(tf[0] for tf in self.timeframes.values())
        if len(prices) < max_lookback + 1:
            return None
        
        weighted_signal = 0.0
        total_weight = 0.0
        
        for tf_name, (lookback, weight) in self.timeframes.items():
            momentum = self._calculate_tf_momentum(prices, lookback)
            self.momentum_by_tf[symbol][tf_name] = momentum
            
            # Convert momentum to signal (-1, 0, 1)
            if momentum > 0.01:
                signal = 1
            elif momentum < -0.01:
                signal = -1
            else:
                signal = 0
            
            weighted_signal += signal * weight
            total_weight += weight
        
        # Normalize
        if total_weight > 0:
            weighted_signal /= total_weight
        
        # Generate signal based on consensus
        if weighted_signal >= self.consensus_threshold:
            return Signal.BUY
        elif weighted_signal <= -self.consensus_threshold:
            return Signal.SELL
        
        return Signal.HOLD
    
    def on_tick(self, tick: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        return None
    
    def on_order_fill(self, fill, portfolio: Portfolio) -> None:
        pass


if __name__ == "__main__":
    import pandas as pd
    import sys
    from pathlib import Path
    
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from engine import BacktestEngine, BacktestConfig
    
    # Create trending sample data
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    np.random.seed(42)
    
    # Generate trending price series with momentum
    prices = [100]
    trend = 0.0005  # Small upward drift
    
    for i in range(1, len(dates)):
        # Momentum effect: continue previous direction with some persistence
        if i > 1:
            prev_return = (prices[-1] - prices[-2]) / prices[-2]
            momentum = 0.3 * prev_return  # 30% momentum persistence
        else:
            momentum = 0
        
        noise = np.random.normal(0, 0.015)
        daily_return = trend + momentum + noise
        prices.append(prices[-1] * (1 + daily_return))
    
    prices = np.array(prices)
    
    data = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.005, len(dates))),
        'high': prices * (1 + abs(np.random.normal(0, 0.01, len(dates)))),
        'low': prices * (1 - abs(np.random.normal(0, 0.01, len(dates)))),
        'close': prices,
        'volume': np.random.randint(1_000_000, 10_000_000, len(dates)),
    }, index=dates)
    
    config = BacktestConfig(
        initial_capital=100_000,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=['AAPL'],
        commission_rate=0.001,
        slippage_bps=1.0,
    )
    
    engine = BacktestEngine(config)
    engine.load_data(data)
    
    strategy = MomentumStrategy(
        lookback=12,
        momentum_type=MomentumType.PRICE_MOMENTUM,
        use_trend_filter=True,
        long_threshold=0.02,
    )
    
    results = engine.run(strategy)
    
    print("\n" + "="*60)
    print("MOMENTUM STRATEGY BACKTEST RESULTS")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Lookback: {strategy.lookback}")
    print(f"  Momentum Type: {strategy.momentum_type.value}")
    print(f"  Long Threshold: {strategy.long_threshold:.1%}")
    print(f"  Trend Filter: {strategy.use_trend_filter}")
    print(f"\nPerformance:")
    print(f"  Total Return: {results.metrics.total_return:.2%}")
    print(f"  Sharpe Ratio: {results.metrics.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {results.metrics.max_drawdown:.2%}")
    print(f"  Total Trades: {results.trade_stats.total_trades}")
    print(f"  Win Rate: {results.trade_stats.win_rate:.1%}")
    print("="*60)
