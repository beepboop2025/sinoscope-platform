"""
DragonScope Risk Analytics Engine

Enterprise-grade real-time portfolio risk calculation system.
"""

__version__ = "2.0.0"
__author__ = "DragonScope Enterprise"

from .calculations import (
    PortfolioAnalytics,
    ValueAtRisk,
    GreeksCalculator,
    FactorExposure,
    StressTest,
    VaRMethod,
    VaRResult,
    GreeksResult,
    FactorExposureResult,
    StressTestResult
)

from .models import (
    Portfolio,
    Position,
    RiskReport,
    RiskMetrics,
    VaRRequest,
    StressTestRequest,
    Scenario,
    FactorModel,
    RiskFactor,
    CorrelationMatrix,
    AssetClass,
    VaRMethod as VaRMethodEnum
)

__all__ = [
    "PortfolioAnalytics",
    "ValueAtRisk",
    "GreeksCalculator",
    "FactorExposure",
    "StressTest",
    "VaRMethod",
    "VaRResult",
    "GreeksResult",
    "FactorExposureResult",
    "StressTestResult",
    "Portfolio",
    "Position",
    "RiskReport",
    "RiskMetrics",
    "VaRRequest",
    "StressTestRequest",
    "Scenario",
    "FactorModel",
    "RiskFactor",
    "CorrelationMatrix",
    "AssetClass",
    "VaRMethodEnum"
]
