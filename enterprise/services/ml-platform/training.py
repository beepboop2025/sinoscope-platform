"""
DragonScope Training Pipeline

End-to-end training orchestration with time-series cross-validation,
hyperparameter tuning, and comprehensive evaluation.
"""

from __future__ import annotations

import json
import logging
import pickle
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Iterator
import time

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, log_loss, classification_report,
)

logger = logging.getLogger(__name__)

# Optional imports for advanced features
try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


class ProblemType(Enum):
    """Types of ML problems."""
    REGRESSION = auto()
    CLASSIFICATION = auto()
    TIME_SERIES = auto()
    ANOMALY_DETECTION = auto()


class ValidationStrategy(Enum):
    """Cross-validation strategies for time series."""
    WALK_FORWARD = "walk_forward"  # Expanding window
    SLIDING_WINDOW = "sliding_window"  # Fixed window
    PURGED_KFOLD = "purged_kfold"  # Purged cross-validation
    COMBINATORIAL = "combinatorial"  # Combinatorial purged CV


@dataclass
class CVSplit:
    """A single cross-validation split."""
    train_start: datetime
    train_end: datetime
    val_start: datetime
    val_end: datetime
    fold: int
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "val_start": self.val_start.isoformat(),
            "val_end": self.val_end.isoformat(),
            "fold": self.fold,
        }


@dataclass
class TrainingConfig:
    """Configuration for training pipeline."""
    # Data
    target_column: str = "target"
    feature_columns: List[str] = field(default_factory=list)
    date_column: str = "timestamp"
    entity_column: str = "entity_id"
    
    # Validation
    cv_strategy: ValidationStrategy = ValidationStrategy.WALK_FORWARD
    n_splits: int = 5
    test_size: float = 0.2
    embargo_pct: float = 0.01  # Purge overlap between train/test
    
    # Preprocessing
    scaler_type: str = "robust"  # standard, robust, none
    handle_missing: str = "forward_fill"  # forward_fill, interpolate, drop
    outlier_method: str = "winsorize"  # winsorize, remove, none
    outlier_threshold: float = 3.0
    
    # Training
    random_state: int = 42
    early_stopping_rounds: int = 50
    
    # Hyperparameter tuning
    enable_tuning: bool = False
    n_trials: int = 100
    tuning_metric: str = "val_loss"
    timeout_seconds: Optional[int] = None
    
    # Model-specific
    class_weight: Optional[str] = "balanced"
    sample_weight: Optional[str] = None  # Column name for sample weights
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "cv_strategy": self.cv_strategy.value,
        }


@dataclass
class FoldResult:
    """Results from a single CV fold."""
    fold: int
    train_metrics: Dict[str, float]
    val_metrics: Dict[str, float]
    feature_importance: Optional[Dict[str, float]] = None
    train_predictions: Optional[np.ndarray] = None
    val_predictions: Optional[np.ndarray] = None
    training_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fold": self.fold,
            "train_metrics": self.train_metrics,
            "val_metrics": self.val_metrics,
            "feature_importance": self.feature_importance,
            "training_time_seconds": self.training_time_seconds,
        }


@dataclass
class TrainingResult:
    """Complete training results."""
    model_name: str
    model_version: str
    config: TrainingConfig
    
    # Results
    fold_results: List[FoldResult]
    aggregated_metrics: Dict[str, Dict[str, float]]
    
    # Final model
    final_model: Any = None
    scaler: Any = None
    feature_columns: List[str] = field(default_factory=list)
    
    # Metadata
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    total_training_time: float = 0.0
    best_hyperparameters: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "config": self.config.to_dict(),
            "fold_results": [f.to_dict() for f in self.fold_results],
            "aggregated_metrics": self.aggregated_metrics,
            "feature_columns": self.feature_columns,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_training_time": self.total_training_time,
            "best_hyperparameters": self.best_hyperparameters,
        }
    
    @property
    def best_fold(self) -> Optional[FoldResult]:
        """Get the best performing fold."""
        if not self.fold_results:
            return None
        
        # For regression, use lowest RMSE; for classification, use highest AUC
        metric = "rmse" if "rmse" in self.fold_results[0].val_metrics else "auc"
        
        if metric == "rmse":
            return min(self.fold_results, key=lambda x: x.val_metrics.get("rmse", float("inf")))
        else:
            return max(self.fold_results, key=lambda x: x.val_metrics.get("auc", 0))


class DataPreprocessor:
    """Data preprocessing for financial time series."""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.scaler = None
        self._fit_data = None
    
    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit preprocessor and transform data."""
        df = df.copy()
        
        # Handle missing values
        df = self._handle_missing(df)
        
        # Handle outliers
        df = self._handle_outliers(df)
        
        # Fit scaler
        feature_cols = self.config.feature_columns or [
            c for c in df.columns
            if c not in [self.config.target_column, self.config.date_column, self.config.entity_column]
        ]
        
        if self.config.scaler_type == "standard":
            self.scaler = StandardScaler()
        elif self.config.scaler_type == "robust":
            self.scaler = RobustScaler()
        
        if self.scaler:
            df[feature_cols] = self.scaler.fit_transform(df[feature_cols])
        
        return df
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform data using fitted preprocessor."""
        df = df.copy()
        
        df = self._handle_missing(df)
        df = self._handle_outliers(df)
        
        feature_cols = self.config.feature_columns or [
            c for c in df.columns
            if c not in [self.config.target_column, self.config.date_column, self.config.entity_column]
        ]
        
        if self.scaler:
            df[feature_cols] = self.scaler.transform(df[feature_cols])
        
        return df
    
    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values."""
        method = self.config.handle_missing
        
        if method == "forward_fill":
            df = df.sort_values(self.config.date_column)
            df = df.groupby(self.config.entity_column).ffill()
            df = df.fillna(0)  # Fill remaining with 0
        elif method == "interpolate":
            df = df.sort_values(self.config.date_column)
            df = df.groupby(self.config.entity_column).apply(
                lambda x: x.interpolate(method="linear").fillna(method="bfill").fillna(method="ffill")
            )
        elif method == "drop":
            df = df.dropna()
        
        return df
    
    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle outliers."""
        method = self.config.outlier_method
        
        if method == "none":
            return df
        
        feature_cols = self.config.feature_columns or [
            c for c in df.columns
            if c not in [self.config.target_column, self.config.date_column, self.config.entity_column]
            and df[c].dtype in [np.float64, np.float32, np.int64]
        ]
        
        if method == "winsorize":
            for col in feature_cols:
                lower = df[col].quantile(0.01)
                upper = df[col].quantile(0.99)
                df[col] = df[col].clip(lower, upper)
        elif method == "remove":
            # Only for training, mark rows to remove
            mask = pd.Series(True, index=df.index)
            for col in feature_cols:
                mean = df[col].mean()
                std = df[col].std()
                threshold = self.config.outlier_threshold * std
                mask &= (df[col] - mean).abs() <= threshold
            df = df[mask]
        
        return df


class TimeSeriesCV:
    """Time series cross-validation with purging and embargo."""
    
    def __init__(
        self,
        n_splits: int = 5,
        test_size: float = 0.2,
        embargo_pct: float = 0.01,
        strategy: ValidationStrategy = ValidationStrategy.WALK_FORWARD,
    ):
        self.n_splits = n_splits
        self.test_size = test_size
        self.embargo_pct = embargo_pct
        self.strategy = strategy
    
    def split(
        self,
        df: pd.DataFrame,
        date_column: str = "timestamp",
    ) -> Iterator[Tuple[pd.DataFrame, pd.DataFrame, CVSplit]]:
        """Generate train/validation splits."""
        df = df.sort_values(date_column).reset_index(drop=True)
        dates = pd.to_datetime(df[date_column])
        min_date, max_date = dates.min(), dates.max()
        total_days = (max_date - min_date).days
        
        if self.strategy == ValidationStrategy.WALK_FORWARD:
            yield from self._walk_forward_splits(df, dates, min_date, total_days)
        elif self.strategy == ValidationStrategy.SLIDING_WINDOW:
            yield from self._sliding_window_splits(df, dates, min_date, total_days)
        else:
            yield from self._walk_forward_splits(df, dates, min_date, total_days)
    
    def _walk_forward_splits(
        self,
        df: pd.DataFrame,
        dates: pd.Series,
        min_date: datetime,
        total_days: int,
    ) -> Iterator[Tuple[pd.DataFrame, pd.DataFrame, CVSplit]]:
        """Generate expanding window splits."""
        test_days = int(total_days * self.test_size / self.n_splits)
        embargo_days = int(total_days * self.embargo_pct)
        
        for i in range(self.n_splits):
            # Validation period
            val_start_offset = total_days - (self.n_splits - i) * test_days
            val_end_offset = val_start_offset + test_days
            
            val_start = min_date + timedelta(days=val_start_offset)
            val_end = min_date + timedelta(days=val_end_offset)
            
            # Training period (everything before validation + embargo)
            train_end = val_start - timedelta(days=embargo_days)
            train_start = min_date
            
            train_mask = dates <= train_end
            val_mask = (dates >= val_start) & (dates < val_end)
            
            split_info = CVSplit(
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
                fold=i + 1,
            )
            
            yield df[train_mask], df[val_mask], split_info
    
    def _sliding_window_splits(
        self,
        df: pd.DataFrame,
        dates: pd.Series,
        min_date: datetime,
        total_days: int,
    ) -> Iterator[Tuple[pd.DataFrame, pd.DataFrame, CVSplit]]:
        """Generate fixed window splits."""
        window_days = int(total_days * (1 - self.test_size))
        test_days = int(total_days * self.test_size / self.n_splits)
        embargo_days = int(total_days * self.embargo_pct)
        
        for i in range(self.n_splits):
            val_start_offset = window_days + i * test_days
            val_end_offset = val_start_offset + test_days
            
            train_start = min_date + timedelta(days=i * test_days)
            train_end = min_date + timedelta(days=val_start_offset - embargo_days)
            val_start = min_date + timedelta(days=val_start_offset)
            val_end = min_date + timedelta(days=min(val_end_offset, total_days))
            
            train_mask = (dates >= train_start) & (dates <= train_end)
            val_mask = (dates >= val_start) & (dates < val_end)
            
            split_info = CVSplit(
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
                fold=i + 1,
            )
            
            yield df[train_mask], df[val_mask], split_info


class ModelTrainer(ABC):
    """Abstract base class for model trainers."""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
    
    @abstractmethod
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[np.ndarray] = None,
    ) -> Tuple[Any, Dict[str, float]]:
        """Train model and return trained model + metrics."""
        pass
    
    @abstractmethod
    def predict(self, model: Any, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions."""
        pass
    
    @abstractmethod
    def get_feature_importance(self, model: Any) -> Optional[Dict[str, float]]:
        """Get feature importance if available."""
        pass
    
    @abstractmethod
    def get_default_params(self) -> Dict[str, Any]:
        """Get default hyperparameters."""
        pass
    
    @abstractmethod
    def get_param_space(self, trial: Any) -> Dict[str, Any]:
        """Get hyperparameter search space for Optuna."""
        pass


class LightGBMTrainer(ModelTrainer):
    """LightGBM model trainer."""
    
    def __init__(
        self,
        config: TrainingConfig,
        problem_type: ProblemType = ProblemType.REGRESSION,
    ):
        super().__init__(config)
        self.problem_type = problem_type
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[np.ndarray] = None,
    ) -> Tuple[Any, Dict[str, float]]:
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm required for LightGBMTrainer")
        
        params = self.get_default_params()
        
        if self.problem_type == ProblemType.REGRESSION:
            params["objective"] = "regression"
            params["metric"] = "rmse"
        elif self.problem_type == ProblemType.CLASSIFICATION:
            params["objective"] = "binary" if y_train.nunique() == 2 else "multiclass"
            params["metric"] = "auc" if y_train.nunique() == 2 else "multi_logloss"
        
        train_data = lgb.Dataset(X_train, label=y_train, weight=sample_weight)
        valid_sets = [train_data]
        valid_names = ["train"]
        
        if X_val is not None and y_val is not None:
            val_data = lgb.Dataset(X_val, label=y_val)
            valid_sets.append(val_data)
            valid_names.append("valid")
        
        model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=[lgb.early_stopping(self.config.early_stopping_rounds, verbose=False)],
        )
        
        metrics = {
            "best_iteration": model.best_iteration,
            "best_score": model.best_score,
        }
        
        return model, metrics
    
    def predict(self, model: Any, X: pd.DataFrame) -> np.ndarray:
        return model.predict(X, num_iteration=model.best_iteration)
    
    def get_feature_importance(self, model: Any) -> Optional[Dict[str, float]]:
        importance = model.feature_importance(importance_type="gain")
        return dict(zip(model.feature_name(), importance))
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "random_state": self.config.random_state,
        }
    
    def get_param_space(self, trial: Any) -> Dict[str, Any]:
        return {
            "num_leaves": trial.suggest_int("num_leaves", 20, 150),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.6, 1.0),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.6, 1.0),
            "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        }


class XGBoostTrainer(ModelTrainer):
    """XGBoost model trainer."""
    
    def __init__(
        self,
        config: TrainingConfig,
        problem_type: ProblemType = ProblemType.REGRESSION,
    ):
        super().__init__(config)
        self.problem_type = problem_type
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[np.ndarray] = None,
    ) -> Tuple[Any, Dict[str, float]]:
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost required for XGBoostTrainer")
        
        params = self.get_default_params()
        
        if self.problem_type == ProblemType.REGRESSION:
            params["objective"] = "reg:squarederror"
        elif self.problem_type == ProblemType.CLASSIFICATION:
            params["objective"] = "binary:logistic" if y_train.nunique() == 2 else "multi:softprob"
        
        dtrain = xgb.DMatrix(X_train, label=y_train, weight=sample_weight)
        
        evals = [(dtrain, "train")]
        if X_val is not None and y_val is not None:
            dval = xgb.DMatrix(X_val, label=y_val)
            evals.append((dval, "eval"))
        
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=1000,
            evals=evals,
            early_stopping_rounds=self.config.early_stopping_rounds,
            verbose_eval=False,
        )
        
        metrics = {
            "best_iteration": model.best_iteration,
            "best_score": model.best_score,
        }
        
        return model, metrics
    
    def predict(self, model: Any, X: pd.DataFrame) -> np.ndarray:
        return model.predict(xgb.DMatrix(X))
    
    def get_feature_importance(self, model: Any) -> Optional[Dict[str, float]]:
        importance = model.get_score(importance_type="gain")
        return importance
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": self.config.random_state,
        }
    
    def get_param_space(self, trial: Any) -> Dict[str, Any]:
        return {
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "gamma": trial.suggest_float("gamma", 1e-8, 1.0, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        }


class TrainingPipeline:
    """
    End-to-end training pipeline for financial ML models.
    
    Features:
    - Time-series aware cross-validation
    - Automated preprocessing
    - Hyperparameter tuning with Optuna
    - Comprehensive evaluation metrics
    """
    
    def __init__(
        self,
        name: str,
        model_type: ProblemType,
        trainer: Optional[ModelTrainer] = None,
        config: Optional[TrainingConfig] = None,
        feature_store: Optional[Any] = None,
        registry: Optional[Any] = None,
    ):
        self.name = name
        self.model_type = model_type
        self.config = config or TrainingConfig()
        self.trainer = trainer
        self.feature_store = feature_store
        self.registry = registry
        
        self._results: Optional[TrainingResult] = None
    
    def add_features(self, feature_names: List[str]) -> None:
        """Add features to the training configuration."""
        self.config.feature_columns = feature_names
    
    def train(
        self,
        data: Optional[pd.DataFrame] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        hyperparameter_tuning: bool = False,
        cv_folds: Optional[int] = None,
    ) -> TrainingResult:
        """
        Execute the training pipeline.
        
        Args:
            data: Training data (or fetch from feature_store)
            start_date: Data start date
            end_date: Data end date
            hyperparameter_tuning: Enable Optuna hyperparameter tuning
            cv_folds: Override number of CV folds
        
        Returns:
            TrainingResult with all metrics and artifacts
        """
        start_time = time.time()
        
        if cv_folds:
            self.config.n_splits = cv_folds
        
        # Load data
        if data is None and self.feature_store:
            data = self._load_from_feature_store(start_date, end_date)
        elif data is None:
            raise ValueError("Either data or feature_store must be provided")
        
        logger.info(f"Training {self.name} on {len(data)} samples")
        
        # Hyperparameter tuning
        if hyperparameter_tuning and OPTUNA_AVAILABLE:
            best_params = self._tune_hyperparameters(data)
            self.config.best_hyperparameters = best_params
        
        # Cross-validation training
        cv = TimeSeriesCV(
            n_splits=self.config.n_splits,
            test_size=self.config.test_size,
            embargo_pct=self.config.embargo_pct,
            strategy=self.config.cv_strategy,
        )
        
        fold_results = []
        models = []
        scalers = []
        
        for fold_idx, (train_df, val_df, split_info) in enumerate(cv.split(data)):
            logger.info(f"Training fold {fold_idx + 1}/{self.config.n_splits}")
            
            fold_result, model, scaler = self._train_fold(train_df, val_df, split_info)
            fold_results.append(fold_result)
            models.append(model)
            scalers.append(scaler)
        
        # Aggregate metrics
        aggregated = self._aggregate_metrics(fold_results)
        
        # Train final model on all data
        final_model, final_scaler = self._train_final_model(data)
        
        # Create result
        self._results = TrainingResult(
            model_name=self.name,
            model_version="1.0.0",  # Will be updated on registration
            config=self.config,
            fold_results=fold_results,
            aggregated_metrics=aggregated,
            final_model=final_model,
            scaler=final_scaler,
            feature_columns=self.config.feature_columns,
            end_time=datetime.utcnow(),
            total_training_time=time.time() - start_time,
            best_hyperparameters=self.config.best_hyperparameters,
        )
        
        logger.info(f"Training complete in {self._results.total_training_time:.1f}s")
        
        return self._results
    
    def _load_from_feature_store(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> pd.DataFrame:
        """Load training data from feature store."""
        # This would integrate with the actual feature store
        raise NotImplementedError("Feature store integration not implemented")
    
    def _train_fold(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        split_info: CVSplit,
    ) -> Tuple[FoldResult, Any, Any]:
        """Train a single CV fold."""
        fold_start = time.time()
        
        # Preprocess
        preprocessor = DataPreprocessor(self.config)
        train_processed = preprocessor.fit_transform(train_df)
        val_processed = preprocessor.transform(val_df)
        
        # Prepare features
        feature_cols = self.config.feature_columns or [
            c for c in train_processed.columns
            if c not in [
                self.config.target_column,
                self.config.date_column,
                self.config.entity_column,
            ]
        ]
        
        X_train = train_processed[feature_cols]
        y_train = train_processed[self.config.target_column]
        X_val = val_processed[feature_cols]
        y_val = val_processed[self.config.target_column]
        
        # Get sample weights if configured
        sample_weight = None
        if self.config.sample_weight and self.config.sample_weight in train_processed.columns:
            sample_weight = train_processed[self.config.sample_weight].values
        
        # Train model
        if self.trainer is None:
            self.trainer = LightGBMTrainer(self.config, self.model_type)
        
        model, train_metrics = self.trainer.train(
            X_train, y_train, X_val, y_val, sample_weight
        )
        
        # Predictions and metrics
        train_preds = self.trainer.predict(model, X_train)
        val_preds = self.trainer.predict(model, X_val)
        
        train_eval = self._compute_metrics(y_train, train_preds)
        val_eval = self._compute_metrics(y_val, val_preds)
        
        # Feature importance
        feature_importance = self.trainer.get_feature_importance(model)
        
        fold_result = FoldResult(
            fold=split_info.fold,
            train_metrics=train_eval,
            val_metrics=val_eval,
            feature_importance=feature_importance,
            train_predictions=train_preds,
            val_predictions=val_preds,
            training_time_seconds=time.time() - fold_start,
        )
        
        return fold_result, model, preprocessor.scaler
    
    def _compute_metrics(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
    ) -> Dict[str, float]:
        """Compute evaluation metrics."""
        metrics = {}
        
        if self.model_type == ProblemType.REGRESSION:
            metrics["mse"] = mean_squared_error(y_true, y_pred)
            metrics["rmse"] = np.sqrt(metrics["mse"])
            metrics["mae"] = mean_absolute_error(y_true, y_pred)
            metrics["mape"] = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
            metrics["r2"] = r2_score(y_true, y_pred)
            
            # Financial metrics
            metrics["directional_accuracy"] = np.mean(
                np.sign(y_true) == np.sign(y_pred)
            )
            
        elif self.model_type == ProblemType.CLASSIFICATION:
            if len(np.unique(y_true)) == 2:
                metrics["accuracy"] = accuracy_score(y_true, (y_pred > 0.5).astype(int))
                metrics["precision"] = precision_score(y_true, (y_pred > 0.5).astype(int), zero_division=0)
                metrics["recall"] = recall_score(y_true, (y_pred > 0.5).astype(int), zero_division=0)
                metrics["f1"] = f1_score(y_true, (y_pred > 0.5).astype(int), zero_division=0)
                metrics["auc"] = roc_auc_score(y_true, y_pred)
                metrics["logloss"] = log_loss(y_true, y_pred)
            else:
                metrics["accuracy"] = accuracy_score(y_true, np.argmax(y_pred, axis=1))
        
        return metrics
    
    def _aggregate_metrics(
        self,
        fold_results: List[FoldResult],
    ) -> Dict[str, Dict[str, float]]:
        """Aggregate metrics across folds."""
        if not fold_results:
            return {}
        
        # Collect all metric names
        train_metrics = [fr.train_metrics for fr in fold_results]
        val_metrics = [fr.val_metrics for fr in fold_results]
        
        aggregated = {"train": {}, "val": {}}
        
        for metric_name in train_metrics[0].keys():
            values = [m[metric_name] for m in train_metrics if metric_name in m]
            aggregated["train"][f"{metric_name}_mean"] = np.mean(values)
            aggregated["train"][f"{metric_name}_std"] = np.std(values)
        
        for metric_name in val_metrics[0].keys():
            values = [m[metric_name] for m in val_metrics if metric_name in m]
            aggregated["val"][f"{metric_name}_mean"] = np.mean(values)
            aggregated["val"][f"{metric_name}_std"] = np.std(values)
        
        return aggregated
    
    def _train_final_model(self, data: pd.DataFrame) -> Tuple[Any, Any]:
        """Train final model on all data."""
        preprocessor = DataPreprocessor(self.config)
        processed = preprocessor.fit_transform(data)
        
        feature_cols = self.config.feature_columns or [
            c for c in processed.columns
            if c not in [
                self.config.target_column,
                self.config.date_column,
                self.config.entity_column,
            ]
        ]
        
        X = processed[feature_cols]
        y = processed[self.config.target_column]
        
        sample_weight = None
        if self.config.sample_weight and self.config.sample_weight in processed.columns:
            sample_weight = processed[self.config.sample_weight].values
        
        model, _ = self.trainer.train(X, y, sample_weight=sample_weight)
        
        return model, preprocessor.scaler
    
    def _tune_hyperparameters(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Run hyperparameter tuning with Optuna."""
        if not OPTUNA_AVAILABLE:
            logger.warning("Optuna not available, skipping hyperparameter tuning")
            return {}
        
        def objective(trial):
            # Create trainer with trial params
            params = self.trainer.get_param_space(trial)
            
            # Quick CV to evaluate
            cv = TimeSeriesCV(n_splits=3, test_size=0.2)
            scores = []
            
            for train_df, val_df, _ in cv.split(data):
                preprocessor = DataPreprocessor(self.config)
                train_processed = preprocessor.fit_transform(train_df)
                val_processed = preprocessor.transform(val_df)
                
                feature_cols = self.config.feature_columns or [
                    c for c in train_processed.columns
                    if c not in [
                        self.config.target_column,
                        self.config.date_column,
                        self.config.entity_column,
                    ]
                ]
                
                X_train = train_processed[feature_cols]
                y_train = train_processed[self.config.target_column]
                X_val = val_processed[feature_cols]
                y_val = val_processed[self.config.target_column]
                
                # Create temporary trainer with trial params
                temp_trainer = type(self.trainer)(self.config, self.model_type)
                temp_trainer.get_default_params = lambda: {**self.trainer.get_default_params(), **params}
                
                try:
                    model, _ = temp_trainer.train(X_train, y_train, X_val, y_val)
                    preds = temp_trainer.predict(model, X_val)
                    
                    if self.model_type == ProblemType.REGRESSION:
                        score = -mean_squared_error(y_val, preds)  # Negative for minimization
                    else:
                        score = roc_auc_score(y_val, preds)
                    
                    scores.append(score)
                except Exception as e:
                    logger.warning(f"Trial failed: {e}")
                    return float("-inf")
            
            return np.mean(scores)
        
        study = optuna.create_study(direction="maximize")
        study.optimize(
            objective,
            n_trials=self.config.n_trials,
            timeout=self.config.timeout_seconds,
            show_progress_bar=True,
        )
        
        logger.info(f"Best hyperparameters: {study.best_params}")
        return study.best_params
    
    def register(
        self,
        stage: str = "staging",
        metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[Any]:
        """
        Register the trained model.
        
        Args:
            stage: Initial stage (development, staging, production)
            metrics: Additional metrics to register
        
        Returns:
            Registered model version
        """
        if self._results is None:
            raise ValueError("Must train model before registration")
        
        if self.registry is None:
            logger.warning("No registry configured, skipping registration")
            return None
        
        # Convert to registry metrics
        from model_registry import ModelMetrics
        
        registry_metrics = ModelMetrics()
        agg = self._results.aggregated_metrics.get("val", {})
        registry_metrics.rmse = agg.get("rmse_mean")
        registry_metrics.mae = agg.get("mae_mean")
        registry_metrics.r2 = agg.get("r2_mean")
        
        # Register
        version = self.registry.register_version(
            name=self.name,
            model_type=self._get_model_type(),
            algorithm=self._get_algorithm(),
            model_object={
                "model": self._results.final_model,
                "scaler": self._results.scaler,
                "feature_columns": self._results.feature_columns,
            },
            metrics=registry_metrics,
            params=self.config.best_hyperparameters or {},
            description=f"Trained with {self.config.cv_strategy.value} CV",
        )
        
        # Transition to requested stage
        from model_registry import ModelStage
        stage_enum = ModelStage(stage.upper())
        version = self.registry.transition_stage(
            self.name, version.version, stage_enum, "Auto-registered from training pipeline"
        )
        
        logger.info(f"Registered {self.name} v{version.version} to {stage}")
        return version
    
    def _get_model_type(self):
        """Convert problem type to registry model type."""
        from model_registry import ModelType
        type_map = {
            ProblemType.REGRESSION: ModelType.PRICE_PREDICTION,
            ProblemType.CLASSIFICATION: ModelType.REGIME_DETECTION,
            ProblemType.ANOMALY_DETECTION: ModelType.ANOMALY_DETECTION,
        }
        return type_map.get(self.model_type, ModelType.PRICE_PREDICTION)
    
    def _get_algorithm(self):
        """Get algorithm type from trainer."""
        from model_registry import AlgorithmType
        if isinstance(self.trainer, LightGBMTrainer):
            return AlgorithmType.LIGHTGBM
        elif isinstance(self.trainer, XGBoostTrainer):
            return AlgorithmType.XGBOOST
        return AlgorithmType.LIGHTGBM
    
    def save(self, path: str) -> None:
        """Save training results to disk."""
        if self._results is None:
            raise ValueError("No training results to save")
        
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        with open(save_path / "metadata.json", "w") as f:
            json.dump(self._results.to_dict(), f, indent=2, default=str)
        
        # Save model
        with open(save_path / "model.pkl", "wb") as f:
            pickle.dump(self._results.final_model, f)
        
        # Save scaler
        with open(save_path / "scaler.pkl", "wb") as f:
            pickle.dump(self._results.scaler, f)
        
        logger.info(f"Saved training results to {save_path}")


# =============================================================================
# Convenience Functions
# =============================================================================

def create_price_prediction_pipeline(
    name: str,
    features: List[str],
    registry: Optional[Any] = None,
) -> TrainingPipeline:
    """Create a price prediction training pipeline."""
    config = TrainingConfig(
        target_column="forward_return",
        feature_columns=features,
        cv_strategy=ValidationStrategy.WALK_FORWARD,
        n_splits=5,
        scaler_type="robust",
        enable_tuning=True,
        n_trials=50,
    )
    
    return TrainingPipeline(
        name=name,
        model_type=ProblemType.REGRESSION,
        trainer=LightGBMTrainer(config, ProblemType.REGRESSION),
        config=config,
        registry=registry,
    )


def create_regime_detection_pipeline(
    name: str,
    features: List[str],
    registry: Optional[Any] = None,
) -> TrainingPipeline:
    """Create a regime detection training pipeline."""
    config = TrainingConfig(
        target_column="regime",
        feature_columns=features,
        cv_strategy=ValidationStrategy.WALK_FORWARD,
        n_splits=5,
        scaler_type="robust",
        class_weight="balanced",
    )
    
    return TrainingPipeline(
        name=name,
        model_type=ProblemType.CLASSIFICATION,
        trainer=LightGBMTrainer(config, ProblemType.CLASSIFICATION),
        config=config,
        registry=registry,
    )


def create_anomaly_detection_pipeline(
    name: str,
    features: List[str],
    registry: Optional[Any] = None,
) -> TrainingPipeline:
    """Create an anomaly detection training pipeline."""
    config = TrainingConfig(
        target_column="is_anomaly",
        feature_columns=features,
        cv_strategy=ValidationStrategy.SLIDING_WINDOW,
        n_splits=3,
        outlier_method="none",  # Don't remove outliers for anomaly detection
    )
    
    return TrainingPipeline(
        name=name,
        model_type=ProblemType.ANOMALY_DETECTION,
        config=config,
        registry=registry,
    )
