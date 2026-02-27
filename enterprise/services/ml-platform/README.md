# DragonScope ML Platform

Enterprise-grade MLOps infrastructure for financial machine learning models.

## Overview

The ML Platform provides a complete MLOps stack for developing, deploying, and monitoring financial ML models at scale. It supports:

- **Price Prediction**: Time series forecasting for asset prices
- **Regime Detection**: Market state classification (bull/bear/high-volatility)
- **Anomaly Detection**: Unusual pattern identification in trading data
- **Factor Models**: Risk factor exposure and attribution

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DRAGONSCOPE ML PLATFORM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Feature    │  │    Model     │  │   Training   │  │  Inference   │    │
│  │    Store     │  │   Registry   │  │   Pipeline   │  │   Service    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │            │
│         └─────────────────┴─────────────────┴─────────────────┘            │
│                                   │                                        │
│                         ┌─────────┴─────────┐                              │
│                         │   ML Metadata     │                              │
│                         │    (Lineage)      │                              │
│                         └───────────────────┘                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Online      │  │   Offline    │  │   Model      │  │   A/B        │    │
│  │  Store       │  │   Store      │  │   Artifacts  │  │   Testing    │    │
│  │  (Redis)     │  │   (Iceberg)  │  │   (S3)       │  │   (Split)    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Feature Store (`feature_store.py`)

Dual-store architecture for real-time and batch feature serving:

| Store Type | Storage | Latency | Use Case |
|------------|---------|---------|----------|
| Online | Redis | <10ms | Real-time inference |
| Offline | Apache Iceberg | Seconds | Training, backtesting |

**Key Features:**
- Point-in-time correctness for training data
- Time-window aggregations (EWMA, rolling stats)
- Feature versioning and lineage tracking
- Automated backfill for new features

**Feature Categories:**
```python
# Price Features
- returns_1d, returns_5d, returns_21d
- volatility_20d, volatility_60d
- price_momentum_10d, price_momentum_30d

# Technical Indicators
- rsi_14, macd, bollinger_position
- sma_20, sma_50, ema_12, ema_26
- atr_14, adx_14

# Alternative Data
- sentiment_score, news_volume
- options_flow_bullish_ratio
- insider_buying_ratio
- social_media_mentions

# Macro Features
- vix_level, yield_curve_slope
- dxy_strength, credit_spread
```

### 2. Model Registry (`model_registry.py`)

MLflow-inspired model lifecycle management:

**Versioning:**
- Semantic versioning (MAJOR.MINOR.PATCH)
- Auto-increment on new training runs
- Git commit SHA tracking

**Stage Transitions:**
```
Development → Staging → Production → Archived
     ↑                                    ↓
     └───────── Rollback ←───────────────┘
```

**Capabilities:**
- Artifact storage (models, preprocessing pipelines)
- Model signature validation
- Performance metrics tracking
- Dependency management

### 3. Training Pipeline (`training.py`)

End-to-end training orchestration:

**Pipeline Stages:**
1. **Data Ingestion**: Load features from offline store
2. **Preprocessing**: Scaling, encoding, outlier handling
3. **Cross-Validation**: Time-series aware splits
4. **Hyperparameter Tuning**: Optuna Bayesian optimization
5. **Model Training**: Distributed training support
6. **Evaluation**: Comprehensive metrics suite
7. **Registration**: Auto-register best models

**Time-Series CV:**
```
Fold 1: [Train: 2019-2020] [Val: 2021]
Fold 2: [Train: 2019-2021] [Val: 2022]
Fold 3: [Train: 2019-2022] [Val: 2023]
```

### 4. Inference Service (`inference.py`)

Multi-modal model serving:

**Serving Modes:**
- **Real-time**: HTTP/gRPC endpoints (<50ms p99)
- **Batch**: Scheduled jobs for portfolio scoring
- **Streaming**: Kafka consumers for live predictions

**Advanced Features:**
- Model caching with LRU eviction
- A/B testing with traffic splitting
- Shadow deployment for validation
- Drift detection (data, concept, prediction)

## Model Types

### Price Prediction

**Algorithms:**
- LightGBM for gradient boosting
- Temporal Fusion Transformers (TFT)
- N-BEATS for univariate forecasting
- LSTM/GRU for sequential modeling

**Features:**
- Lagged returns and prices
- Technical indicators
- Market microstructure
- Cross-asset correlations

**Metrics:**
- RMSE, MAE, MAPE
- Directional accuracy
- Sharpe ratio of predictions
- Maximum drawdown

### Regime Detection

**Algorithms:**
- Hidden Markov Models (HMM)
- Gaussian Mixture Models
- Clustering (K-Means, DBSCAN)
- Supervised classification (XGBoost)

**Regimes:**
- Bull market (low vol, upward trend)
- Bear market (high vol, downward trend)
- High volatility (uncertainty)
- Low volatility (complacency)
- Mean-reverting (range-bound)

**Use Cases:**
- Dynamic position sizing
- Strategy selection
- Risk management

### Anomaly Detection

**Algorithms:**
- Isolation Forest
- Autoencoders (LSTM-VAE)
- One-Class SVM
- Prophet for time series

**Anomaly Types:**
- Price jumps/gaps
- Volume spikes
- Unusual correlation breakdowns
- Flash crash precursors

**Applications:**
- Risk alerts
- Fraud detection
- Market manipulation detection

### Factor Models

**Model Types:**
- Fama-French 3/5 factor
- PCA-based statistical factors
- Deep factor models
- Custom fundamental factors

**Factors:**
- Market, Size, Value, Momentum, Quality
- Volatility, Liquidity, Sentiment
- Macroeconomic factors
- Custom alpha factors

## A/B Testing Framework

### Experiment Types

1. **Model Comparison**: Old vs new model performance
2. **Feature Variants**: Different feature sets
3. **Hyperparameters**: Tuned vs baseline
4. **Ensemble Strategies**: Weighting schemes

### Traffic Splitting

```python
# Configurable splits
control: 45%
treatment_a: 45%
shadow: 10%  # Shadow deployment, not used for decisions
```

### Metrics

- **Online**: Prediction accuracy, latency, error rates
- **Business**: P&L, Sharpe ratio, max drawdown
- **Statistical**: P-value, confidence intervals, power analysis

## AutoML Capabilities

### Feature Engineering

- Automatic feature interactions
- Polynomial features
- Time-based aggregations
- Lag feature generation

### Model Selection

- Algorithm comparison (XGBoost, LightGBM, CatBoost)
- Neural architecture search (NAS)
- Ensemble stacking
- Model compression

### Hyperparameter Optimization

```python
# Optuna-based tuning
- Bayesian optimization
- Early stopping (Hyperband)
- Distributed trials
- Multi-objective (accuracy + latency)
```

## Monitoring & Observability

### Data Drift Detection

- **Statistical Tests**: KS test, Chi-square, PSI
- **Distance Metrics**: Wasserstein, Jensen-Shannon
- **Feature Drift**: Per-feature monitoring
- **Prediction Drift**: Output distribution changes

### Model Performance

- Real-time accuracy tracking
- Prediction confidence calibration
- Feature importance drift
- Business metric correlation

### System Metrics

- Inference latency (p50, p99)
- Throughput (predictions/sec)
- Cache hit rates
- Resource utilization

## Security & Compliance

- Model signing and verification
- Audit trails for all model changes
- PII handling in features
- GDPR/CCPA compliance for model predictions
- Access control (RBAC) for model operations

## Usage Examples

### Training a Price Prediction Model

```python
from ml_platform.feature_store import FeatureStore
from ml_platform.training import TrainingPipeline
from ml_platform.model_registry import ModelRegistry

# Initialize components
feature_store = FeatureStore()
registry = ModelRegistry()

# Define training pipeline
pipeline = TrainingPipeline(
    name="btc_price_predictor",
    model_type="price_prediction",
    algorithm="lightgbm",
    feature_store=feature_store,
    registry=registry
)

# Configure features
pipeline.add_features([
    "returns_1d", "returns_5d", "volatility_20d",
    "rsi_14", "macd", "sentiment_score"
])

# Run training with hyperparameter tuning
result = pipeline.train(
    start_date="2020-01-01",
    end_date="2024-01-01",
    hyperparameter_tuning=True,
    cv_folds=5
)

# Register best model
model_version = result.register(
    stage="staging",
    metrics={"val_rmse": result.best_rmse}
)
```

### Real-time Inference

```python
from ml_platform.inference import InferenceService

# Initialize service
service = InferenceService(
    model_name="btc_price_predictor",
    model_version="1.2.0"
)

# Real-time prediction
prediction = service.predict({
    "symbol": "BTC-USD",
    "features": ["returns_1d", "rsi_14", ...]
})

print(f"Predicted return: {prediction.value}")
print(f"Confidence: {prediction.confidence}")
```

### Feature Retrieval

```python
# Online features (low latency)
features = feature_store.get_online_features(
    entity_ids=["AAPL", "GOOGL"],
    feature_names=["rsi_14", "macd", "volume_ema"],
    timestamp=datetime.utcnow()
)

# Offline features (training)
training_df = feature_store.get_historical_features(
    entity_df=symbols,
    feature_names=["returns_1d", "volatility_20d"],
    start_date="2020-01-01",
    end_date="2024-01-01"
)
```

## Configuration

### Environment Variables

```bash
# Feature Store
ML_PLATFORM__REDIS_URL=redis://localhost:6379
ML_PLATFORM__ICEBERG_CATALOG=s3://dragonscope-ml/warehouse

# Model Registry
ML_PLATFORM__REGISTRY_URI=s3://dragonscope-ml/registry
ML_PLATFORM__ARTIFACT_STORE=s3://dragonscope-ml/artifacts

# Training
ML_PLATFORM__OPTUNA_STORAGE=postgresql://optuna:pass@db/optuna
ML_PLATFORM__MLFLOW_TRACKING_URI=http://mlflow:5000

# Inference
ML_PLATFORM__CACHE_SIZE=10000
ML_PLATFORM__MAX_LATENCY_MS=50
```

## Development

### Running Tests

```bash
pytest tests/ -v --cov=ml_platform
```

### Local Development

```bash
# Start dependencies
docker-compose up -d redis iceberg minio

# Run training pipeline
python -m ml_platform.training --config configs/price_pred.yaml

# Start inference server
python -m ml_platform.inference.server --port 8080
```

## Roadmap

- [ ] Multi-model ensemble serving
- [ ] Federated learning support
- [ ] Explainability (SHAP, LIME) integration
- [ ] Reinforcement learning for trading
- [ ] NLP models for sentiment analysis
- [ ] Graph neural networks for market networks
