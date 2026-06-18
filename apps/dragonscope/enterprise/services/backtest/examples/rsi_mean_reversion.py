"""
RSI Mean Reversion Strategy Example.

A contrarian strategy that generates buy signals when RSI indicates
oversold conditions and sell signals when overbought.
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


class RSIMeanReversionStrategy:
    """
    RSI Mean Reversion Strategy.
    
    Generates BUY signals when RSI falls below oversold threshold
    and SELL signals when RSI rises above overbought threshold.
    
    Includes optional confirmation mechanisms and position sizing
    based on RSI extremity.
    
    Parameters:
    -----------
    period : int
        RSI calculation period (default: 14)
    oversold : float
        Oversold threshold (default: 30)
    overbought : float
        Overbought threshold (default: 70)
    use_confirmation : bool
        Require confirmation before signal (default: True)
    mean_reversion_mode : str
        'extreme' - trade at extreme levels
        'crossover' - trade on threshold crossovers
        (default: 'extreme')
    """
    
    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        use_confirmation: bool = True,
        mean_reversion_mode: str = "extreme",
    ):
        if not 0 < oversold < overbought < 100:
            raise ValueError("Must have 0 < oversold < overbought < 100")
        
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.use_confirmation = use_confirmation
        self.mean_reversion_mode = mean_reversion_mode
        
        # State tracking
        self.price_history: dict = {}
        self.rsi_history: dict = {}
        self.confirmation_state: dict = {}  # Track state for confirmation
        self.last_signal: dict = {}  # Prevent duplicate signals
    
    def _calculate_rsi(self, prices: list) -> float:
        """
        Calculate RSI (Relative Strength Index).
        
        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss
        """
        if len(prices) < self.period + 1:
            return 50.0  # Neutral RSI when insufficient data
        
        # Calculate price changes
        deltas = np.diff(prices[-(self.period + 1):])
        
        # Separate gains and losses
        gains = deltas[deltas > 0]
        losses = -deltas[deltas < 0]
        
        if len(losses) == 0:
            return 100.0  # All gains = max RSI
        if len(gains) == 0:
            return 0.0    # All losses = min RSI
        
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001  # Avoid div by zero
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_smoothed_rsi(self, prices: list) -> float:
        """
        Calculate RSI using Wilder's smoothing method.
        More accurate for continuous calculation.
        """
        if len(prices) < self.period + 1:
            return 50.0
        
        deltas = np.diff(prices[-(self.period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Initial averages
        avg_gain = np.mean(gains[:self.period])
        avg_loss = np.mean(losses[:self.period])
        
        # Apply smoothing
        alpha = 1 / self.period
        for i in range(self.period, len(gains)):
            avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
            avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _get_position_size_multiplier(self, rsi: float) -> float:
        """
        Calculate position size based on RSI extremity.
        More extreme RSI = larger position (mean reversion confidence).
        """
        if rsi <= self.oversold:
            # Scale from 0.5 to 1.0 as RSI goes from oversold to 0
            return 0.5 + 0.5 * (self.oversold - rsi) / self.oversold
        elif rsi >= self.overbought:
            # Scale from 0.5 to 1.0 as RSI goes from overbought to 100
            return 0.5 + 0.5 * (rsi - self.overbought) / (100 - self.overbought)
        return 0.5
    
    def on_bar(self, bar: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """
        Process bar and generate mean reversion signals.
        
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
        
        # Initialize tracking for symbol
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.rsi_history[symbol] = []
            self.confirmation_state[symbol] = None
            self.last_signal[symbol] = None
        
        # Update price history
        self.price_history[symbol].append(close_price)
        
        # Need enough data
        if len(self.price_history[symbol]) < self.period + 1:
            return None
        
        # Calculate RSI
        rsi = self._calculate_rsi(self.price_history[symbol])
        self.rsi_history[symbol].append(rsi)
        
        # Generate signals based on mode
        if self.mean_reversion_mode == "extreme":
            return self._check_extreme_signal(symbol, rsi)
        else:  # crossover mode
            return self._check_crossover_signal(symbol, rsi)
    
    def _check_extreme_signal(self, symbol: str, rsi: float) -> Optional[Signal]:
        """Check for extreme RSI signals with optional confirmation."""
        state = self.confirmation_state[symbol]
        
        # Check for oversold condition
        if rsi < self.oversold:
            if state == 'oversold_confirmed':
                # Already confirmed, wait for exit
                return Signal.HOLD
            elif state == 'oversold':
                # Second consecutive oversold reading - confirm
                if self.use_confirmation:
                    self.confirmation_state[symbol] = 'oversold_confirmed'
                    self.last_signal[symbol] = Signal.BUY
                    return Signal.BUY
            else:
                # First oversold reading
                self.confirmation_state[symbol] = 'oversold'
                if not self.use_confirmation:
                    self.last_signal[symbol] = Signal.BUY
                    return Signal.BUY
        
        # Check for overbought condition
        elif rsi > self.overbought:
            if state == 'overbought_confirmed':
                return Signal.HOLD
            elif state == 'overbought':
                if self.use_confirmation:
                    self.confirmation_state[symbol] = 'overbought_confirmed'
                    self.last_signal[symbol] = Signal.SELL
                    return Signal.SELL
            else:
                self.confirmation_state[symbol] = 'overbought'
                if not self.use_confirmation:
                    self.last_signal[symbol] = Signal.SELL
                    return Signal.SELL
        
        # RSI in neutral zone - reset confirmation
        elif self.oversold <= rsi <= self.overbought:
            self.confirmation_state[symbol] = None
        
        return Signal.HOLD
    
    def _check_crossover_signal(self, symbol: str, rsi: float) -> Optional[Signal]:
        """Check for threshold crossover signals."""
        if len(self.rsi_history[symbol]) < 2:
            return None
        
        prev_rsi = self.rsi_history[symbol][-2]
        
        # Oversold crossover (below to above)
        if prev_rsi < self.oversold and rsi >= self.oversold:
            if self.last_signal[symbol] != Signal.BUY:
                self.last_signal[symbol] = Signal.BUY
                return Signal.BUY
        
        # Overbought crossover (above to below)
        if prev_rsi > self.overbought and rsi <= self.overbought:
            if self.last_signal[symbol] != Signal.SELL:
                self.last_signal[symbol] = Signal.SELL
                return Signal.SELL
        
        return Signal.HOLD
    
    def on_tick(self, tick: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """Process tick data."""
        return None
    
    def on_order_fill(self, fill, portfolio: Portfolio) -> None:
        """Handle order fills."""
        pass
    
    def get_current_rsi(self, symbol: str) -> Optional[float]:
        """Get current RSI value for a symbol."""
        history = self.rsi_history.get(symbol, [])
        return history[-1] if history else None
    
    def get_state(self) -> dict:
        """Get strategy state for serialization."""
        return {
            'period': self.period,
            'oversold': self.oversold,
            'overbought': self.overbought,
            'use_confirmation': self.use_confirmation,
            'mean_reversion_mode': self.mean_reversion_mode,
            'price_history': {k: list(v)[-self.period*2:] for k, v in self.price_history.items()},
            'rsi_history': {k: list(v)[-50:] for k, v in self.rsi_history.items()},
            'confirmation_state': self.confirmation_state,
        }
    
    @classmethod
    def from_state(cls, state: dict) -> 'RSIMeanReversionStrategy':
        """Restore strategy from serialized state."""
        strategy = cls(
            period=state['period'],
            oversold=state['oversold'],
            overbought=state['overbought'],
            use_confirmation=state['use_confirmation'],
            mean_reversion_mode=state['mean_reversion_mode'],
        )
        strategy.price_history = state.get('price_history', {})
        strategy.rsi_history = state.get('rsi_history', {})
        strategy.confirmation_state = state.get('confirmation_state', {})
        return strategy


if __name__ == "__main__":
    import pandas as pd
    import sys
    from pathlib import Path
    
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from engine import BacktestEngine, BacktestConfig
    
    # Create mean-reverting sample data
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    np.random.seed(42)
    
    # Generate mean-reverting price series
    prices = [100]
    for i in range(1, len(dates)):
        # Pull back to mean with noise
        deviation = prices[-1] - 100
        mean_reversion = -0.05 * deviation
        noise = np.random.normal(0, 1)
        prices.append(prices[-1] + mean_reversion + noise)
    
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
    
    strategy = RSIMeanReversionStrategy(
        period=14,
        oversold=30,
        overbought=70,
        use_confirmation=True,
    )
    
    results = engine.run(strategy)
    
    print("\n" + "="*60)
    print("RSI MEAN REVERSION STRATEGY BACKTEST RESULTS")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  RSI Period: {strategy.period}")
    print(f"  Oversold: {strategy.oversold}")
    print(f"  Overbought: {strategy.overbought}")
    print(f"  Confirmation: {strategy.use_confirmation}")
    print(f"\nPerformance:")
    print(f"  Total Return: {results.metrics.total_return:.2%}")
    print(f"  Sharpe Ratio: {results.metrics.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {results.metrics.max_drawdown:.2%}")
    print(f"  Total Trades: {results.trade_stats.total_trades}")
    print(f"  Win Rate: {results.trade_stats.win_rate:.1%}")
    print("="*60)
