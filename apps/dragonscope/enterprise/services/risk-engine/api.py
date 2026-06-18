"""
DragonScope Risk Analytics Engine - FastAPI Endpoints

High-performance REST API for real-time portfolio risk calculations.
Optimized for sub-second response times with Redis caching.
"""

import os
import time
import json
import hashlib
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from functools import wraps

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import local modules
from models import (
    Portfolio, Position, RiskReport, RiskMetrics, VaRResult, VaRRequest,
    StressTestRequest, StressTestResult, Scenario, ScenarioCreateRequest,
    ScenarioResult, FactorModel, RiskFactor, FactorModelRequest,
    FactorExposureResult, FactorExposure, CorrelationMatrix,
    CacheKey, CachedResult, AssetClass, VaRMethod, FactorType
)
from calculations import (
    PortfolioAnalytics, ValueAtRisk, GreeksCalculator,
    FactorExposure, StressTest, VaRMethod as CalcVaRMethod
)

# Redis caching (optional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="DragonScope Risk Analytics Engine",
    description="Enterprise-grade real-time portfolio risk calculation system",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Redis Cache Setup
# ============================================================================

class CacheManager:
    """Manages Redis caching for risk calculations."""
    
    def __init__(self):
        self.redis_client = None
        self.local_cache = {}
        self.enabled = False
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=int(os.getenv("REDIS_DB", 0)),
                    password=os.getenv("REDIS_PASSWORD") or None,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                self.redis_client.ping()
                self.enabled = True
            except (redis.ConnectionError, Exception):
                print("Redis not available, using in-memory cache")
    
    def get(self, key: str) -> Optional[Dict]:
        """Get value from cache."""
        if not self.enabled:
            return self.local_cache.get(key)
        
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception:
            return self.local_cache.get(key)
        return None
    
    def set(self, key: str, value: Dict, ttl_seconds: int = 300) -> bool:
        """Set value in cache with TTL."""
        try:
            serialized = json.dumps(value, default=str)
            if not self.enabled:
                self.local_cache[key] = value
                return True
            self.redis_client.setex(key, ttl_seconds, serialized)
            return True
        except Exception:
            self.local_cache[key] = value
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.enabled:
            self.local_cache.pop(key, None)
            return True
        try:
            self.redis_client.delete(key)
            return True
        except Exception:
            return False
    
    def generate_key(self, calculation_type: str, portfolio_id: str, params: Dict) -> str:
        """Generate cache key from parameters."""
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return f"risk:{calculation_type}:{portfolio_id}:{date_str}:{params_hash}"

# Global cache manager
cache = CacheManager()

# ============================================================================
# In-Memory Data Stores (Replace with database in production)
# ============================================================================

portfolios_db: Dict[str, Portfolio] = {}
scenarios_db: Dict[str, Scenario] = {s.scenario_id: s for s in create_default_scenarios()}
factor_models_db: Dict[str, FactorModel] = {
    "fama_french_5f": create_fama_french_factors(),
    "macro_factors": create_macro_factor_model()
}
historical_returns_db: Dict[str, pd.DataFrame] = {}

# ============================================================================
# Dependency Injection
# ============================================================================

def get_analytics() -> PortfolioAnalytics:
    return PortfolioAnalytics()

def get_cache() -> CacheManager:
    return cache

# ============================================================================
# Helper Functions
# ============================================================================

def generate_sample_portfolio(portfolio_id: str, n_positions: int = 100) -> Portfolio:
    """Generate a sample portfolio for testing."""
    np.random.seed(42)
    positions = []
    asset_classes = list(AssetClass)
    
    for i in range(n_positions):
        asset_class = np.random.choice(asset_classes[:-2])
        pos = Position(
            position_id=f"pos_{i}",
            asset_id=f"asset_{i}",
            asset_name=f"Asset {i}",
            asset_class=asset_class,
            quantity=np.random.randint(10, 1000),
            price=np.random.uniform(10, 500),
            volatility=np.random.uniform(0.1, 0.4),
            expected_return=np.random.uniform(-0.05, 0.15)
        )
        positions.append(pos)
    
    return Portfolio(
        portfolio_id=portfolio_id,
        name=f"Sample Portfolio {portfolio_id}",
        positions=positions
    )

def generate_sample_returns(assets: List[str], n_days: int = 252) -> pd.DataFrame:
    """Generate sample historical returns."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.utcnow(), periods=n_days, freq='B')
    n_assets = len(assets)
    mean = np.random.uniform(-0.001, 0.001, n_assets)
    std = np.random.uniform(0.01, 0.03, n_assets)
    corr = np.eye(n_assets) * 0.7 + 0.3
    np.fill_diagonal(corr, 1.0)
    cov = np.outer(std, std) * corr
    returns = np.random.multivariate_normal(mean, cov, n_days)
    return pd.DataFrame(returns, index=dates, columns=assets)

# ============================================================================
# Request/Response Models
# ============================================================================

class PortfolioCreateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    name: str
    base_currency: str = "USD"
    positions: List[Position] = []

class VaRResponse(BaseModel):
    portfolio_id: str
    var_result: VaRResult
    cached: bool = False
    metadata: Dict[str, Any] = {}

class StressTestResponse(BaseModel):
    portfolio_id: str
    stress_result: Dict[str, Any]
    cached: bool = False
    metadata: Dict[str, Any] = {}

class GreeksRequest(BaseModel):
    option_type: str
    spot: float = Field(..., gt=0)
    strike: float = Field(..., gt=0)
    time_to_expiry: float = Field(..., gt=0)
    risk_free_rate: float = 0.05
    volatility: float = Field(..., gt=0, le=5)
    dividend_yield: float = 0.0

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "DragonScope Risk Analytics Engine",
        "version": "2.0.0",
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "var": "/risk/portfolio/{id}/var",
            "stress_test": "/risk/portfolio/{id}/stress-test",
            "factors": "/risk/factors",
            "scenarios": "/risk/scenarios"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "cache_enabled": cache.enabled,
        "redis_available": REDIS_AVAILABLE and cache.enabled
    }

# -----------------------------------------------------------------------------
# VaR Endpoints
# -----------------------------------------------------------------------------

@app.post("/risk/portfolio/{portfolio_id}/var", response_model=VaRResponse)
async def calculate_var(
    portfolio_id: str,
    request: VaRRequest,
    background_tasks: BackgroundTasks,
    analytics: PortfolioAnalytics = Depends(get_analytics),
    cache_mgr: CacheManager = Depends(get_cache)
):
    """Calculate Value at Risk for a portfolio."""
    start_time = time.time()
    
    # Check cache
    cache_params = {
        "method": request.method.value,
        "confidence": request.confidence_level,
        "horizon": request.time_horizon,
        "simulations": request.n_simulations
    }
    cache_key = cache_mgr.generate_key("var", portfolio_id, cache_params)
    
    if request.use_cache:
        cached = cache_mgr.get(cache_key)
        if cached:
            return VaRResponse(
                portfolio_id=portfolio_id,
                var_result=VaRResult(**cached["var_result"]),
                cached=True,
                metadata={"timestamp": datetime.utcnow().isoformat()}
            )
    
    # Get portfolio
    if portfolio_id not in portfolios_db:
        portfolios_db[portfolio_id] = generate_sample_portfolio(portfolio_id)
    
    portfolio = portfolios_db[portfolio_id]
    positions_dict = portfolio.to_positions_dict()
    
    # Get historical data
    asset_ids = [pos.asset_id for pos in portfolio.positions]
    if portfolio_id not in historical_returns_db:
        historical_returns_db[portfolio_id] = generate_sample_returns(asset_ids)
    historical_data = historical_returns_db[portfolio_id]
    
    # Map method
    method_map = {
        VaRMethod.PARAMETRIC: CalcVaRMethod.PARAMETRIC,
        VaRMethod.HISTORICAL: CalcVaRMethod.HISTORICAL,
        VaRMethod.MONTE_CARLO: CalcVaRMethod.MONTE_CARLO
    }
    calc_method = method_map.get(request.method, CalcVaRMethod.MONTE_CARLO)
    
    # Calculate VaR
    var_result = analytics.calculate_var(
        positions=positions_dict,
        method=calc_method,
        confidence_level=request.confidence_level,
        time_horizon=request.time_horizon,
        n_simulations=request.n_simulations,
        historical_data=historical_data
    )
    
    calculation_time = (time.time() - start_time) * 1000
    
    response = VaRResponse(
        portfolio_id=portfolio_id,
        var_result=VaRResult(
            var_95=var_result.var_95,
            var_99=var_result.var_99,
            cvar_95=var_result.cvar_95,
            cvar_99=var_result.cvar_99,
            method=request.method,
            confidence_level=request.confidence_level,
            time_horizon=request.time_horizon,
            n_simulations=var_result.n_simulations,
            calculation_time_ms=calculation_time
        ),
        cached=False,
        metadata={
            "calculation_time_ms": round(calculation_time, 2),
            "portfolio_value": portfolio.total_value,
            "n_positions": len(portfolio.positions)
        }
    )
    
    # Cache result
    if request.use_cache:
        cache_data = {"var_result": response.var_result.dict(), "portfolio_value": portfolio.total_value}
        background_tasks.add_task(cache_mgr.set, cache_key, cache_data, ttl_seconds=300)
    
    return response

# -----------------------------------------------------------------------------
# Stress Test Endpoints
# -----------------------------------------------------------------------------

@app.post("/risk/portfolio/{portfolio_id}/stress-test", response_model=StressTestResponse)
async def run_stress_test(
    portfolio_id: str,
    request: StressTestRequest,
    background_tasks: BackgroundTasks,
    analytics: PortfolioAnalytics = Depends(get_analytics),
    cache_mgr: CacheManager = Depends(get_cache)
):
    """Run stress test on a portfolio."""
    start_time = time.time()
    
    if portfolio_id not in portfolios_db:
        portfolios_db[portfolio_id] = generate_sample_portfolio(portfolio_id)
    
    portfolio = portfolios_db[portfolio_id]
    positions_dict = portfolio.to_positions_dict()
    current_prices = {pos.asset_id: pos.price for pos in portfolio.positions}
    
    # Determine scenario
    if request.scenario_id:
        if request.scenario_id not in scenarios_db:
            raise HTTPException(status_code=404, detail=f"Scenario {request.scenario_id} not found")
        scenario = scenarios_db[request.scenario_id]
    elif request.scenario:
        scenario = request.scenario
    elif request.shocks:
        scenario = Scenario(name="Custom Shock Scenario", shocks=request.shocks)
    else:
        raise HTTPException(status_code=400, detail="No scenario specified")
    
    # Run stress test
    stress_result = analytics.run_stress_test(
        positions=positions_dict,
        scenario=scenario.dict(),
        current_prices=current_prices
    )
    
    position_impacts = stress_result.position_impacts if request.include_position_details else "omitted"
    
    response_data = {
        "scenario_name": stress_result.scenario_name,
        "portfolio_value_before": stress_result.portfolio_value_before,
        "portfolio_value_after": stress_result.portfolio_value_after,
        "pnl_impact": stress_result.pnl_impact,
        "pnl_impact_pct": stress_result.pnl_impact_pct,
        "position_impacts": position_impacts,
        "risk_metrics": {"before": stress_result.risk_metrics_before, "after": stress_result.risk_metrics_after}
    }
    
    calculation_time = (time.time() - start_time) * 1000
    
    return StressTestResponse(
        portfolio_id=portfolio_id,
        stress_result=response_data,
        cached=False,
        metadata={"calculation_time_ms": round(calculation_time, 2)}
    )

# -----------------------------------------------------------------------------
# Factor Endpoints
# -----------------------------------------------------------------------------

@app.get("/risk/factors")
async def list_factors(model_id: Optional[str] = None, factor_type: Optional[str] = None):
    """List available risk factors."""
    factors = []
    
    if model_id and model_id in factor_models_db:
        model = factor_models_db[model_id]
        factors = [
            {"factor_id": f.factor_id, "factor_name": f.factor_name, 
             "factor_type": f.factor_type.value, "model_id": model_id, "model_name": model.model_name}
            for f in model.factors
        ]
    else:
        for mid, model in factor_models_db.items():
            for f in model.factors:
                if factor_type is None or f.factor_type.value == factor_type:
                    factors.append({
                        "factor_id": f.factor_id, "factor_name": f.factor_name,
                        "factor_type": f.factor_type.value, "model_id": mid, "model_name": model.model_name
                    })
    
    return {"factors": factors, "count": len(factors)}

# -----------------------------------------------------------------------------
# Scenario Endpoints
# -----------------------------------------------------------------------------

@app.get("/risk/scenarios")
async def list_scenarios():
    """List all stress test scenarios."""
    scenarios = []
    for scenario_id, scenario in scenarios_db.items():
        scenarios.append({
            "scenario_id": scenario_id,
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": scenario.scenario_type.value,
            "shocks": scenario.shocks,
            "is_system": scenario.is_system
        })
    return {"scenarios": scenarios, "count": len(scenarios)}

@app.post("/risk/scenarios")
async def create_scenario(request: ScenarioCreateRequest):
    """Create a new custom stress test scenario."""
    scenario = Scenario(
        name=request.name,
        description=request.description,
        scenario_type=request.scenario_type,
        shocks=request.shocks,
        factor_shocks=request.factor_shocks,
        correlation_stress=request.correlation_stress,
        tags=request.tags,
        is_system=False
    )
    scenarios_db[scenario.scenario_id] = scenario
    return scenario

# -----------------------------------------------------------------------------
# Greeks Calculation Endpoint
# -----------------------------------------------------------------------------

@app.post("/risk/calculate/greeks")
async def calculate_greeks(request: GreeksRequest):
    """Calculate option Greeks using Black-Scholes model."""
    analytics = PortfolioAnalytics()
    
    greeks = analytics.calculate_greeks(
        option_type=request.option_type,
        spot=request.spot,
        strike=request.strike,
        time_to_expiry=request.time_to_expiry,
        risk_free_rate=request.risk_free_rate,
        volatility=request.volatility,
        dividend_yield=request.dividend_yield
    )
    
    return {
        "option_type": request.option_type,
        "spot": request.spot,
        "strike": request.strike,
        "time_to_expiry_years": request.time_to_expiry,
        "greeks": {
            "delta": round(greeks.delta, 6),
            "gamma": round(greeks.gamma, 6),
            "theta": round(greeks.theta, 6),
            "vega": round(greeks.vega, 6),
            "rho": round(greeks.rho, 6),
            "vanna": round(greeks.vanna, 6) if greeks.vanna else None,
            "charm": round(greeks.charm, 6) if greeks.charm else None
        }
    }

# -----------------------------------------------------------------------------
# Portfolio Management Endpoints
# -----------------------------------------------------------------------------

@app.post("/portfolios")
async def create_portfolio(request: PortfolioCreateRequest):
    """Create a new portfolio."""
    portfolio_id = request.portfolio_id or str(uuid.uuid4())
    portfolio = Portfolio(
        portfolio_id=portfolio_id,
        name=request.name,
        base_currency=request.base_currency,
        positions=request.positions
    )
    portfolios_db[portfolio_id] = portfolio
    
    return {
        "portfolio_id": portfolio_id,
        "name": portfolio.name,
        "total_value": portfolio.total_value,
        "n_positions": len(portfolio.positions),
        "created_at": portfolio.created_at.isoformat()
    }

@app.get("/portfolios/{portfolio_id}")
async def get_portfolio(portfolio_id: str):
    """Get portfolio details."""
    if portfolio_id not in portfolios_db:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    portfolio = portfolios_db[portfolio_id]
    return {
        "portfolio_id": portfolio_id,
        "name": portfolio.name,
        "base_currency": portfolio.base_currency,
        "total_value": portfolio.total_value,
        "long_value": portfolio.long_value,
        "short_value": portfolio.short_value,
        "gross_exposure": portfolio.gross_exposure,
        "net_exposure": portfolio.net_exposure,
        "n_positions": len(portfolio.positions),
        "asset_class_breakdown": portfolio.get_asset_class_breakdown(),
        "created_at": portfolio.created_at.isoformat()
    }

# -----------------------------------------------------------------------------
# Cache Management Endpoints
# -----------------------------------------------------------------------------

@app.delete("/cache/clear/{cache_type}")
async def clear_cache(cache_type: str, portfolio_id: Optional[str] = None):
    """Clear cached calculations."""
    if cache_type == "all":
        cache.local_cache.clear()
        return {"cleared": True, "type": "all"}
    elif cache_type == "var":
        keys_to_remove = [k for k in cache.local_cache.keys() if "var" in k]
        for k in keys_to_remove:
            del cache.local_cache[k]
        return {"cleared": True, "type": "var", "count": len(keys_to_remove)}
    elif cache_type == "stress":
        keys_to_remove = [k for k in cache.local_cache.keys() if "stress" in k]
        for k in keys_to_remove:
            del cache.local_cache[k]
        return {"cleared": True, "type": "stress", "count": len(keys_to_remove)}
    return {"cleared": False, "error": "Unknown cache type"}

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
