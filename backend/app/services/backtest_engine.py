"""Backtesting engine — event-driven tick replay with DSL interpretation.

Pure Python implementation — no pandas/numpy dependency.
"""

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Signal:
    timestamp: datetime
    action: str  # "buy" or "sell"
    symbol: str
    strength: float = 1.0


@dataclass
class Trade:
    timestamp: datetime
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    commission: float = 0.0
    slippage: float = 0.0
    pnl: float | None = None


@dataclass
class BacktestResult:
    trades: list[Trade]
    final_capital: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    daily_returns: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Technical indicators (pure Python)
# ---------------------------------------------------------------------------
class BacktestEngine:
    """Event-driven backtesting engine with DSL strategy interpretation."""

    @staticmethod
    def calculate_sma(prices: list[float], period: int) -> list[float | None]:
        """Simple Moving Average.

        Returns list of same length as prices; first (period-1) values are None.
        """
        if period <= 0 or not prices:
            return [None] * len(prices)

        result: list[float | None] = [None] * len(prices)
        if period > len(prices):
            return result

        window_sum = sum(prices[:period])
        result[period - 1] = window_sum / period

        for i in range(period, len(prices)):
            window_sum += prices[i] - prices[i - period]
            result[i] = window_sum / period

        return result

    @staticmethod
    def calculate_ema(prices: list[float], period: int) -> list[float | None]:
        """Exponential Moving Average.

        Returns list of same length as prices; first (period-1) values are None.
        """
        if period <= 0 or not prices:
            return [None] * len(prices)

        result: list[float | None] = [None] * len(prices)
        if period > len(prices):
            return result

        # Seed with SMA
        sma_seed = sum(prices[:period]) / period
        result[period - 1] = sma_seed

        multiplier = 2.0 / (period + 1)
        for i in range(period, len(prices)):
            prev = result[i - 1]
            if prev is None:
                result[i] = prices[i]
            else:
                result[i] = (prices[i] - prev) * multiplier + prev

        return result

    @staticmethod
    def calculate_rsi(prices: list[float], period: int = 14) -> list[float | None]:
        """Relative Strength Index.

        Returns list of same length as prices; first `period` values are None.
        """
        if period <= 0 or len(prices) < period + 1:
            return [None] * len(prices)

        result: list[float | None] = [None] * len(prices)
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Initial average gain/loss
        gains = [max(d, 0.0) for d in deltas[:period]]
        losses = [abs(min(d, 0.0)) for d in deltas[:period]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            result[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[period] = 100.0 - (100.0 / (1.0 + rs))

        # Smoothed RSI
        for i in range(period, len(deltas)):
            gain = max(deltas[i], 0.0)
            loss = abs(min(deltas[i], 0.0))

            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

            if avg_loss == 0:
                result[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                result[i + 1] = 100.0 - (100.0 / (1.0 + rs))

        return result

    @staticmethod
    def interpret_dsl(
        dsl_config: dict,
        indicators: dict[str, list[float | None]],
        prices: list[float],
        timestamps: list[datetime],
        symbol: str = "UNKNOWN",
    ) -> list[Signal]:
        """Interpret a strategy DSL config and generate trading signals.

        DSL format example:
        {
            "rules": [
                {"indicator": "sma_cross", "params": {"fast": 10, "slow": 30}, "action": "buy"},
                {"indicator": "rsi_oversold", "params": {"period": 14, "threshold": 30}, "action": "buy"},
                {"indicator": "rsi_overbought", "params": {"period": 14, "threshold": 70}, "action": "sell"},
            ],
            "stop_loss": 0.05,
            "take_profit": 0.10,
        }
        """
        signals: list[Signal] = []
        rules = dsl_config.get("rules", [])

        for rule in rules:
            indicator = rule.get("indicator", "")
            params = rule.get("params", {})
            action = rule.get("action", "buy")

            if indicator == "sma_cross":
                fast_key = f"sma_{params.get('fast', 10)}"
                slow_key = f"sma_{params.get('slow', 30)}"
                fast_sma = indicators.get(fast_key, [])
                slow_sma = indicators.get(slow_key, [])

                for i in range(1, min(len(fast_sma), len(slow_sma), len(timestamps))):
                    if fast_sma[i] is None or slow_sma[i] is None:
                        continue
                    if fast_sma[i - 1] is None or slow_sma[i - 1] is None:
                        continue

                    if action == "buy":
                        # Buy when fast crosses above slow
                        if fast_sma[i - 1] <= slow_sma[i - 1] and fast_sma[i] > slow_sma[i]:
                            signals.append(Signal(
                                timestamp=timestamps[i],
                                action="buy",
                                symbol=symbol,
                                strength=1.0,
                            ))
                    elif action == "sell":
                        # Sell when fast crosses below slow
                        if fast_sma[i - 1] >= slow_sma[i - 1] and fast_sma[i] < slow_sma[i]:
                            signals.append(Signal(
                                timestamp=timestamps[i],
                                action="sell",
                                symbol=symbol,
                                strength=1.0,
                            ))

            elif indicator == "ema_cross":
                fast_key = f"ema_{params.get('fast', 12)}"
                slow_key = f"ema_{params.get('slow', 26)}"
                fast_ema = indicators.get(fast_key, [])
                slow_ema = indicators.get(slow_key, [])

                for i in range(1, min(len(fast_ema), len(slow_ema), len(timestamps))):
                    if fast_ema[i] is None or slow_ema[i] is None:
                        continue
                    if fast_ema[i - 1] is None or slow_ema[i - 1] is None:
                        continue

                    if action == "buy" and fast_ema[i - 1] <= slow_ema[i - 1] and fast_ema[i] > slow_ema[i]:
                        signals.append(Signal(timestamp=timestamps[i], action="buy", symbol=symbol))
                    elif action == "sell" and fast_ema[i - 1] >= slow_ema[i - 1] and fast_ema[i] < slow_ema[i]:
                        signals.append(Signal(timestamp=timestamps[i], action="sell", symbol=symbol))

            elif indicator == "rsi_oversold":
                period = params.get("period", 14)
                threshold = params.get("threshold", 30)
                rsi_key = f"rsi_{period}"
                rsi = indicators.get(rsi_key, [])

                for i in range(1, min(len(rsi), len(timestamps))):
                    if rsi[i] is not None and rsi[i - 1] is not None:
                        if rsi[i - 1] <= threshold and rsi[i] > threshold:
                            signals.append(Signal(timestamp=timestamps[i], action="buy", symbol=symbol))

            elif indicator == "rsi_overbought":
                period = params.get("period", 14)
                threshold = params.get("threshold", 70)
                rsi_key = f"rsi_{period}"
                rsi = indicators.get(rsi_key, [])

                for i in range(1, min(len(rsi), len(timestamps))):
                    if rsi[i] is not None and rsi[i - 1] is not None:
                        if rsi[i - 1] >= threshold and rsi[i] < threshold:
                            signals.append(Signal(timestamp=timestamps[i], action="sell", symbol=symbol))

        # Sort signals by timestamp
        signals.sort(key=lambda s: s.timestamp)
        return signals

    @staticmethod
    def run_backtest(
        strategy_dsl: dict,
        prices: list[float],
        timestamps: list[datetime],
        symbol: str = "UNKNOWN",
        initial_capital: float = 100000.0,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.0005,
    ) -> BacktestResult:
        """Run a full backtest: compute indicators, interpret DSL, simulate trades.

        Args:
            strategy_dsl: Strategy DSL configuration dict.
            prices: List of prices (close prices for each bar).
            timestamps: Corresponding timestamps.
            symbol: Asset symbol being traded.
            initial_capital: Starting capital.
            commission_pct: Commission as fraction of trade value (0.001 = 0.1%).
            slippage_pct: Slippage as fraction of price (0.0005 = 0.05%).

        Returns:
            BacktestResult with trades, metrics.
        """
        if not prices or len(prices) < 2:
            return BacktestResult(
                trades=[], final_capital=initial_capital, total_return=0.0,
                sharpe_ratio=0.0, max_drawdown=0.0, win_rate=0.0, total_trades=0,
            )

        # --- Step 1: Compute all indicators needed by the DSL ---
        indicators: dict[str, list[float | None]] = {}
        rules = strategy_dsl.get("rules", [])

        for rule in rules:
            indicator = rule.get("indicator", "")
            params = rule.get("params", {})

            if indicator in ("sma_cross",):
                fast_p = params.get("fast", 10)
                slow_p = params.get("slow", 30)
                if f"sma_{fast_p}" not in indicators:
                    indicators[f"sma_{fast_p}"] = BacktestEngine.calculate_sma(prices, fast_p)
                if f"sma_{slow_p}" not in indicators:
                    indicators[f"sma_{slow_p}"] = BacktestEngine.calculate_sma(prices, slow_p)

            elif indicator in ("ema_cross",):
                fast_p = params.get("fast", 12)
                slow_p = params.get("slow", 26)
                if f"ema_{fast_p}" not in indicators:
                    indicators[f"ema_{fast_p}"] = BacktestEngine.calculate_ema(prices, fast_p)
                if f"ema_{slow_p}" not in indicators:
                    indicators[f"ema_{slow_p}"] = BacktestEngine.calculate_ema(prices, slow_p)

            elif indicator in ("rsi_oversold", "rsi_overbought"):
                period = params.get("period", 14)
                if f"rsi_{period}" not in indicators:
                    indicators[f"rsi_{period}"] = BacktestEngine.calculate_rsi(prices, period)

        # --- Step 2: Generate signals ---
        signals = BacktestEngine.interpret_dsl(
            dsl_config=strategy_dsl,
            indicators=indicators,
            prices=prices,
            timestamps=timestamps,
            symbol=symbol,
        )

        # --- Step 3: Simulate trading ---
        stop_loss = strategy_dsl.get("stop_loss", 0.0)
        take_profit = strategy_dsl.get("take_profit", 0.0)

        cash = initial_capital
        position: float = 0.0  # number of shares held
        entry_price: float = 0.0
        trades: list[Trade] = []

        # Index signals by timestamp for O(1) lookup
        signal_map: dict[datetime, Signal] = {}
        for sig in signals:
            # Keep only the last signal per timestamp
            signal_map[sig.timestamp] = sig

        # Daily portfolio values for metric calculation
        daily_values: list[float] = []

        for i, (price, ts) in enumerate(zip(prices, timestamps)):
            portfolio_value = cash + position * price
            daily_values.append(portfolio_value)

            # Check stop-loss / take-profit on existing position
            if position > 0 and entry_price > 0:
                change = (price - entry_price) / entry_price

                if stop_loss > 0 and change <= -stop_loss:
                    # Trigger stop-loss: sell all
                    slip = price * slippage_pct
                    sell_price = price - slip
                    comm = abs(position * sell_price) * commission_pct
                    proceeds = position * sell_price - comm
                    pnl = proceeds - position * entry_price
                    trades.append(Trade(
                        timestamp=ts, symbol=symbol, side="sell",
                        quantity=position, price=sell_price,
                        commission=round(comm, 4), slippage=round(slip, 4),
                        pnl=round(pnl, 4),
                    ))
                    cash += proceeds
                    position = 0.0
                    entry_price = 0.0
                    continue

                if take_profit > 0 and change >= take_profit:
                    # Trigger take-profit: sell all
                    slip = price * slippage_pct
                    sell_price = price - slip
                    comm = abs(position * sell_price) * commission_pct
                    proceeds = position * sell_price - comm
                    pnl = proceeds - position * entry_price
                    trades.append(Trade(
                        timestamp=ts, symbol=symbol, side="sell",
                        quantity=position, price=sell_price,
                        commission=round(comm, 4), slippage=round(slip, 4),
                        pnl=round(pnl, 4),
                    ))
                    cash += proceeds
                    position = 0.0
                    entry_price = 0.0
                    continue

            # Process signal for this timestamp
            sig = signal_map.get(ts)
            if sig is None:
                continue

            if sig.action == "buy" and position == 0.0 and cash > 0:
                # Buy: use all available cash
                slip = price * slippage_pct
                buy_price = price + slip
                comm_rate = commission_pct
                # shares = cash / (buy_price * (1 + comm_rate))
                max_shares = cash / (buy_price * (1.0 + comm_rate))
                quantity = math.floor(max_shares * 100) / 100  # round down to 2 decimal places
                if quantity <= 0:
                    continue
                cost = quantity * buy_price
                comm = cost * comm_rate
                cash -= (cost + comm)
                position = quantity
                entry_price = buy_price
                trades.append(Trade(
                    timestamp=ts, symbol=symbol, side="buy",
                    quantity=quantity, price=round(buy_price, 4),
                    commission=round(comm, 4), slippage=round(slip, 4),
                ))

            elif sig.action == "sell" and position > 0:
                # Sell all
                slip = price * slippage_pct
                sell_price = price - slip
                comm = abs(position * sell_price) * commission_pct
                proceeds = position * sell_price - comm
                pnl = proceeds - position * entry_price
                trades.append(Trade(
                    timestamp=ts, symbol=symbol, side="sell",
                    quantity=position, price=round(sell_price, 4),
                    commission=round(comm, 4), slippage=round(slip, 4),
                    pnl=round(pnl, 4),
                ))
                cash += proceeds
                position = 0.0
                entry_price = 0.0

        # --- Step 4: Compute metrics ---
        final_capital = cash + position * prices[-1] if prices else initial_capital
        total_return = (final_capital - initial_capital) / initial_capital if initial_capital > 0 else 0.0

        # Daily returns from portfolio values
        daily_returns: list[float] = []
        for i in range(1, len(daily_values)):
            if daily_values[i - 1] > 0:
                daily_returns.append((daily_values[i] - daily_values[i - 1]) / daily_values[i - 1])

        # Sharpe ratio (annualized, risk-free = 0)
        sharpe_ratio = 0.0
        if len(daily_returns) >= 2:
            mean_r = statistics.mean(daily_returns)
            std_r = statistics.stdev(daily_returns)
            if std_r > 0:
                sharpe_ratio = (mean_r / std_r) * math.sqrt(252)

        # Max drawdown
        max_drawdown = 0.0
        peak = initial_capital
        for val in daily_values:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

        # Win rate
        sell_trades = [t for t in trades if t.side == "sell" and t.pnl is not None]
        total_trades_count = len(sell_trades)
        wins = sum(1 for t in sell_trades if t.pnl is not None and t.pnl > 0)
        win_rate = (wins / total_trades_count) if total_trades_count > 0 else 0.0

        return BacktestResult(
            trades=trades,
            final_capital=round(final_capital, 4),
            total_return=round(total_return, 6),
            sharpe_ratio=round(sharpe_ratio, 6),
            max_drawdown=round(max_drawdown, 6),
            win_rate=round(win_rate, 4),
            total_trades=len(trades),
            daily_returns=daily_returns,
        )
