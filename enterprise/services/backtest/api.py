"""
FastAPI Backtest API - REST endpoints for backtesting operations.

Provides HTTP API for running backtests, managing strategies,
and comparing results.
"""

from __future__ import annotations

import json
import logging
import pickle
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, validator

# Import backtesting components
try:
    from .engine import BacktestEngine, BacktestConfig, BacktestResults
    from .analytics import PerformanceMetrics, TradeStatistics
    from .execution_models import MarketOrderModel, LimitOrderModel
    from .market_impact import SquareRootImpactModel, LinearImpactModel
except ImportError:
    # For standalone testing
    from engine import BacktestEngine, BacktestConfig, BacktestResults
    from analytics import PerformanceMetrics, TradeStatistics
    from execution_models import MarketOrderModel, LimitOrderModel
    from market_impact import SquareRootImpactModel, LinearImpactModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DragonScope Backtesting API",
    description="Professional backtesting engine for quantitative trading strategies",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with database in production)
STRATEGIES: Dict[str, Dict] = {}
BACKTESTS: Dict[str, BacktestResults] = {}
DATA_CACHE: Dict[str, pd.DataFrame] = {}


# ==================== Pydantic Models ====================

class BacktestRequest(BaseModel):
    """Request model for running a backtest."""
    
    strategy_id: Optional[str] = None
    strategy_code: Optional[str] = None
    symbols: List[str] = Field(default_factory=list)
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(default=1_000_000, gt=0)
    data_frequency: str = Field(default="1d", regex="^(tick|1min|5min|1h|1d)$")
    commission_rate: float = Field(default=0.001, ge=0)
    slippage_bps: float = Field(default=1.0, ge=0)
    allow_short: bool = True
    execution_model: str = Field(default="market", regex="^(market|limit|sor)$")
    impact_model: str = Field(default="linear", regex="^(linear|sqrt|none)$")
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values:
            start = datetime.strptime(values['start_date'], '%Y-%m-%d')
            end = datetime.strptime(v, '%Y-%m-%d')
            if end <= start:
                raise ValueError('end_date must be after start_date')
        return v


class StrategyUpload(BaseModel):
    """Strategy upload metadata."""
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class StrategyResponse(BaseModel):
    """Strategy response model."""
    strategy_id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class BacktestResponse(BaseModel):
    """Backtest response model."""
    backtest_id: str
    status: str
    strategy_id: Optional[str]
    start_date: str
    end_date: str
    symbols: List[str]
    created_at: datetime
    completed_at: Optional[datetime] = None


class BacktestResultsResponse(BaseModel):
    """Detailed backtest results response."""
    backtest_id: str
    summary: Dict[str, Any]
    metrics: Dict[str, float]
    trade_stats: Dict[str, Any]
    drawdown_analysis: Dict[str, Any]
    equity_curve: Optional[List[Dict]] = None


class ComparisonRequest(BaseModel):
    """Request model for comparing backtests."""
    backtest_ids: List[str] = Field(..., min_items=2, max_items=10)
    metrics: List[str] = Field(
        default_factory=lambda: ["sharpe_ratio", "total_return", "max_drawdown"]
    )


# ==================== Helper Functions ====================

def load_sample_data(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Load or generate sample market data for backtesting."""
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    data = []
    for symbol in symbols:
        np.random.seed(hash(symbol) % 2**32)
        
        # Generate synthetic OHLCV data
        returns = np.random.normal(0.0005, 0.02, len(dates))
        prices = 100 * np.exp(np.cumsum(returns))
        
        for i, date in enumerate(dates):
            volatility = 0.01
            open_price = prices[i] * (1 + np.random.normal(0, volatility * 0.3))
            close_price = prices[i]
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, volatility)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, volatility)))
            volume = np.random.randint(1_000_000, 10_000_000)
            
            data.append({
                'date': date,
                'symbol': symbol,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
            })
    
    df = pd.DataFrame(data)
    df.set_index('date', inplace=True)
    return df


def create_execution_model(model_type: str, slippage_bps: float):
    """Create execution model based on configuration."""
    if model_type == "market":
        return MarketOrderModel(slippage_bps=slippage_bps)
    elif model_type == "limit":
        return LimitOrderModel()
    else:
        return MarketOrderModel(slippage_bps=slippage_bps)


def create_impact_model(model_type: str):
    """Create impact model based on configuration."""
    if model_type == "linear":
        return LinearImpactModel()
    elif model_type == "sqrt":
        return SquareRootImpactModel()
    else:
        return None


def results_to_dict(results: BacktestResults, include_equity: bool = False) -> Dict:
    """Convert BacktestResults to dictionary for JSON response."""
    response = {
        'backtest_id': results.backtest_id,
        'summary': results.summary(),
        'metrics': results.metrics.to_dict(),
        'trade_stats': results.trade_stats.to_dict(),
        'config': {
            'initial_capital': results.config.initial_capital,
            'symbols': results.config.symbols,
            'start_date': results.config.start_date.isoformat() if isinstance(results.config.start_date, datetime) else results.config.start_date,
            'end_date': results.config.end_date.isoformat() if isinstance(results.config.end_date, datetime) else results.config.end_date,
        },
    }
    
    if include_equity and not results.equity_curve.empty:
        # Sample equity curve for response (every 10th point)
        equity_sample = results.equity_curve.iloc[::10].copy()
        response['equity_curve'] = [
            {'date': idx.isoformat(), 'equity': row['equity']}
            for idx, row in equity_sample.iterrows()
        ]
    
    return response


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "DragonScope Backtesting API",
        "version": "2.0.0",
        "documentation": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_backtests": len(BACKTESTS),
        "stored_strategies": len(STRATEGIES),
    }


@app.post("/api/v1/strategies", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def upload_strategy(
    name: str,
    file: UploadFile = File(...),
    description: Optional[str] = None,
):
    """Upload a new trading strategy."""
    strategy_id = str(uuid.uuid4())[:8]
    
    try:
        content = await file.read()
        strategy_code = content.decode('utf-8')
        compile(strategy_code, file.filename, 'exec')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy code: {str(e)}"
        )
    
    now = datetime.now()
    STRATEGIES[strategy_id] = {
        'strategy_id': strategy_id,
        'name': name,
        'description': description,
        'filename': file.filename,
        'code': strategy_code,
        'created_at': now,
        'updated_at': now,
    }
    
    logger.info(f"Strategy uploaded: {strategy_id} - {name}")
    
    return StrategyResponse(
        strategy_id=strategy_id,
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
    )


@app.get("/api/v1/strategies", response_model=List[StrategyResponse])
async def list_strategies():
    """List all uploaded strategies."""
    return [
        StrategyResponse(
            strategy_id=s['strategy_id'],
            name=s['name'],
            description=s['description'],
            created_at=s['created_at'],
            updated_at=s['updated_at'],
        )
        for s in STRATEGIES.values()
    ]


@app.get("/api/v1/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy details."""
    if strategy_id not in STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found"
        )
    
    strategy = STRATEGIES[strategy_id].copy()
    del strategy['code']
    return strategy


@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """Delete a strategy."""
    if strategy_id not in STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found"
        )
    
    del STRATEGIES[strategy_id]
    logger.info(f"Strategy deleted: {strategy_id}")
    return {"message": f"Strategy {strategy_id} deleted"}


@app.post("/api/v1/backtests", response_model=BacktestResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(request: BacktestRequest):
    """Run a new backtest."""
    backtest_id = str(uuid.uuid4())[:8]
    
    if request.strategy_id and request.strategy_id not in STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {request.strategy_id} not found"
        )
    
    now = datetime.now()
    BACKTESTS[backtest_id] = None
    
    try:
        data = load_sample_data(request.symbols, request.start_date, request.end_date)
        
        start_dt = datetime.strptime(request.start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(request.end_date, '%Y-%m-%d')
        
        config = BacktestConfig(
            initial_capital=request.initial_capital,
            start_date=start_dt,
            end_date=end_dt,
            symbols=request.symbols,
            data_frequency=request.data_frequency,
            commission_rate=request.commission_rate,
            slippage_bps=request.slippage_bps,
            allow_short=request.allow_short,
            execution_model=create_execution_model(request.execution_model, request.slippage_bps),
            impact_model=create_impact_model(request.impact_model),
        )
        
        engine = BacktestEngine(config)
        engine.load_data(data)
        
        from examples.moving_average_crossover import MACrossoverStrategy
        strategy = MACrossoverStrategy(fast_period=20, slow_period=50)
        
        results = engine.run(strategy)
        BACKTESTS[backtest_id] = results
        
        logger.info(f"Backtest completed: {backtest_id}")
        
    except Exception as e:
        logger.error(f"Backtest failed: {backtest_id} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest execution failed: {str(e)}"
        )
    
    return BacktestResponse(
        backtest_id=backtest_id,
        status="completed",
        strategy_id=request.strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        symbols=request.symbols,
        created_at=now,
        completed_at=datetime.now(),
    )


@app.get("/api/v1/backtests")
async def list_backtests(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all backtests."""
    backtest_list = [
        {
            'backtest_id': bt_id,
            'status': 'completed' if bt is not None else 'running',
            'summary': bt.summary() if bt else None,
        }
        for bt_id, bt in list(BACKTESTS.items())[offset:offset+limit]
    ]
    
    return {
        'backtests': backtest_list,
        'total': len(BACKTESTS),
        'limit': limit,
        'offset': offset,
    }


@app.get("/api/v1/backtests/{backtest_id}")
async def get_backtest(backtest_id: str):
    """Get backtest status and summary."""
    if backtest_id not in BACKTESTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found"
        )
    
    results = BACKTESTS[backtest_id]
    if results is None:
        return {'backtest_id': backtest_id, 'status': 'running'}
    
    return results_to_dict(results, include_equity=False)


@app.get("/api/v1/backtests/{backtest_id}/results")
async def get_backtest_results(
    backtest_id: str,
    include_equity: bool = Query(False),
):
    """Get detailed backtest results."""
    if backtest_id not in BACKTESTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found"
        )
    
    results = BACKTESTS[backtest_id]
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backtest {backtest_id} is still running"
        )
    
    return results_to_dict(results, include_equity=include_equity)


@app.get("/api/v1/backtests/{backtest_id}/equity")
async def get_equity_curve(backtest_id: str, format: str = Query("json")):
    """Get equity curve data."""
    if backtest_id not in BACKTESTS or BACKTESTS[backtest_id] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found or not complete"
        )
    
    results = BACKTESTS[backtest_id]
    equity = results.equity_curve
    
    if format == "csv":
        csv_data = equity.to_csv()
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=equity_{backtest_id}.csv"}
        )
    
    return {
        'backtest_id': backtest_id,
        'equity_curve': [
            {'date': idx.isoformat(), 'equity': row['equity'], 'returns': row.get('returns', 0)}
            for idx, row in equity.iterrows()
        ]
    }


@app.get("/api/v1/backtests/{backtest_id}/trades")
async def get_trade_history(backtest_id: str):
    """Get trade/fill history."""
    if backtest_id not in BACKTESTS or BACKTESTS[backtest_id] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found or not complete"
        )
    
    results = BACKTESTS[backtest_id]
    
    trades = []
    for fill in results.fills:
        trades.append({
            'order_id': fill.order_id,
            'symbol': fill.symbol,
            'side': fill.side.name,
            'quantity': fill.quantity,
            'fill_price': fill.fill_price,
            'timestamp': fill.timestamp.to_datetime().isoformat(),
            'commission': fill.commission,
            'slippage': fill.slippage,
        })
    
    return {
        'backtest_id': backtest_id,
        'total_trades': len(trades),
        'trades': trades,
    }


@app.delete("/api/v1/backtests/{backtest_id}")
async def delete_backtest(backtest_id: str):
    """Delete a backtest."""
    if backtest_id not in BACKTESTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found"
        )
    
    del BACKTESTS[backtest_id]
    logger.info(f"Backtest deleted: {backtest_id}")
    return {"message": f"Backtest {backtest_id} deleted"}


@app.post("/api/v1/backtests/compare")
async def compare_backtests(request: ComparisonRequest):
    """Compare multiple backtests."""
    for bt_id in request.backtest_ids:
        if bt_id not in BACKTESTS or BACKTESTS[bt_id] is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest {bt_id} not found or not complete"
            )
    
    comparison = {'metrics': request.metrics, 'backtests': {}}
    
    for bt_id in request.backtest_ids:
        results = BACKTESTS[bt_id]
        metrics_dict = results.metrics.to_dict()
        stats_dict = results.trade_stats.to_dict()
        
        comparison['backtests'][bt_id] = {
            'summary': results.summary(),
            'metrics': {k: metrics_dict.get(k) for k in request.metrics if k in metrics_dict},
            'trade_stats': stats_dict,
        }
    
    winners = {}
    for metric in request.metrics:
        values = {
            bt_id: data['metrics'].get(metric, float('-inf'))
            for bt_id, data in comparison['backtests'].items()
        }
        
        lower_is_better = ['max_drawdown', 'volatility', 'var_95', 'var_99', 'cvar_95']
        
        if metric in lower_is_better:
            winner = min(values, key=values.get)
        else:
            winner = max(values, key=values.get)
        
        winners[metric] = {'backtest_id': winner, 'value': values[winner]}
    
    comparison['winners'] = winners
    return comparison


@app.get("/api/v1/backtests/{backtest_id}/report")
async def generate_report(backtest_id: str):
    """Generate comprehensive backtest report."""
    if backtest_id not in BACKTESTS or BACKTESTS[backtest_id] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found or not complete"
        )
    
    results = BACKTESTS[backtest_id]
    
    report = {
        'backtest_id': backtest_id,
        'generated_at': datetime.now().isoformat(),
        'summary': results.summary(),
        'performance_metrics': results.metrics.to_dict(),
        'trade_statistics': results.trade_stats.to_dict(),
        'drawdown_analysis': DrawdownAnalyzer.analyze(results.equity_curve['equity']),
        'configuration': {
            'initial_capital': results.config.initial_capital,
            'symbols': results.config.symbols,
            'start_date': str(results.config.start_date),
            'end_date': str(results.config.end_date),
            'commission_rate': results.config.commission_rate,
            'slippage_bps': results.config.slippage_bps,
        },
    }
    
    return report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
