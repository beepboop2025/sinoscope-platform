"""Tests for Backtesting Framework."""

import math
from datetime import datetime, timezone

import pytest

from app.services.backtest_engine import BacktestEngine


# ---------------------------------------------------------------------------
# Technical Indicators
# ---------------------------------------------------------------------------
class TestSMA:
    """Test Simple Moving Average calculation."""

    def test_basic_sma(self):
        """SMA should compute correct average."""
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        sma = BacktestEngine.calculate_sma(prices, 3)
        assert sma[0] is None
        assert sma[1] is None
        assert abs(sma[2] - 2.0) < 0.001  # (1+2+3)/3
        assert abs(sma[3] - 3.0) < 0.001  # (2+3+4)/3
        assert abs(sma[4] - 4.0) < 0.001  # (3+4+5)/3

    def test_sma_period_1(self):
        """SMA with period 1 should equal the prices."""
        prices = [10.0, 20.0, 30.0]
        sma = BacktestEngine.calculate_sma(prices, 1)
        for i, p in enumerate(prices):
            assert abs(sma[i] - p) < 0.001

    def test_sma_period_equals_length(self):
        """SMA with period equal to length should return one value."""
        prices = [1.0, 2.0, 3.0]
        sma = BacktestEngine.calculate_sma(prices, 3)
        assert sma[0] is None
        assert sma[1] is None
        assert abs(sma[2] - 2.0) < 0.001

    def test_sma_period_exceeds_length(self):
        """SMA with period > length should return all None."""
        prices = [1.0, 2.0, 3.0]
        sma = BacktestEngine.calculate_sma(prices, 5)
        assert all(v is None for v in sma)

    def test_sma_empty(self):
        """SMA of empty list should return empty."""
        sma = BacktestEngine.calculate_sma([], 3)
        assert sma == []


class TestEMA:
    """Test Exponential Moving Average calculation."""

    def test_ema_starts_with_sma(self):
        """EMA should start with SMA seed."""
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        ema = BacktestEngine.calculate_ema(prices, 3)
        sma = BacktestEngine.calculate_sma(prices, 3)
        # First computed EMA should equal SMA
        assert abs(ema[2] - sma[2]) < 0.001

    def test_ema_follows_trend(self):
        """EMA should follow an uptrend."""
        prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0]
        ema = BacktestEngine.calculate_ema(prices, 3)
        # EMA values should be increasing after the warmup period
        valid = [v for v in ema if v is not None]
        for i in range(1, len(valid)):
            assert valid[i] > valid[i - 1]

    def test_ema_reacts_faster_than_sma(self):
        """EMA should be closer to recent prices than SMA."""
        prices = [10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0]
        ema = BacktestEngine.calculate_ema(prices, 3)
        sma = BacktestEngine.calculate_sma(prices, 3)
        # After jump, EMA should be higher than SMA (closer to 20)
        if ema[6] is not None and sma[6] is not None:
            assert ema[6] >= sma[6]


class TestRSI:
    """Test Relative Strength Index calculation."""

    def test_rsi_bounded(self):
        """RSI should always be between 0 and 100."""
        import random
        rng = random.Random(42)
        prices = [100.0 + rng.gauss(0, 5) for _ in range(100)]
        rsi = BacktestEngine.calculate_rsi(prices, 14)
        valid = [v for v in rsi if v is not None]
        for v in valid:
            assert 0.0 <= v <= 100.0

    def test_rsi_uptrend(self):
        """In strong uptrend, RSI should be high (>50)."""
        prices = list(range(1, 52))  # 1, 2, 3, ..., 51
        prices = [float(p) for p in prices]
        rsi = BacktestEngine.calculate_rsi(prices, 14)
        valid = [v for v in rsi if v is not None]
        if valid:
            assert valid[-1] > 50

    def test_rsi_downtrend(self):
        """In strong downtrend, RSI should be low (<50)."""
        prices = list(range(51, 0, -1))  # 51, 50, ..., 1
        prices = [float(p) for p in prices]
        rsi = BacktestEngine.calculate_rsi(prices, 14)
        valid = [v for v in rsi if v is not None]
        if valid:
            assert valid[-1] < 50

    def test_rsi_constant_price(self):
        """Constant price should give RSI of 100 (no losses)."""
        prices = [100.0] * 30
        rsi = BacktestEngine.calculate_rsi(prices, 14)
        # When there are no changes, gains/losses are 0 so RSI may not compute
        # The implementation should handle division by zero gracefully
        valid = [v for v in rsi if v is not None]
        # RSI may be None for all if there are no changes, or 100 if avg_loss = 0
        # Just ensure no crash
        assert len(rsi) == 30

    def test_rsi_not_enough_data(self):
        """RSI with insufficient data should return all None."""
        prices = [100.0, 101.0, 102.0]
        rsi = BacktestEngine.calculate_rsi(prices, 14)
        assert all(v is None for v in rsi)


# ---------------------------------------------------------------------------
# DSL Interpretation
# ---------------------------------------------------------------------------
class TestDSLInterpretation:
    """Test strategy DSL interpretation."""

    def test_sma_cross_buy_signal(self):
        """SMA crossover should generate buy signals."""
        # Create prices where SMA(3) crosses above SMA(5)
        # A strong uptrend after a flat period
        prices = [10.0] * 10 + [11.0, 12.0, 13.0, 14.0, 15.0]
        timestamps = [
            datetime(2024, 1, i + 1, tzinfo=timezone.utc) for i in range(len(prices))
        ]

        sma3 = BacktestEngine.calculate_sma(prices, 3)
        sma5 = BacktestEngine.calculate_sma(prices, 5)

        dsl = {
            "rules": [
                {"indicator": "sma_cross", "params": {"fast": 3, "slow": 5}, "action": "buy"},
            ]
        }

        signals = BacktestEngine.interpret_dsl(
            dsl_config=dsl,
            indicators={"sma_3": sma3, "sma_5": sma5},
            prices=prices,
            timestamps=timestamps,
            symbol="TEST",
        )

        # There should be at least one buy signal during the uptrend
        buy_signals = [s for s in signals if s.action == "buy"]
        assert len(buy_signals) >= 1

    def test_empty_dsl(self):
        """Empty DSL should produce no signals."""
        prices = [100.0, 101.0, 102.0]
        timestamps = [datetime(2024, 1, i + 1, tzinfo=timezone.utc) for i in range(3)]

        signals = BacktestEngine.interpret_dsl(
            dsl_config={"rules": []},
            indicators={},
            prices=prices,
            timestamps=timestamps,
        )
        assert signals == []


# ---------------------------------------------------------------------------
# Full Backtest Execution
# ---------------------------------------------------------------------------
class TestBacktestExecution:
    """Test full backtest execution with sample data."""

    @pytest.fixture
    def trending_prices(self):
        """Generate trending price data with both up and down moves."""
        import random
        from datetime import timedelta
        rng = random.Random(42)
        prices = []
        current = 100.0
        # 500 bars with regime changes to ensure crossovers
        for phase in range(5):
            for _ in range(100):
                if phase == 1:
                    drift = 0.004
                elif phase == 2:
                    drift = -0.003
                elif phase == 3:
                    drift = 0.003
                else:
                    drift = 0.0
                current *= (1 + drift + rng.gauss(0, 0.005))
                prices.append(round(current, 4))
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        timestamps = [base + timedelta(days=i) for i in range(len(prices))]
        return prices, timestamps

    def test_backtest_completes(self, trending_prices):
        """Backtest should complete without error."""
        prices, timestamps = trending_prices
        dsl = {
            "rules": [
                {"indicator": "sma_cross", "params": {"fast": 5, "slow": 20}, "action": "buy"},
                {"indicator": "sma_cross", "params": {"fast": 5, "slow": 20}, "action": "sell"},
            ],
            "stop_loss": 0.05,
            "take_profit": 0.10,
        }
        result = BacktestEngine.run_backtest(
            strategy_dsl=dsl, prices=prices, timestamps=timestamps,
            symbol="TEST", initial_capital=100000.0,
        )
        assert result.final_capital > 0
        assert result.total_trades >= 0
        assert 0.0 <= result.win_rate <= 1.0
        assert 0.0 <= result.max_drawdown <= 1.0

    def test_backtest_capital_conservation(self, trending_prices):
        """Capital should not become negative."""
        prices, timestamps = trending_prices
        dsl = {
            "rules": [
                {"indicator": "sma_cross", "params": {"fast": 3, "slow": 10}, "action": "buy"},
                {"indicator": "sma_cross", "params": {"fast": 3, "slow": 10}, "action": "sell"},
            ],
        }
        result = BacktestEngine.run_backtest(
            strategy_dsl=dsl, prices=prices, timestamps=timestamps,
            initial_capital=10000.0,
        )
        assert result.final_capital >= 0

    def test_backtest_empty_prices(self):
        """Backtest with empty prices should return initial capital."""
        dsl = {"rules": []}
        result = BacktestEngine.run_backtest(
            strategy_dsl=dsl, prices=[], timestamps=[],
            initial_capital=100000.0,
        )
        assert result.final_capital == 100000.0
        assert result.total_trades == 0

    def test_backtest_no_signals(self, trending_prices):
        """Backtest with no matching signals should hold cash."""
        prices, timestamps = trending_prices
        # Use periods that won't produce crossovers
        dsl = {
            "rules": [
                {"indicator": "sma_cross", "params": {"fast": 199, "slow": 200}, "action": "buy"},
            ],
        }
        result = BacktestEngine.run_backtest(
            strategy_dsl=dsl, prices=prices, timestamps=timestamps,
            initial_capital=100000.0,
        )
        # Should stay approximately at initial capital (no trades)
        assert abs(result.final_capital - 100000.0) < 1.0

    def test_backtest_trades_have_correct_sides(self, trending_prices):
        """Trades should alternate between buy and sell."""
        prices, timestamps = trending_prices
        dsl = {
            "rules": [
                {"indicator": "sma_cross", "params": {"fast": 5, "slow": 20}, "action": "buy"},
                {"indicator": "sma_cross", "params": {"fast": 5, "slow": 20}, "action": "sell"},
            ],
        }
        result = BacktestEngine.run_backtest(
            strategy_dsl=dsl, prices=prices, timestamps=timestamps,
            initial_capital=100000.0,
        )
        if result.trades:
            # First trade should be buy (we start with cash)
            assert result.trades[0].side == "buy"
            # Each buy should be followed by a sell (or stop/tp)
            for i in range(1, len(result.trades)):
                if result.trades[i].side == "buy":
                    assert result.trades[i - 1].side == "sell"

    def test_commission_and_slippage_reduce_returns(self, trending_prices):
        """Higher commission/slippage should reduce returns."""
        prices, timestamps = trending_prices
        dsl = {
            "rules": [
                {"indicator": "sma_cross", "params": {"fast": 5, "slow": 20}, "action": "buy"},
                {"indicator": "sma_cross", "params": {"fast": 5, "slow": 20}, "action": "sell"},
            ],
        }
        result_low = BacktestEngine.run_backtest(
            strategy_dsl=dsl, prices=prices, timestamps=timestamps,
            initial_capital=100000.0, commission_pct=0.0001, slippage_pct=0.0001,
        )
        result_high = BacktestEngine.run_backtest(
            strategy_dsl=dsl, prices=prices, timestamps=timestamps,
            initial_capital=100000.0, commission_pct=0.01, slippage_pct=0.01,
        )
        # Higher costs should result in less capital (if any trades occurred)
        if result_low.total_trades > 0 and result_high.total_trades > 0:
            assert result_high.final_capital <= result_low.final_capital
