"""
Performance Analytics - Comprehensive metrics calculation for backtest results.

Provides institutional-grade performance analytics including risk-adjusted returns,
drawdown analysis, trade statistics, and benchmark comparison.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore', category=RuntimeWarning)


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics container.
    
    Contains all standard risk and return metrics used in institutional
    performance reporting.
    """
    
    # Return Metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    cagr: float = 0.0
    
    # Risk Metrics
    volatility: float = 0.0
    downside_deviation: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    
    # Risk-Adjusted Performance
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    information_ratio: float = 0.0
    treynor_ratio: float = 0.0
    
    # Benchmark Comparison
    alpha: float = 0.0
    beta: float = 0.0
    tracking_error: float = 0.0
    
    # Additional Metrics
    skewness: float = 0.0
    kurtosis: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """Convert metrics to dictionary."""
        return {
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'cagr': self.cagr,
            'volatility': self.volatility,
            'downside_deviation': self.downside_deviation,
            'var_95': self.var_95,
            'var_99': self.var_99,
            'cvar_95': self.cvar_95,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'omega_ratio': self.omega_ratio,
            'information_ratio': self.information_ratio,
            'treynor_ratio': self.treynor_ratio,
            'alpha': self.alpha,
            'beta': self.beta,
            'tracking_error': self.tracking_error,
            'skewness': self.skewness,
            'kurtosis': self.kurtosis,
        }
    
    @classmethod
    def calculate(
        cls,
        equity_curve: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> PerformanceMetrics:
        """
        Calculate all performance metrics from equity curve.
        
        Args:
            equity_curve: DataFrame with 'equity' column
            benchmark_returns: Optional benchmark returns series
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year
            
        Returns:
            PerformanceMetrics object
        """
        if equity_curve.empty or 'equity' not in equity_curve.columns:
            return cls()
        
        metrics = cls()
        equity = equity_curve['equity']
        returns = equity_curve['returns'].dropna()
        
        if len(returns) < 2:
            return metrics
        
        # Period adjustment factor
        period_adj = np.sqrt(periods_per_year)
        
        # Return Metrics
        metrics.total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
        
        n_periods = len(returns)
        n_years = n_periods / periods_per_year
        
        if n_years > 0:
            metrics.cagr = (1 + metrics.total_return) ** (1 / n_years) - 1
            metrics.annualized_return = returns.mean() * periods_per_year
        
        # Risk Metrics
        metrics.volatility = returns.std() * period_adj
        
        # Downside deviation (semi-standard deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            metrics.downside_deviation = downside_returns.std() * period_adj
        
        # VaR and CVaR
        metrics.var_95 = np.percentile(returns, 5)
        metrics.var_99 = np.percentile(returns, 1)
        metrics.cvar_95 = returns[returns <= metrics.var_95].mean()
        
        # Risk-Adjusted Performance
        excess_returns = returns - risk_free_rate / periods_per_year
        
        if metrics.volatility > 0:
            metrics.sharpe_ratio = (excess_returns.mean() * periods_per_year) / metrics.volatility
        
        if metrics.downside_deviation > 0:
            metrics.sortino_ratio = (excess_returns.mean() * periods_per_year) / metrics.downside_deviation
        
        # Calculate drawdown for Calmar
        drawdown = DrawdownAnalyzer.calculate_drawdown_series(equity)
        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        if max_dd > 0:
            metrics.calmar_ratio = metrics.annualized_return / max_dd
        
        # Omega Ratio
        metrics.omega_ratio = cls._calculate_omega_ratio(returns, risk_free_rate / periods_per_year)
        
        # Distribution statistics
        metrics.skewness = returns.skew()
        metrics.kurtosis = returns.kurtosis()
        
        # Benchmark comparison
        if benchmark_returns is not None:
            metrics.beta, metrics.alpha, metrics.tracking_error = cls._calculate_beta_metrics(
                returns, benchmark_returns, risk_free_rate, periods_per_year
            )
            
            if metrics.tracking_error > 0:
                metrics.information_ratio = metrics.alpha / metrics.tracking_error
            
            if metrics.beta > 0:
                metrics.treynor_ratio = metrics.annualized_return / metrics.beta
        
        return metrics
    
    @staticmethod
    def _calculate_omega_ratio(
        returns: pd.Series,
        threshold: float = 0.0,
    ) -> float:
        """Calculate Omega ratio."""
        excess = returns - threshold
        gains = excess[excess > 0].sum()
        losses = abs(excess[excess < 0].sum())
        
        return gains / losses if losses > 0 else np.inf
    
    @staticmethod
    def _calculate_beta_metrics(
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
        risk_free_rate: float,
        periods_per_year: int,
    ) -> Tuple[float, float, float]:
        """Calculate beta, alpha, and tracking error."""
        # Align series
        aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
        if len(aligned) < 2:
            return 0.0, 0.0, 0.0
        
        s_rets = aligned.iloc[:, 0]
        b_rets = aligned.iloc[:, 1]
        
        # Beta
        covariance = s_rets.cov(b_rets)
        benchmark_var = b_rets.var()
        beta = covariance / benchmark_var if benchmark_var > 0 else 0.0
        
        # Alpha (annualized)
        alpha = (s_rets.mean() - risk_free_rate / periods_per_year - 
                beta * (b_rets.mean() - risk_free_rate / periods_per_year)) * periods_per_year
        
        # Tracking error (annualized)
        tracking_diff = s_rets - b_rets
        tracking_error = tracking_diff.std() * np.sqrt(periods_per_year)
        
        return beta, alpha, tracking_error


@dataclass
class TradeStatistics:
    """Trade-level performance statistics."""
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_trade_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    kelly_criterion: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_trade_duration: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    def to_dict(self) -> Dict[str, Union[int, float]]:
        """Convert statistics to dictionary."""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_trade_return': self.avg_trade_return,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'expectancy': self.expectancy,
            'kelly_criterion': self.kelly_criterion,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'avg_trade_duration': self.avg_trade_duration,
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
        }
    
    @classmethod
    def calculate(cls, fills: List) -> TradeStatistics:
        """
        Calculate trade statistics from fill history.
        
        Args:
            fills: List of Fill objects
            
        Returns:
            TradeStatistics object
        """
        stats = cls()
        
        if not fills:
            return stats
        
        # Group fills by trade (simplified - assumes fills alternate buy/sell)
        trades = cls._group_fills_into_trades(fills)
        
        if not trades:
            return stats
        
        stats.total_trades = len(trades)
        
        # Calculate P&L for each trade
        pnls = []
        durations = []
        consecutive_wins = 0
        consecutive_losses = 0
        max_wins = 0
        max_losses = 0
        
        for trade in trades:
            pnl = trade.get('pnl', 0)
            pnls.append(pnl)
            
            if 'duration' in trade:
                durations.append(trade['duration'])
            
            if pnl > 0:
                stats.winning_trades += 1
                stats.largest_win = max(stats.largest_win, pnl)
                consecutive_wins += 1
                consecutive_losses = 0
                max_wins = max(max_wins, consecutive_wins)
            elif pnl < 0:
                stats.losing_trades += 1
                stats.largest_loss = min(stats.largest_loss, pnl)
                consecutive_losses += 1
                consecutive_wins = 0
                max_losses = max(max_losses, consecutive_losses)
        
        stats.max_consecutive_wins = max_wins
        stats.max_consecutive_losses = max_losses
        
        if stats.total_trades > 0:
            stats.win_rate = stats.winning_trades / stats.total_trades
            stats.avg_trade_return = np.mean(pnls)
        
        # Calculate win/loss averages
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        if wins:
            stats.avg_win = np.mean(wins)
        if losses:
            stats.avg_loss = np.mean(losses)
        
        # Profit factor
        total_wins = sum(wins)
        total_losses = abs(sum(losses))
        stats.profit_factor = total_wins / total_losses if total_losses > 0 else np.inf
        
        # Expectancy
        stats.expectancy = (stats.win_rate * stats.avg_win + 
                          (1 - stats.win_rate) * stats.avg_loss)
        
        # Kelly Criterion
        if stats.avg_loss != 0:
            win_loss_ratio = abs(stats.avg_win / stats.avg_loss)
            stats.kelly_criterion = stats.win_rate - ((1 - stats.win_rate) / win_loss_ratio)
        
        if durations:
            stats.avg_trade_duration = np.mean(durations)
        
        return stats
    
    @staticmethod
    def _group_fills_into_trades(fills: List) -> List[Dict]:
        """Group fills into completed trades."""
        # Simplified trade grouping - assumes FIFO matching
        trades = []
        position = 0.0
        entry_value = 0.0
        entry_time = None
        
        for fill in fills:
            qty = fill.quantity if fill.side.name == 'BUY' else -fill.quantity
            fill_value = fill.quantity * fill.fill_price
            
            if position == 0:
                # Opening new position
                position = qty
                entry_value = fill_value
                entry_time = fill.timestamp
            elif (position > 0 and qty > 0) or (position < 0 and qty < 0):
                # Adding to position
                entry_value = (abs(position) * entry_value / abs(position) + fill_value)
                position += qty
            else:
                # Reducing/closing position
                exit_qty = min(abs(position), abs(qty))
                
                if position > 0:  # Long position
                    pnl = exit_qty * fill.fill_price - exit_qty * (entry_value / abs(position))
                else:  # Short position
                    pnl = exit_qty * (entry_value / abs(position)) - exit_qty * fill.fill_price
                
                duration = 0
                if entry_time:
                    from datetime import datetime
                    duration = (fill.timestamp.to_datetime() - entry_time.to_datetime()).total_seconds()
                
                trades.append({
                    'pnl': pnl - fill.commission,
                    'duration': duration,
                })
                
                position += qty
                if position == 0:
                    entry_value = 0
                    entry_time = None
        
        return trades


class DrawdownAnalyzer:
    """Analyze drawdown characteristics of an equity curve."""
    
    @staticmethod
    def calculate_drawdown_series(equity: pd.Series) -> pd.Series:
        """Calculate running drawdown series."""
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        return drawdown
    
    @classmethod
    def analyze(cls, equity: pd.Series) -> Dict:
        """
        Perform comprehensive drawdown analysis.
        
        Args:
            equity: Equity curve series
            
        Returns:
            Dictionary with drawdown statistics
        """
        drawdown = cls.calculate_drawdown_series(equity)
        
        # Find drawdown periods
        is_drawdown = drawdown < 0
        drawdown_periods = []
        
        in_drawdown = False
        start_idx = None
        
        for i, dd in enumerate(drawdown):
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                start_idx = i
            elif dd == 0 and in_drawdown:
                in_drawdown = False
                drawdown_periods.append((start_idx, i - 1))
        
        if in_drawdown:
            drawdown_periods.append((start_idx, len(drawdown) - 1))
        
        # Calculate statistics
        max_drawdown = abs(drawdown.min())
        
        drawdown_depths = []
        drawdown_durations = []
        
        for start, end in drawdown_periods:
            period_dd = drawdown.iloc[start:end+1]
            depth = abs(period_dd.min())
            duration = end - start + 1
            drawdown_depths.append(depth)
            drawdown_durations.append(duration)
        
        avg_drawdown = np.mean(drawdown_depths) if drawdown_depths else 0
        avg_duration = np.mean(drawdown_durations) if drawdown_durations else 0
        
        # Ulcer Index (square root of mean squared drawdown)
        ulcer_index = np.sqrt(np.mean(drawdown ** 2))
        
        # Calmar Ratio (if not already calculated)
        # Pain Ratio (return / ulcer index)
        total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
        pain_ratio = total_return / ulcer_index if ulcer_index > 0 else 0
        
        # Recovery analysis
        recovery_times = []
        for start, end in drawdown_periods:
            recovery_start = end
            # Find when equity recovered to previous high
            peak_before = equity.iloc[start]
            for i in range(end + 1, len(equity)):
                if equity.iloc[i] >= peak_before:
                    recovery_times.append(i - end)
                    break
        
        avg_recovery = np.mean(recovery_times) if recovery_times else 0
        
        return {
            'max_drawdown': max_drawdown,
            'avg_drawdown': avg_drawdown,
            'max_drawdown_duration': max(drawdown_durations) if drawdown_durations else 0,
            'avg_drawdown_duration': avg_duration,
            'ulcer_index': ulcer_index,
            'pain_ratio': pain_ratio,
            'avg_recovery_time': avg_recovery,
            'num_drawdowns': len(drawdown_periods),
            'drawdown_frequency': len(drawdown_periods) / len(equity) if len(equity) > 0 else 0,
        }
    
    @classmethod
    def plot_drawdown(cls, equity: pd.Series, figsize: Tuple[int, int] = (12, 8)):
        """
        Generate drawdown plot (returns matplotlib figure).
        
        Note: Requires matplotlib to be installed.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("matplotlib is required for plotting")
        
        drawdown = cls.calculate_drawdown_series(equity)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, 
                                        gridspec_kw={'height_ratios': [3, 1]})
        
        # Equity curve
        ax1.plot(equity.index, equity.values, label='Equity', color='blue')
        ax1.set_ylabel('Equity ($)')
        ax1.set_title('Equity Curve and Drawdown')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Drawdown
        ax2.fill_between(drawdown.index, drawdown.values, 0, 
                         color='red', alpha=0.3, label='Drawdown')
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_xlabel('Date')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig


class AttributionAnalyzer:
    """Performance attribution analysis."""
    
    @staticmethod
    def factor_attribution(
        returns: pd.Series,
        factors: pd.DataFrame,
    ) -> Dict:
        """
        Perform factor attribution analysis.
        
        Args:
            returns: Strategy returns series
            factors: DataFrame of factor returns (e.g., Fama-French)
            
        Returns:
            Dictionary with attribution results
        """
        # Align data
        data = pd.concat([returns, factors], axis=1).dropna()
        y = data.iloc[:, 0]
        X = data.iloc[:, 1:]
        X = sm.add_constant(X) if 'const' not in X.columns else X
        
        # OLS regression
        try:
            import statsmodels.api as sm
            model = sm.OLS(y, X).fit()
            
            attribution = {
                'r_squared': model.rsquared,
                'adj_r_squared': model.rsquared_adj,
                'alpha': model.params.get('const', 0),
                'factor_exposures': model.params.drop('const', errors='ignore').to_dict(),
                't_stats': model.tvalues.drop('const', errors='ignore').to_dict(),
                'p_values': model.pvalues.drop('const', errors='ignore').to_dict(),
            }
            
            # Calculate contribution of each factor
            factor_contrib = {}
            for factor in factors.columns:
                if factor in model.params:
                    factor_contrib[factor] = model.params[factor] * factors[factor].mean()
            
            attribution['factor_contributions'] = factor_contrib
            
        except ImportError:
            # Simple numpy regression fallback
            X_np = np.column_stack([np.ones(len(X)), X.values])
            coeffs = np.linalg.lstsq(X_np, y.values, rcond=None)[0]
            
            attribution = {
                'alpha': coeffs[0],
                'factor_exposures': dict(zip(factors.columns, coeffs[1:])),
            }
        
        return attribution
    
    @staticmethod
    def sector_attribution(
        returns: pd.Series,
        sector_returns: pd.DataFrame,
        sector_weights: pd.Series,
    ) -> Dict:
        """
        Perform sector attribution analysis.
        
        Args:
            returns: Portfolio returns
            sector_returns: Sector index returns
            sector_weights: Portfolio sector weights
            
        Returns:
            Attribution breakdown by sector
        """
        # Allocation effect
        benchmark_weights = pd.Series(1/len(sector_weights), index=sector_weights.index)
        allocation_effect = (sector_weights - benchmark_weights) * sector_returns.mean()
        
        # Selection effect
        selection_effect = benchmark_weights * (sector_returns.mean() - sector_returns.mean().mean())
        
        # Interaction effect
        interaction = (sector_weights - benchmark_weights) * (
            sector_returns.mean() - sector_returns.mean().mean()
        )
        
        return {
            'allocation_effect': allocation_effect.to_dict(),
            'selection_effect': selection_effect.to_dict(),
            'interaction_effect': interaction.to_dict(),
            'total_attribution': (allocation_effect + selection_effect + interaction).to_dict(),
        }
    
    @staticmethod
    def time_attribution(
        returns: pd.Series,
        periods: str = 'M',
    ) -> pd.DataFrame:
        """
        Analyze performance attribution by time period.
        
        Args:
            returns: Returns series
            periods: Resampling period ('D', 'W', 'M', 'Q', 'Y')
            
        Returns:
            DataFrame with period-wise attribution
        """
        # Resample returns
        period_returns = returns.resample(periods).apply(lambda x: (1 + x).prod() - 1)
        
        attribution = pd.DataFrame({
            'return': period_returns,
            'cumulative': (1 + period_returns).cumprod() - 1,
            'contribution': period_returns / period_returns.sum() if period_returns.sum() != 0 else 0,
        })
        
        return attribution


class RollingAnalytics:
    """Rolling window performance analytics."""
    
    @staticmethod
    def rolling_metrics(
        returns: pd.Series,
        window: int = 63,  # ~3 months
        risk_free_rate: float = 0.02,
    ) -> pd.DataFrame:
        """
        Calculate rolling performance metrics.
        
        Args:
            returns: Returns series
            window: Rolling window size
            risk_free_rate: Annual risk-free rate
            
        Returns:
            DataFrame with rolling metrics
        """
        periods_per_year = 252
        
        rolling_metrics = pd.DataFrame({
            'return': returns.rolling(window).mean() * periods_per_year,
            'volatility': returns.rolling(window).std() * np.sqrt(periods_per_year),
        })
        
        # Rolling Sharpe
        excess_return = returns - risk_free_rate / periods_per_year
        rolling_metrics['sharpe'] = (
            excess_return.rolling(window).mean() * periods_per_year /
            rolling_metrics['volatility'].replace(0, np.nan)
        )
        
        # Rolling Sortino
        downside = returns.where(returns < 0, 0)
        downside_std = downside.rolling(window).std() * np.sqrt(periods_per_year)
        rolling_metrics['sortino'] = (
            excess_return.rolling(window).mean() * periods_per_year /
            downside_std.replace(0, np.nan)
        )
        
        # Rolling win rate
        rolling_metrics['win_rate'] = (returns > 0).rolling(window).mean()
        
        return rolling_metrics
    
    @staticmethod
    def regime_analysis(
        returns: pd.Series,
        volatility_threshold: float = 0.02,
    ) -> Dict:
        """
        Analyze performance across market regimes.
        
        Args:
            returns: Returns series
            volatility_threshold: Threshold for high/low volatility classification
            
        Returns:
            Dictionary with regime-specific metrics
        """
        # Calculate rolling volatility
        rolling_vol = returns.rolling(21).std()
        
        # Classify regimes
        high_vol = rolling_vol > volatility_threshold
        low_vol = rolling_vol <= volatility_threshold
        
        regimes = {
            'high_volatility': {
                'mean_return': returns[high_vol].mean(),
                'volatility': returns[high_vol].std(),
                'sharpe': returns[high_vol].mean() / returns[high_vol].std() if returns[high_vol].std() > 0 else 0,
                'periods': high_vol.sum(),
            },
            'low_volatility': {
                'mean_return': returns[low_vol].mean(),
                'volatility': returns[low_vol].std(),
                'sharpe': returns[low_vol].mean() / returns[low_vol].std() if returns[low_vol].std() > 0 else 0,
                'periods': low_vol.sum(),
            },
        }
        
        return regimes
