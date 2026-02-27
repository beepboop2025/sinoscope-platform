"""
DragonScope Inference Service

Real-time and batch inference with model caching, A/B testing,
shadow deployment, and drift detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from collections import defaultdict, deque
import uuid

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PredictionType(Enum):
    """Types of predictions."""
    POINT = "point"  # Single value
    DISTRIBUTION = "distribution"  # Probabilistic
    INTERVAL = "interval"  # Confidence interval
    SEQUENCE = "sequence"  # Time series forecast


class DriftType(Enum):
    """Types of drift that can be detected."""
    DATA_DRIFT = "data_drift"  # Input feature distribution change
    CONCEPT_DRIFT = "concept_drift"  # Relationship change
    PREDICTION_DRIFT = "prediction_drift"  # Output distribution change
    FEATURE_DRIFT = "feature_drift"  # Individual feature drift


@dataclass
class Prediction:
    """A model prediction result."""
    model_name: str
    model_version: str
    entity_id: str
    timestamp: datetime
    
    # Prediction value
    value: Any
    prediction_type: PredictionType = PredictionType.POINT
    
    # Uncertainty
    confidence: Optional[float] = None
    std_dev: Optional[float] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    
    # Full distribution for probabilistic predictions
    distribution: Optional[Dict[str, float]] = None
    
    # Metadata
    feature_values: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    experiment_id: Optional[str] = None
    is_shadow: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "prediction_type": self.prediction_type.value,
            "confidence": self.confidence,
            "std_dev": self.std_dev,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "distribution": self.distribution,
            "latency_ms": self.latency_ms,
            "experiment_id": self.experiment_id,
            "is_shadow": self.is_shadow,
        }


@dataclass
class DriftReport:
    """Drift detection report."""
    drift_type: DriftType
    feature_name: Optional[str]
    detected: bool
    p_value: float
    statistic: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reference_distribution: Optional[Dict] = None
    current_distribution: Optional[Dict] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_type": self.drift_type.value,
            "feature_name": self.feature_name,
            "detected": self.detected,
            "p_value": self.p_value,
            "statistic": self.statistic,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Experiment:
    """A/B test experiment configuration."""
    id: str
    name: str
    model_name: str
    
    # Variants
    control_version: str
    treatment_version: str
    traffic_split: Dict[str, float]  # variant -> percentage
    
    # Configuration
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, paused, completed
    
    # Metrics tracking
    metrics: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    def assign_variant(self, entity_id: str) -> str:
        """Assign entity to variant using consistent hashing."""
        hash_val = int(hashlib.md5(f"{self.id}:{entity_id}".encode()).hexdigest(), 16)
        bucket = hash_val % 100
        
        cumulative = 0
        for variant, pct in self.traffic_split.items():
            cumulative += pct
            if bucket < cumulative:
                return variant
        
        return list(self.traffic_split.keys())[-1]


class ModelCache:
    """LRU cache for loaded models."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get model from cache."""
        with self._lock:
            if key not in self._cache:
                return None
            
            model, cached_at = self._cache[key]
            
            # Check TTL
            if datetime.utcnow() - cached_at > timedelta(seconds=self.ttl_seconds):
                del self._cache[key]
                del self._access_times[key]
                return None
            
            self._access_times[key] = datetime.utcnow()
            return model
    
    def put(self, key: str, model: Any) -> None:
        """Add model to cache."""
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self.max_size:
                oldest = min(self._access_times, key=self._access_times.get)
                del self._cache[oldest]
                del self._access_times[oldest]
            
            self._cache[key] = (model, datetime.utcnow())
            self._access_times[key] = datetime.utcnow()
    
    def invalidate(self, key: str) -> None:
        """Remove model from cache."""
        with self._lock:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cached models."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
            }


class DriftDetector:
    """Detect drift in data, predictions, and concepts."""
    
    def __init__(
        self,
        reference_data: Optional[pd.DataFrame] = None,
        window_size: int = 1000,
        drift_threshold: float = 0.05,
    ):
        self.reference_data = reference_data
        self.window_size = window_size
        self.drift_threshold = drift_threshold
        
        self._reference_stats: Dict[str, Dict] = {}
        self._prediction_window: deque = deque(maxlen=window_size)
        self._feature_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        
        if reference_data is not None:
            self._compute_reference_stats()
    
    def _compute_reference_stats(self) -> None:
        """Compute reference distribution statistics."""
        for col in self.reference_data.select_dtypes(include=[np.number]).columns:
            self._reference_stats[col] = {
                "mean": self.reference_data[col].mean(),
                "std": self.reference_data[col].std(),
                "quantiles": self.reference_data[col].quantile([0.25, 0.5, 0.75]).to_dict(),
            }
    
    def detect_feature_drift(
        self,
        feature_name: str,
        current_value: float,
    ) -> Optional[DriftReport]:
        """Detect drift for a single feature."""
        if feature_name not in self._reference_stats:
            return None
        
        window = self._feature_windows[feature_name]
        window.append(current_value)
        
        if len(window) < 100:
            return None
        
        # Simple z-score based drift detection
        ref_mean = self._reference_stats[feature_name]["mean"]
        ref_std = self._reference_stats[feature_name]["std"]
        
        current_mean = np.mean(window)
        z_score = abs(current_mean - ref_mean) / (ref_std + 1e-8)
        
        # Two-sample t-test approximation
        n = len(window)
        t_stat = z_score * np.sqrt(n)
        
        # Simple p-value approximation
        p_value = 2 * (1 - self._approx_cdf(abs(t_stat)))
        
        return DriftReport(
            drift_type=DriftType.FEATURE_DRIFT,
            feature_name=feature_name,
            detected=p_value < self.drift_threshold,
            p_value=p_value,
            statistic=t_stat,
            threshold=self.drift_threshold,
            reference_distribution=self._reference_stats.get(feature_name),
            current_distribution={"mean": current_mean, "std": np.std(window)},
        )
    
    def detect_prediction_drift(
        self,
        prediction: Prediction,
    ) -> Optional[DriftReport]:
        """Detect drift in prediction distribution."""
        self._prediction_window.append(prediction.value)
        
        if len(self._prediction_window) < 100:
            return None
        
        current_window = list(self._prediction_window)
        
        # KS test approximation
        if len(current_window) >= self.window_size // 2:
            # Compare first half vs second half
            mid = len(current_window) // 2
            stat, p_value = self._approx_ks_test(current_window[:mid], current_window[mid:])
            
            return DriftReport(
                drift_type=DriftType.PREDICTION_DRIFT,
                feature_name=None,
                detected=p_value < self.drift_threshold,
                p_value=p_value,
                statistic=stat,
                threshold=self.drift_threshold,
            )
        
        return None
    
    def _approx_cdf(self, x: float) -> float:
        """Approximate standard normal CDF."""
        # Abramowitz and Stegun approximation
        b1 = 0.319381530
        b2 = -0.356563782
        b3 = 1.781477937
        b4 = -1.821255978
        b5 = 1.330274429
        p = 0.2316419
        c = 0.39894228
        
        if x >= 0:
            t = 1.0 / (1.0 + p * x)
            return 1.0 - c * np.exp(-x * x / 2.0) * t * (t * (t * (t * (t * b5 + b4) + b3) + b2) + b1)
        else:
            return 1.0 - self._approx_cdf(-x)
    
    def _approx_ks_test(self, x: List[float], y: List[float]) -> Tuple[float, float]:
        """Approximate Kolmogorov-Smirnov test."""
        x_sorted = sorted(x)
        y_sorted = sorted(y)
        
        # Compute ECDFs and find max difference
        all_vals = sorted(set(x + y))
        max_diff = 0
        
        for val in all_vals:
            x_cdf = sum(1 for v in x_sorted if v <= val) / len(x_sorted)
            y_cdf = sum(1 for v in y_sorted if v <= val) / len(y_sorted)
            max_diff = max(max_diff, abs(x_cdf - y_cdf))
        
        # Approximate p-value
        n = len(x) * len(y) / (len(x) + len(y))
        p_value = np.exp(-2 * n * max_diff * max_diff)
        
        return max_diff, p_value


class InferenceService:
    """
    Real-time and batch inference service.
    
    Features:
    - Model caching for low latency
    - A/B testing with traffic splitting
    - Shadow deployment for validation
    - Drift detection
    """
    
    def __init__(
        self,
        registry: Any,
        feature_store: Optional[Any] = None,
        cache_size: int = 100,
        enable_drift_detection: bool = True,
    ):
        self.registry = registry
        self.feature_store = feature_store
        self.cache = ModelCache(max_size=cache_size)
        self.enable_drift_detection = enable_drift_detection
        
        # Experiments (A/B tests)
        self._experiments: Dict[str, Experiment] = {}
        
        # Drift detectors per model
        self._drift_detectors: Dict[str, DriftDetector] = {}
        
        # Metrics
        self._prediction_count = 0
        self._latency_sum = 0.0
        self._error_count = 0
    
    def predict(
        self,
        entity_id: str,
        model_name: str,
        model_version: Optional[str] = None,
        features: Optional[Dict[str, Any]] = None,
        fetch_features: bool = True,
    ) -> Prediction:
        """
        Generate a real-time prediction.
        
        Args:
            entity_id: Entity identifier (e.g., symbol)
            model_name: Model name in registry
            model_version: Specific version (default: production)
            features: Pre-computed features (optional)
            fetch_features: Fetch features from feature store
        
        Returns:
            Prediction object
        """
        start_time = time.time()
        timestamp = datetime.utcnow()
        
        try:
            # Check for active experiments
            experiment = self._get_active_experiment(model_name)
            if experiment:
                variant = experiment.assign_variant(entity_id)
                if variant == "control":
                    model_version = experiment.control_version
                else:
                    model_version = experiment.treatment_version
            
            # Load model (with caching)
            model, scaler, feature_columns = self._load_model(model_name, model_version)
            
            # Get features
            if features is None and fetch_features and self.feature_store:
                features = self._fetch_features(entity_id, feature_columns)
            
            if features is None:
                raise ValueError("Features must be provided or fetched from feature store")
            
            # Prepare input
            X = self._prepare_input(features, feature_columns, scaler)
            
            # Generate prediction
            value = self._generate_prediction(model, X)
            
            # Build prediction object
            latency_ms = (time.time() - start_time) * 1000
            
            prediction = Prediction(
                model_name=model_name,
                model_version=model_version or "latest",
                entity_id=entity_id,
                timestamp=timestamp,
                value=float(value),
                feature_values=features,
                latency_ms=latency_ms,
                experiment_id=experiment.id if experiment else None,
            )
            
            # Drift detection
            if self.enable_drift_detection:
                self._check_drift(prediction, features)
            
            # Update metrics
            self._prediction_count += 1
            self._latency_sum += latency_ms
            
            # Shadow deployment if configured
            shadow_pred = self._generate_shadow_prediction(model_name, entity_id, features)
            if shadow_pred:
                logger.debug(f"Shadow prediction: {shadow_pred.value}")
            
            return prediction
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"Prediction failed: {e}")
            raise
    
    def predict_batch(
        self,
        entity_ids: List[str],
        model_name: str,
        model_version: Optional[str] = None,
        features_df: Optional[pd.DataFrame] = None,
    ) -> List[Prediction]:
        """
        Generate batch predictions.
        
        Args:
            entity_ids: List of entity identifiers
            model_name: Model name
            model_version: Specific version
            features_df: DataFrame with pre-computed features
        
        Returns:
            List of Prediction objects
        """
        start_time = time.time()
        timestamp = datetime.utcnow()
        
        # Load model
        model, scaler, feature_columns = self._load_model(model_name, model_version)
        
        # Get features for all entities
        if features_df is None and self.feature_store:
            features_df = self.feature_store.get_online_features(
                entity_ids=entity_ids,
                feature_names=feature_columns,
            )
        
        # Batch prediction
        X = features_df[feature_columns].values
        if scaler:
            X = scaler.transform(X)
        
        predictions = model.predict(X)
        
        # Build prediction objects
        results = []
        latency_ms = (time.time() - start_time) * 1000 / len(entity_ids)
        
        for i, entity_id in enumerate(entity_ids):
            pred = Prediction(
                model_name=model_name,
                model_version=model_version or "latest",
                entity_id=entity_id,
                timestamp=timestamp,
                value=float(predictions[i]),
                latency_ms=latency_ms,
            )
            results.append(pred)
        
        self._prediction_count += len(entity_ids)
        self._latency_sum += latency_ms * len(entity_ids)
        
        return results
    
    def _load_model(
        self,
        model_name: str,
        model_version: Optional[str] = None,
    ) -> Tuple[Any, Any, List[str]]:
        """Load model from cache or registry."""
        cache_key = f"{model_name}:{model_version or 'prod'}"
        
        cached = self.cache.get(cache_key)
        if cached:
            return cached["model"], cached.get("scaler"), cached["feature_columns"]
        
        # Load from registry
        model_bundle = self.registry.load_model(model_name, model_version)
        
        if isinstance(model_bundle, dict):
            model = model_bundle.get("model")
            scaler = model_bundle.get("scaler")
            feature_columns = model_bundle.get("feature_columns", [])
        else:
            model = model_bundle
            scaler = None
            feature_columns = []
        
        # Cache
        self.cache.put(cache_key, {
            "model": model,
            "scaler": scaler,
            "feature_columns": feature_columns,
        })
        
        return model, scaler, feature_columns
    
    def _fetch_features(self, entity_id: str, feature_names: List[str]) -> Dict[str, Any]:
        """Fetch features from feature store."""
        if not self.feature_store:
            return {}
        
        df = self.feature_store.get_online_features(
            entity_ids=[entity_id],
            feature_names=feature_names,
        )
        
        if df.empty:
            return {}
        
        return df.iloc[0].to_dict()
    
    def _prepare_input(
        self,
        features: Dict[str, Any],
        feature_columns: List[str],
        scaler: Optional[Any],
    ) -> np.ndarray:
        """Prepare input features for model."""
        values = []
        for col in feature_columns:
            val = features.get(col, 0)
            values.append(float(val) if val is not None else 0)
        
        X = np.array(values).reshape(1, -1)
        
        if scaler:
            X = scaler.transform(X)
        
        return X
    
    def _generate_prediction(self, model: Any, X: np.ndarray) -> float:
        """Generate prediction from model."""
        if hasattr(model, "predict"):
            pred = model.predict(X)
            return float(pred[0]) if len(pred.shape) > 0 else float(pred)
        else:
            # For models with custom interface
            return float(model.predict(X))
    
    def _get_active_experiment(self, model_name: str) -> Optional[Experiment]:
        """Get active A/B test for model."""
        for exp in self._experiments.values():
            if exp.model_name == model_name and exp.status == "running":
                if exp.start_time <= datetime.utcnow():
                    if exp.end_time is None or exp.end_time > datetime.utcnow():
                        return exp
        return None
    
    def _generate_shadow_prediction(
        self,
        model_name: str,
        entity_id: str,
        features: Dict[str, Any],
    ) -> Optional[Prediction]:
        """Generate shadow prediction for validation."""
        # Check if there's a staging version to shadow test
        staging = self.registry.get_version(model_name, stage="staging")
        if not staging:
            return None
        
        # Skip if production is already the staging version
        prod = self.registry.get_version(model_name, stage="production")
        if prod and prod.version == staging.version:
            return None
        
        try:
            # Generate shadow prediction (don't cache)
            model_bundle = self.registry.load_model(model_name, staging.version)
            model = model_bundle.get("model") if isinstance(model_bundle, dict) else model_bundle
            scaler = model_bundle.get("scaler") if isinstance(model_bundle, dict) else None
            feature_columns = model_bundle.get("feature_columns", []) if isinstance(model_bundle, dict) else []
            
            X = self._prepare_input(features, feature_columns, scaler)
            value = self._generate_prediction(model, X)
            
            return Prediction(
                model_name=model_name,
                model_version=staging.version,
                entity_id=entity_id,
                timestamp=datetime.utcnow(),
                value=value,
                is_shadow=True,
            )
        except Exception as e:
            logger.warning(f"Shadow prediction failed: {e}")
            return None
    
    def _check_drift(self, prediction: Prediction, features: Dict[str, Any]) -> None:
        """Check for drift in features and predictions."""
        model_key = f"{prediction.model_name}:{prediction.model_version}"
        
        if model_key not in self._drift_detectors:
            # Initialize drift detector with reference data
            # In practice, this would load reference data from storage
            self._drift_detectors[model_key] = DriftDetector()
        
        detector = self._drift_detectors[model_key]
        
        # Check prediction drift
        drift_report = detector.detect_prediction_drift(prediction)
        if drift_report and drift_report.detected:
            logger.warning(f"Prediction drift detected for {model_key}: p={drift_report.p_value:.4f}")
        
        # Check feature drift
        for feature_name, feature_value in features.items():
            if isinstance(feature_value, (int, float)):
                drift_report = detector.detect_feature_drift(feature_name, feature_value)
                if drift_report and drift_report.detected:
                    logger.warning(f"Feature drift detected for {feature_name}: p={drift_report.p_value:.4f}")
    
    def create_experiment(
        self,
        name: str,
        model_name: str,
        control_version: str,
        treatment_version: str,
        traffic_split: Dict[str, float],
        duration_days: int = 14,
    ) -> Experiment:
        """
        Create an A/B testing experiment.
        
        Args:
            name: Experiment name
            model_name: Model being tested
            control_version: Baseline model version
            treatment_version: New model version
            traffic_split: Traffic allocation (e.g., {"control": 0.5, "treatment": 0.5})
            duration_days: Experiment duration
        
        Returns:
            Experiment object
        """
        experiment = Experiment(
            id=str(uuid.uuid4())[:8],
            name=name,
            model_name=model_name,
            control_version=control_version,
            treatment_version=treatment_version,
            traffic_split=traffic_split,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(days=duration_days),
        )
        
        self._experiments[experiment.id] = experiment
        logger.info(f"Created experiment {experiment.id}: {name}")
        
        return experiment
    
    def stop_experiment(self, experiment_id: str) -> None:
        """Stop an active experiment."""
        if experiment_id in self._experiments:
            self._experiments[experiment_id].status = "completed"
            self._experiments[experiment_id].end_time = datetime.utcnow()
            logger.info(f"Stopped experiment {experiment_id}")
    
    def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get results for an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        return {
            "experiment": {
                "id": exp.id,
                "name": exp.name,
                "model_name": exp.model_name,
                "control_version": exp.control_version,
                "treatment_version": exp.treatment_version,
                "traffic_split": exp.traffic_split,
                "status": exp.status,
            },
            "metrics": dict(exp.metrics),
        }
    
    def record_feedback(
        self,
        entity_id: str,
        model_name: str,
        model_version: str,
        actual_value: float,
        prediction_timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record actual outcome for prediction feedback.
        
        Used for online learning and model evaluation.
        """
        # Store feedback for later analysis
        feedback = {
            "entity_id": entity_id,
            "model_name": model_name,
            "model_version": model_version,
            "predicted_at": prediction_timestamp or datetime.utcnow(),
            "actual_value": actual_value,
            "recorded_at": datetime.utcnow(),
        }
        
        # In production, this would write to a database or queue
        logger.debug(f"Recorded feedback: {feedback}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        avg_latency = self._latency_sum / self._prediction_count if self._prediction_count > 0 else 0
        
        return {
            "predictions_total": self._prediction_count,
            "errors_total": self._error_count,
            "average_latency_ms": avg_latency,
            "cache_stats": self.cache.stats(),
            "active_experiments": len([e for e in self._experiments.values() if e.status == "running"]),
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "cache_stats": self.cache.stats(),
            "metrics": self.get_metrics(),
        }


class BatchPredictionJob:
    """Batch prediction job for offline scoring."""
    
    def __init__(
        self,
        job_id: str,
        model_name: str,
        model_version: str,
        input_path: str,
        output_path: str,
        service: InferenceService,
    ):
        self.job_id = job_id
        self.model_name = model_name
        self.model_version = model_version
        self.input_path = input_path
        self.output_path = output_path
        self.service = service
        
        self.status = "pending"
        self.progress = 0.0
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.records_processed = 0
        self.records_total = 0
    
    def run(self) -> None:
        """Execute batch prediction job."""
        self.status = "running"
        logger.info(f"Starting batch job {self.job_id}")
        
        try:
            # Load input data
            input_df = pd.read_parquet(self.input_path)
            self.records_total = len(input_df)
            
            # Get entity column
            entity_col = "entity_id"
            if entity_col not in input_df.columns:
                entity_col = input_df.columns[0]
            
            # Process in batches
            batch_size = 1000
            results = []
            
            for i in range(0, len(input_df), batch_size):
                batch = input_df.iloc[i:i+batch_size]
                entity_ids = batch[entity_col].tolist()
                
                # Generate predictions
                predictions = self.service.predict_batch(
                    entity_ids=entity_ids,
                    model_name=self.model_name,
                    model_version=self.model_version,
                    features_df=batch,
                )
                
                # Collect results
                for pred in predictions:
                    results.append({
                        "entity_id": pred.entity_id,
                        "prediction": pred.value,
                        "timestamp": pred.timestamp,
                    })
                
                self.records_processed += len(batch)
                self.progress = self.records_processed / self.records_total
            
            # Save results
            output_df = pd.DataFrame(results)
            output_df.to_parquet(self.output_path, index=False)
            
            self.status = "completed"
            self.completed_at = datetime.utcnow()
            
            logger.info(f"Batch job {self.job_id} completed: {self.records_processed} records")
            
        except Exception as e:
            self.status = "failed"
            logger.error(f"Batch job {self.job_id} failed: {e}")
            raise
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "status": self.status,
            "progress": self.progress,
            "records_processed": self.records_processed,
            "records_total": self.records_total,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class BatchPredictionScheduler:
    """Scheduler for batch prediction jobs."""
    
    def __init__(self, service: InferenceService):
        self.service = service
        self._jobs: Dict[str, BatchPredictionJob] = {}
        self._scheduled: List[Dict] = []
    
    def submit_job(
        self,
        model_name: str,
        model_version: str,
        input_path: str,
        output_path: str,
    ) -> str:
        """Submit a batch prediction job."""
        job_id = str(uuid.uuid4())[:8]
        
        job = BatchPredictionJob(
            job_id=job_id,
            model_name=model_name,
            model_version=model_version,
            input_path=input_path,
            output_path=output_path,
            service=self.service,
        )
        
        self._jobs[job_id] = job
        
        # Run asynchronously (in production, use a task queue)
        import threading
        thread = threading.Thread(target=job.run)
        thread.start()
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status of a batch job."""
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None
    
    def schedule_periodic(
        self,
        model_name: str,
        model_version: str,
        input_query: str,
        output_path: str,
        schedule: str,  # cron expression or "daily", "hourly"
    ) -> str:
        """Schedule a recurring batch prediction job."""
        schedule_id = str(uuid.uuid4())[:8]
        
        self._scheduled.append({
            "schedule_id": schedule_id,
            "model_name": model_name,
            "model_version": model_version,
            "input_query": input_query,
            "output_path": output_path,
            "schedule": schedule,
        })
        
        return schedule_id


# =============================================================================
# Convenience Functions
# =============================================================================

def create_inference_service(
    registry: Any,
    feature_store: Optional[Any] = None,
    cache_size: int = 100,
) -> InferenceService:
    """Create a configured inference service."""
    return InferenceService(
        registry=registry,
        feature_store=feature_store,
        cache_size=cache_size,
    )


def create_price_prediction_service(
    model_name: str = "price_predictor",
    registry: Any = None,
    feature_store: Any = None,
) -> InferenceService:
    """Create inference service for price prediction."""
    return create_inference_service(registry, feature_store)


def create_regime_detection_service(
    model_name: str = "regime_detector",
    registry: Any = None,
    feature_store: Any = None,
) -> InferenceService:
    """Create inference service for regime detection."""
    return create_inference_service(registry, feature_store)
