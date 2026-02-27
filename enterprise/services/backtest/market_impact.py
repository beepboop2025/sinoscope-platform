"""
Market Impact Models - Price impact estimation for large orders.

Implements various market impact models used in institutional trading,
including the Almgren square root law and custom linear models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Tuple

import numpy as np


class OrderSide(Enum):
    BUY = 1
    SELL = -1


@dataclass
class ImpactComponents:
    """Decomposed market impact into permanent and temporary components."""
    total_impact_bps: float
    permanent_impact_bps: float
    temporary_impact_bps: float
    decay_factor: float  # How quickly temporary impact fades


class MarketImpactModel(ABC):
    """
    Abstract base class for market impact models.
    
    Market impact models estimate how much an order moves the market price
    based on order size, liquidity, and other market conditions.
    """
    
    def __init__(self, sigma: float = 0.02, daily_volume: float = 1e6):
        """
        Initialize market impact model.
        
        Args:
            sigma: Daily volatility (standard deviation of returns)
            daily_volume: Average daily trading volume in shares
        """
        self.sigma = sigma
        self.daily_volume = daily_volume
    
    @abstractmethod
    def calculate_impact(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> float:
        """
        Calculate price impact in basis points.
        
        Args:
            quantity: Order size in shares/contracts
            side: BUY or SELL
            **kwargs: Additional model-specific parameters
            
        Returns:
            Price impact in basis points (positive = adverse movement)
        """
        pass
    
    @abstractmethod
    def calculate_components(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> ImpactComponents:
        """
        Calculate decomposed impact (permanent vs temporary).
        
        Args:
            quantity: Order size in shares/contracts
            side: BUY or SELL
            **kwargs: Additional model-specific parameters
            
        Returns:
            ImpactComponents with decomposed impact values
        """
        pass
    
    def _validate_quantity(self, quantity: float) -> float:
        """Validate and normalize quantity."""
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")
        return float(quantity)


class LinearImpactModel(MarketImpactModel):
    """
    Linear market impact model.
    
    Simple model where impact is proportional to order size relative to
    average daily volume. Suitable for small orders or as a baseline.
    
    Impact = eta * (Q / ADV) ^ gamma
    
    where gamma = 1.0 for linear relationship.
    """
    
    def __init__(
        self,
        eta: float = 1.0,
        gamma: float = 1.0,
        sigma: float = 0.02,
        daily_volume: float = 1e6,
    ):
        """
        Initialize linear impact model.
        
        Args:
            eta: Impact coefficient (higher = more impact)
            gamma: Exponent for non-linearity (1.0 = linear)
            sigma: Daily volatility
            daily_volume: Average daily volume
        """
        super().__init__(sigma, daily_volume)
        self.eta = eta
        self.gamma = gamma
    
    def calculate_impact(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> float:
        """Calculate linear impact in basis points."""
        quantity = self._validate_quantity(quantity)
        
        if quantity == 0 or self.daily_volume == 0:
            return 0.0
        
        # Participation rate
        participation = quantity / self.daily_volume
        
        # Impact calculation
        impact = self.eta * self.sigma * np.sqrt(252) * (participation ** self.gamma)
        
        # Convert to basis points
        impact_bps = impact * 10_000
        
        # Impact is always adverse to the trader
        return abs(impact_bps)
    
    def calculate_components(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> ImpactComponents:
        """Calculate decomposed impact components."""
        total_impact = self.calculate_impact(quantity, side, **kwargs)
        
        # For linear model, assume 30% permanent, 70% temporary
        permanent = total_impact * 0.3
        temporary = total_impact * 0.7
        
        return ImpactComponents(
            total_impact_bps=total_impact,
            permanent_impact_bps=permanent,
            temporary_impact_bps=temporary,
            decay_factor=0.5,  # 50% decay per day
        )


class SquareRootImpactModel(MarketImpactModel):
    """
    Square Root Impact Model (Almgren et al. 2005).
    
    Industry-standard model based on the square root law:
    Impact scales with the square root of order size relative to volume.
    
    I = eta * sigma * sqrt(Q / ADV)
    
    where:
    - I is the price impact
    - eta is the impact coefficient (~0.5-1.5)
    - sigma is daily volatility
    - Q is order quantity
    - ADV is average daily volume
    
    Reference: Almgren, R., Thum, C., Hauptmann, E., & Li, H. (2005).
    "Direct estimation of equity market impact." Risk, 18(7), 58-62.
    """
    
    def __init__(
        self,
        eta: float = 0.5,
        gamma: float = 0.6,
        beta: float = 0.5,
        sigma: float = 0.02,
        daily_volume: float = 1e6,
        permanent_fraction: float = 0.2,
    ):
        """
        Initialize square root impact model.
        
        Args:
            eta: Temporary impact coefficient (~0.5-1.0)
            gamma: Permanent impact coefficient (~0.5-1.0)
            beta: Decay parameter for temporary impact
            sigma: Daily volatility
            daily_volume: Average daily volume
            permanent_fraction: Fraction of impact that is permanent
        """
        super().__init__(sigma, daily_volume)
        self.eta = eta
        self.gamma = gamma
        self.beta = beta
        self.permanent_fraction = permanent_fraction
    
    def calculate_impact(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> float:
        """Calculate square root impact in basis points."""
        quantity = self._validate_quantity(quantity)
        
        if quantity == 0 or self.daily_volume == 0:
            return 0.0
        
        # Normalized order size
        x = quantity / self.daily_volume
        
        # Square root impact formula
        impact = self.eta * self.sigma * np.sqrt(252) * np.sqrt(x)
        
        # Convert to basis points
        impact_bps = impact * 10_000
        
        return abs(impact_bps)
    
    def calculate_components(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> ImpactComponents:
        """Calculate permanent and temporary impact components."""
        total_impact = self.calculate_impact(quantity, side, **kwargs)
        
        quantity = self._validate_quantity(quantity)
        x = quantity / self.daily_volume if self.daily_volume > 0 else 0
        
        # Permanent impact (linear in order size)
        permanent = self.gamma * self.sigma * np.sqrt(252) * x * 10_000
        
        # Temporary impact (square root component)
        temporary = total_impact - permanent
        temporary = max(temporary, 0)  # Ensure non-negative
        
        return ImpactComponents(
            total_impact_bps=total_impact,
            permanent_impact_bps=permanent,
            temporary_impact_bps=temporary,
            decay_factor=np.exp(-self.beta),  # Exponential decay
        )
    
    def estimate_execution_cost(
        self,
        quantity: float,
        execution_time_hours: float = 1.0,
        market_hours_per_day: float = 6.5,
    ) -> Tuple[float, float]:
        """
        Estimate total execution cost including time-based decay.
        
        Args:
            quantity: Order quantity
            execution_time_hours: Time to complete execution
            market_hours_per_day: Trading hours per day
            
        Returns:
            Tuple of (total_cost_bps, realized_impact_bps)
        """
        impact = self.calculate_components(quantity, OrderSide.BUY)
        
        # Convert execution time to fraction of a day
        execution_days = execution_time_hours / market_hours_per_day
        
        # Temporary impact decays over execution period
        decay = np.exp(-self.beta * execution_days)
        remaining_temporary = impact.temporary_impact_bps * decay
        
        # Total realized cost
        realized_cost = impact.permanent_impact_bps + remaining_temporary
        
        return impact.total_impact_bps, realized_cost


class PowerLawImpactModel(MarketImpactModel):
    """
    General Power Law Impact Model.
    
    More flexible than square root, allows fitting to empirical data:
    I = eta * sigma * (Q / ADV) ^ delta
    
    where delta is typically between 0.4 and 0.7.
    """
    
    def __init__(
        self,
        eta: float = 1.0,
        delta: float = 0.5,
        sigma: float = 0.02,
        daily_volume: float = 1e6,
    ):
        """
        Initialize power law impact model.
        
        Args:
            eta: Impact coefficient
            delta: Power law exponent (~0.5 for square root)
            sigma: Daily volatility
            daily_volume: Average daily volume
        """
        super().__init__(sigma, daily_volume)
        self.eta = eta
        self.delta = delta
    
    def calculate_impact(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> float:
        """Calculate power law impact in basis points."""
        quantity = self._validate_quantity(quantity)
        
        if quantity == 0 or self.daily_volume == 0:
            return 0.0
        
        x = quantity / self.daily_volume
        impact = self.eta * self.sigma * np.sqrt(252) * (x ** self.delta)
        
        return abs(impact * 10_000)
    
    def calculate_components(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> ImpactComponents:
        """Calculate impact components."""
        total = self.calculate_impact(quantity, side, **kwargs)
        
        # Assume 25% permanent for power law
        permanent = total * 0.25
        temporary = total * 0.75
        
        return ImpactComponents(
            total_impact_bps=total,
            permanent_impact_bps=permanent,
            temporary_impact_bps=temporary,
            decay_factor=0.6,
        )


class KyleLambdaImpactModel(MarketImpactModel):
    """
    Kyle's Lambda Impact Model.
    
    Based on Kyle (1985) model of informed trading:
    Price impact per unit of order flow (Kyle's lambda).
    
    Suitable for high-frequency and microstructure analysis.
    
    Reference: Kyle, A. S. (1985). "Continuous auctions and insider trading."
    Econometrica, 53(6), 1315-1335.
    """
    
    def __init__(
        self,
        lambda_kyle: float = 0.001,
        sigma: float = 0.02,
        daily_volume: float = 1e6,
    ):
        """
        Initialize Kyle's lambda model.
        
        Args:
            lambda_kyle: Kyle's lambda (price impact per unit volume)
            sigma: Daily volatility
            daily_volume: Average daily volume
        """
        super().__init__(sigma, daily_volume)
        self.lambda_kyle = lambda_kyle
    
    def calculate_impact(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> float:
        """Calculate Kyle's lambda impact in basis points."""
        quantity = self._validate_quantity(quantity)
        
        # Impact is linear in order size
        price_change = self.lambda_kyle * quantity
        
        # Convert to basis points (assuming reference price)
        reference_price = kwargs.get('reference_price', 100.0)
        impact_bps = (price_change / reference_price) * 10_000
        
        return abs(impact_bps)
    
    def calculate_components(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> ImpactComponents:
        """Calculate impact components."""
        total = self.calculate_impact(quantity, side, **kwargs)
        
        # Kyle's model implies mostly permanent impact
        return ImpactComponents(
            total_impact_bps=total,
            permanent_impact_bps=total * 0.8,
            temporary_impact_bps=total * 0.2,
            decay_factor=0.3,
        )


class VolumeParticipationModel:
    """
    Volume Participation Impact Model.
    
    Models impact based on participation rate in available liquidity.
    Useful for VWAP and POV (Percent of Volume) execution strategies.
    """
    
    def __init__(
        self,
        impact_model: MarketImpactModel,
        max_participation_rate: float = 0.1,
        min_liquidity_window: int = 5,
    ):
        """
        Initialize volume participation model.
        
        Args:
            impact_model: Base impact model to use
            max_participation_rate: Maximum participation in volume
            min_liquidity_window: Minimum bars to distribute execution
        """
        self.impact_model = impact_model
        self.max_participation_rate = max_participation_rate
        self.min_liquidity_window = min_liquidity_window
    
    def calculate_optimal_schedule(
        self,
        total_quantity: float,
        volume_profile: np.ndarray,
    ) -> np.ndarray:
        """
        Calculate optimal execution schedule to minimize impact.
        
        Args:
            total_quantity: Total order quantity
            volume_profile: Expected volume per time bucket
            
        Returns:
            Array of quantities to execute per bucket
        """
        n_buckets = len(volume_profile)
        schedule = np.zeros(n_buckets)
        remaining = total_quantity
        
        for i in range(n_buckets):
            if remaining <= 0:
                break
            
            max_in_bucket = volume_profile[i] * self.max_participation_rate
            schedule[i] = min(remaining, max_in_bucket)
            remaining -= schedule[i]
        
        # If still remaining, distribute evenly
        if remaining > 0:
            per_bucket = remaining / n_buckets
            schedule += per_bucket
        
        return schedule
    
    def estimate_schedule_impact(
        self,
        schedule: np.ndarray,
        volume_profile: np.ndarray,
    ) -> float:
        """
        Estimate total impact for an execution schedule.
        
        Args:
            schedule: Execution quantities per bucket
            volume_profile: Volume per bucket
            
        Returns:
            Average impact in basis points
        """
        impacts = []
        
        for qty, vol in zip(schedule, volume_profile):
            if qty > 0 and vol > 0:
                # Temporarily set daily volume for impact calc
                original_adv = self.impact_model.daily_volume
                self.impact_model.daily_volume = vol * len(volume_profile)
                
                impact = self.impact_model.calculate_impact(qty, OrderSide.BUY)
                impacts.append(impact)
                
                self.impact_model.daily_volume = original_adv
        
        return np.mean(impacts) if impacts else 0.0


class AdaptiveImpactModel(MarketImpactModel):
    """
    Adaptive Impact Model that adjusts based on market conditions.
    
    Combines multiple models and adjusts coefficients based on:
    - Current volatility regime
    - Liquidity conditions
    - Time of day
    """
    
    def __init__(
        self,
        base_model: Optional[MarketImpactModel] = None,
        volatility_regime_adjustment: bool = True,
        time_of_day_adjustment: bool = True,
    ):
        """
        Initialize adaptive impact model.
        
        Args:
            base_model: Base impact model to adapt
            volatility_regime_adjustment: Adjust for vol regime
            time_of_day_adjustment: Adjust for intraday patterns
        """
        super().__init__()
        self.base_model = base_model or SquareRootImpactModel()
        self.volatility_regime_adjustment = volatility_regime_adjustment
        self.time_of_day_adjustment = time_of_day_adjustment
        
        # Regime multipliers
        self.regime_multipliers = {
            "low_vol": 0.7,
            "normal": 1.0,
            "high_vol": 1.5,
            "extreme": 2.5,
        }
        
        # Time of day multipliers (simplified)
        self.time_multipliers = {
            "open": 1.3,      # Higher impact at open
            "midday": 0.9,    # Lower impact midday
            "close": 1.2,     # Higher impact at close
        }
    
    def set_market_conditions(
        self,
        current_volatility: Optional[float] = None,
        time_of_day: Optional[str] = None,
        liquidity_score: Optional[float] = None,
    ) -> None:
        """Update current market conditions for adjustments."""
        self.current_volatility = current_volatility
        self.current_time_of_day = time_of_day
        self.liquidity_score = liquidity_score
    
    def calculate_impact(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> float:
        """Calculate adaptive impact with condition adjustments."""
        base_impact = self.base_model.calculate_impact(quantity, side, **kwargs)
        
        # Apply volatility regime adjustment
        if self.volatility_regime_adjustment and hasattr(self, 'current_volatility'):
            regime = self._classify_volatility_regime(self.current_volatility)
            base_impact *= self.regime_multipliers.get(regime, 1.0)
        
        # Apply time of day adjustment
        if self.time_of_day_adjustment and hasattr(self, 'current_time_of_day'):
            base_impact *= self.time_multipliers.get(self.current_time_of_day, 1.0)
        
        # Apply liquidity adjustment
        if hasattr(self, 'liquidity_score') and self.liquidity_score is not None:
            # Lower liquidity = higher impact
            liquidity_factor = 1.0 / max(self.liquidity_score, 0.1)
            base_impact *= liquidity_factor
        
        return base_impact
    
    def calculate_components(
        self,
        quantity: float,
        side: OrderSide,
        **kwargs,
    ) -> ImpactComponents:
        """Calculate impact components."""
        return self.base_model.calculate_components(quantity, side, **kwargs)
    
    def _classify_volatility_regime(self, current_vol: float) -> str:
        """Classify current volatility regime."""
        if current_vol < self.sigma * 0.5:
            return "low_vol"
        elif current_vol < self.sigma * 1.5:
            return "normal"
        elif current_vol < self.sigma * 3.0:
            return "high_vol"
        else:
            return "extreme"


def calibrate_impact_model(
    trades: np.ndarray,
    impacts: np.ndarray,
    volumes: np.ndarray,
    model_type: str = "square_root",
) -> MarketImpactModel:
    """
    Calibrate impact model parameters from historical data.
    
    Args:
        trades: Array of trade sizes
        impacts: Array of observed price impacts (bps)
        volumes: Array of corresponding market volumes
        model_type: Type of model to calibrate
        
    Returns:
        Calibrated impact model
    """
    if model_type == "square_root":
        # Fit eta parameter
        x = trades / volumes
        y = impacts / 10_000  # Convert from bps
        
        # Linear regression on log scale
        log_x = np.log(np.sqrt(x))
        log_y = np.log(y)
        
        # Simple OLS
        eta = np.exp(np.mean(log_y - log_x))
        
        return SquareRootImpactModel(eta=eta)
    
    elif model_type == "linear":
        x = trades / volumes
        y = impacts / 10_000
        
        eta = np.mean(y / x)
        
        return LinearImpactModel(eta=eta)
    
    elif model_type == "power_law":
        x = trades / volumes
        y = impacts / 10_000
        
        # Fit power law: log(y) = log(eta) + delta * log(x)
        log_x = np.log(x)
        log_y = np.log(y)
        
        delta = np.cov(log_x, log_y)[0, 1] / np.var(log_x)
        eta = np.exp(np.mean(log_y) - delta * np.mean(log_x))
        
        return PowerLawImpactModel(eta=eta, delta=delta)
    
    else:
        raise ValueError(f"Unknown model type: {model_type}")
