"""
DragonScope Feature Store

Enterprise feature store for financial ML with online/offline stores,
point-in-time correctness, and feature lineage tracking.
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict
import threading

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """Types of features supported."""
    NUMERIC = auto()
    CATEGORICAL = auto()
    BOOLEAN = auto()
    TIMESTAMP = auto()
    VECTOR = auto()


class FeatureCategory(Enum):
    """Categories of financial features."""
    PRICE = "price"
    TECHNICAL = "technical"
    ALTERNATIVE = "alternative"
    FUNDAMENTAL = "fundamental"
    MACRO = "macro"
    DERIVED = "derived"


class AggregationWindow(Enum):
    """Standard aggregation windows."""
    D1 = "1d"
    D5 = "5d"
    D10 = "10d"
    D20 = "20d"
    D30 = "30d"
    D60 = "60d"
    D90 = "90d"
    D252 = "252d"  # Trading year


@dataclass(frozen=True)
class FeatureDefinition:
    """Definition of a feature with metadata."""
    name: str
    category: FeatureCategory
    feature_type: FeatureType
    description: str
    entities: List[str]  # Entity types this feature applies to
    
    # Time window configuration
    window: Optional[AggregationWindow] = None
    aggregation: Optional[str] = None  # mean, std, min, max, ewma
    
    # Data quality
    null_threshold: float = 0.1  # Max allowed null ratio
    value_range: Optional[Tuple[float, float]] = None
    
    # Versioning
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    dependencies: List[str] = field(default_factory=list)
    
    @property
    def full_name(self) -> str:
        """Get fully qualified feature name."""
        return f"{self.category.value}.{self.name}"
    
    def compute_hash(self) -> str:
        """Compute hash for feature versioning."""
        content = f"{self.name}:{self.version}:{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class FeatureValue:
    """A computed feature value."""
    definition: FeatureDefinition
    entity_id: str
    timestamp: datetime
    value: Any
    
    # Metadata
    computed_at: datetime = field(default_factory=datetime.utcnow)
    data_source: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.definition.name,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "computed_at": self.computed_at.isoformat(),
        }


class FeatureView(BaseModel):
    """A collection of features for a specific use case."""
    name: str
    description: str
    entities: List[str]
    features: List[str]  # Feature full names
    ttl_seconds: int = 86400  # Feature freshness requirement
    
    # Point-in-time configuration
    event_timestamp_column: str = "timestamp"
    created_timestamp_column: str = "created_at"
    
    class Config:
        arbitrary_types_allowed = True


class Entity(BaseModel):
    """An entity that features are associated with."""
    name: str
    join_keys: List[str]  # Columns to join on
    description: str = ""


# =============================================================================
# Pre-defined Feature Definitions
# =============================================================================

PRICE_FEATURES = [
    FeatureDefinition(
        name="returns_1d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="1-day logarithmic return",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="returns_5d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="5-day logarithmic return",
        entities=["asset"],
        window=AggregationWindow.D5,
    ),
    FeatureDefinition(
        name="returns_21d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="21-day (monthly) logarithmic return",
        entities=["asset"],
        window=AggregationWindow.D30,
    ),
    FeatureDefinition(
        name="returns_63d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="63-day (quarterly) logarithmic return",
        entities=["asset"],
        window=AggregationWindow.D90,
    ),
    FeatureDefinition(
        name="volatility_20d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="20-day annualized volatility",
        entities=["asset"],
        window=AggregationWindow.D20,
        aggregation="std",
    ),
    FeatureDefinition(
        name="volatility_60d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="60-day annualized volatility",
        entities=["asset"],
        window=AggregationWindow.D60,
        aggregation="std",
    ),
    FeatureDefinition(
        name="price_momentum_10d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="10-day price momentum (current / 10d ago - 1)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="price_momentum_30d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="30-day price momentum",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="volume_ema_20d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="20-day exponential moving average of volume",
        entities=["asset"],
        window=AggregationWindow.D20,
        aggregation="ewma",
    ),
    FeatureDefinition(
        name="volume_ratio",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="Current volume / 20-day average volume",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="dollar_volume_20d",
        category=FeatureCategory.PRICE,
        feature_type=FeatureType.NUMERIC,
        description="20-day average dollar volume",
        entities=["asset"],
        window=AggregationWindow.D20,
        aggregation="mean",
    ),
]

TECHNICAL_FEATURES = [
    FeatureDefinition(
        name="rsi_14",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="14-day Relative Strength Index",
        entities=["asset"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="rsi_7",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="7-day Relative Strength Index",
        entities=["asset"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="macd",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="MACD line (12-day EMA - 26-day EMA)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="macd_signal",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="MACD signal line (9-day EMA of MACD)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="macd_histogram",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="MACD histogram (MACD - Signal)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="sma_20",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="20-day simple moving average ratio (price / SMA)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="sma_50",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="50-day simple moving average ratio",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="sma_200",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="200-day simple moving average ratio",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="ema_12",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="12-day exponential moving average ratio",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="ema_26",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="26-day exponential moving average ratio",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="bollinger_position",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="Position within Bollinger Bands (0=lower, 1=upper)",
        entities=["asset"],
        value_range=(0, 1),
    ),
    FeatureDefinition(
        name="bollinger_width",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="Bollinger Band width as % of middle band",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="atr_14",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="14-day Average True Range",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="adx_14",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="14-day Average Directional Index",
        entities=["asset"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="stoch_k",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="Stochastic Oscillator %K",
        entities=["asset"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="stoch_d",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="Stochastic Oscillator %D",
        entities=["asset"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="cci_20",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="20-day Commodity Channel Index",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="williams_r",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="Williams %R",
        entities=["asset"],
        value_range=(-100, 0),
    ),
    FeatureDefinition(
        name="mfi_14",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="14-day Money Flow Index",
        entities=["asset"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="obv",
        category=FeatureCategory.TECHNICAL,
        feature_type=FeatureType.NUMERIC,
        description="On-Balance Volume (normalized)",
        entities=["asset"],
    ),
]

ALTERNATIVE_DATA_FEATURES = [
    FeatureDefinition(
        name="sentiment_score",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Aggregate news sentiment score (-1 to +1)",
        entities=["asset"],
        value_range=(-1, 1),
    ),
    FeatureDefinition(
        name="sentiment_momentum_5d",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="5-day change in sentiment score",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="news_volume",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Number of news articles (normalized)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="news_volume_spike",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.BOOLEAN,
        description="Whether news volume is >2 std above mean",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="options_flow_bullish_ratio",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Ratio of bullish to total unusual options flow",
        entities=["asset"],
        value_range=(0, 1),
    ),
    FeatureDefinition(
        name="options_call_put_ratio",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Call/Put volume ratio",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="options_implied_move",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Expected move from options (IV-based)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="insider_buying_ratio",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Ratio of insider buys to total transactions",
        entities=["asset"],
        value_range=(0, 1),
    ),
    FeatureDefinition(
        name="insider_net_shares",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Net insider shares bought (buys - sells)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="social_media_mentions",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Social media mention count (normalized)",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="social_sentiment",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Social media sentiment score",
        entities=["asset"],
        value_range=(-1, 1),
    ),
    FeatureDefinition(
        name="short_interest_ratio",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Short interest as % of float",
        entities=["asset"],
    ),
    FeatureDefinition(
        name="borrow_cost",
        category=FeatureCategory.ALTERNATIVE,
        feature_type=FeatureType.NUMERIC,
        description="Cost to borrow shares (annualized %)",
        entities=["asset"],
    ),
]

MACRO_FEATURES = [
    FeatureDefinition(
        name="vix_level",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="VIX index level",
        entities=["global"],
    ),
    FeatureDefinition(
        name="vix_percentile_60d",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="VIX percentile over 60 days",
        entities=["global"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="yield_curve_slope",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="10Y - 2Y Treasury yield spread",
        entities=["global"],
    ),
    FeatureDefinition(
        name="yield_curve_inverted",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.BOOLEAN,
        description="Whether yield curve is inverted",
        entities=["global"],
    ),
    FeatureDefinition(
        name="dxy_strength",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="Dollar Index strength (percentile)",
        entities=["global"],
    ),
    FeatureDefinition(
        name="credit_spread_hy",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="High yield credit spread (bps)",
        entities=["global"],
    ),
    FeatureDefinition(
        name="credit_spread_ig",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="Investment grade credit spread (bps)",
        entities=["global"],
    ),
    FeatureDefinition(
        name="fed_futures_prob",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="Fed funds futures implied probability of hike",
        entities=["global"],
        value_range=(0, 1),
    ),
    FeatureDefinition(
        name="market_breadth",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="Percentage of stocks above 200-day MA",
        entities=["global"],
        value_range=(0, 100),
    ),
    FeatureDefinition(
        name="advance_decline_ratio",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="Advance/Decline ratio",
        entities=["global"],
    ),
    FeatureDefinition(
        name="sector_momentum_dispersion",
        category=FeatureCategory.MACRO,
        feature_type=FeatureType.NUMERIC,
        description="Cross-sector momentum dispersion",
        entities=["global"],
    ),
]

# Combined feature registry
ALL_FEATURES = (
    PRICE_FEATURES + 
    TECHNICAL_FEATURES + 
    ALTERNATIVE_DATA_FEATURES + 
    MACRO_FEATURES
)


# =============================================================================
# Storage Backends
# =============================================================================

class StorageBackend(ABC):
    """Abstract base for storage backends."""
    
    @abstractmethod
    def get_features(
        self,
        entity_ids: List[str],
        feature_names: List[str],
        timestamp: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Get features for entities at given timestamp."""
        pass
    
    @abstractmethod
    def set_features(
        self,
        entity_id: str,
        features: List[FeatureValue],
    ) -> None:
        """Store feature values."""
        pass
    
    @abstractmethod
    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_names: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Get historical features with point-in-time correctness."""
        pass


class InMemoryStorage(StorageBackend):
    """In-memory storage for testing and development."""
    
    def __init__(self):
        self._data: Dict[str, List[FeatureValue]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def get_features(
        self,
        entity_ids: List[str],
        feature_names: List[str],
        timestamp: Optional[datetime] = None,
    ) -> pd.DataFrame:
        timestamp = timestamp or datetime.utcnow()
        results = []
        
        with self._lock:
            for entity_id in entity_ids:
                entity_features = self._data.get(entity_id, [])
                
                # Find latest feature values before timestamp
                latest_values = {}
                for fv in entity_features:
                    if fv.definition.name in feature_names:
                        if fv.timestamp <= timestamp:
                            if fv.definition.name not in latest_values:
                                latest_values[fv.definition.name] = fv
                            elif fv.timestamp > latest_values[fv.definition.name].timestamp:
                                latest_values[fv.definition.name] = fv
                
                row = {"entity_id": entity_id}
                for name in feature_names:
                    fv = latest_values.get(name)
                    row[name] = fv.value if fv else None
                results.append(row)
        
        return pd.DataFrame(results)
    
    def set_features(
        self,
        entity_id: str,
        features: List[FeatureValue],
    ) -> None:
        with self._lock:
            self._data[entity_id].extend(features)
    
    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_names: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Point-in-time correct historical feature retrieval."""
        results = []
        
        with self._lock:
            for _, row in entity_df.iterrows():
                entity_id = row["entity_id"]
                event_timestamp = pd.to_datetime(row["timestamp"])
                
                entity_features = self._data.get(entity_id, [])
                
                # Get features valid at event_timestamp
                feature_values = {}
                for fv in entity_features:
                    if fv.definition.name in feature_names:
                        # Feature must be computed before event
                        if fv.timestamp <= event_timestamp:
                            if fv.definition.name not in feature_values:
                                feature_values[fv.definition.name] = fv
                            elif fv.timestamp > feature_values[fv.definition.name].timestamp:
                                feature_values[fv.definition.name] = fv
                
                result_row = {
                    "entity_id": entity_id,
                    "timestamp": event_timestamp,
                }
                for name in feature_names:
                    fv = feature_values.get(name)
                    result_row[name] = fv.value if fv else None
                
                # Filter by date range
                if start_date <= event_timestamp <= end_date:
                    results.append(result_row)
        
        return pd.DataFrame(results)


class RedisStorage(StorageBackend):
    """Redis-backed online feature store."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        try:
            import redis
            self._redis = redis.from_url(redis_url, decode_responses=True)
        except ImportError:
            raise ImportError("redis package required for RedisStorage")
    
    def _make_key(self, entity_id: str, feature_name: str) -> str:
        return f"features:{entity_id}:{feature_name}"
    
    def get_features(
        self,
        entity_ids: List[str],
        feature_names: List[str],
        timestamp: Optional[datetime] = None,
    ) -> pd.DataFrame:
        results = []
        
        for entity_id in entity_ids:
            row = {"entity_id": entity_id}
            
            # Use pipeline for efficiency
            pipe = self._redis.pipeline()
            keys = [self._make_key(entity_id, fn) for fn in feature_names]
            for key in keys:
                pipe.zrevrange(key, 0, 0, withscores=False)
            
            values = pipe.execute()
            
            for fname, val in zip(feature_names, values):
                if val:
                    row[fname] = json.loads(val[0])["value"]
                else:
                    row[fname] = None
            
            results.append(row)
        
        return pd.DataFrame(results)
    
    def set_features(
        self,
        entity_id: str,
        features: List[FeatureValue],
    ) -> None:
        pipe = self._redis.pipeline()
        
        for fv in features:
            key = self._make_key(entity_id, fv.definition.name)
            score = fv.timestamp.timestamp()
            value = json.dumps({
                "value": fv.value,
                "computed_at": fv.computed_at.isoformat(),
                "source": fv.data_source,
            })
            pipe.zadd(key, {value: score})
            
            # Set TTL for automatic expiration
            pipe.expire(key, 86400 * 30)  # 30 days
        
        pipe.execute()
    
    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_names: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        raise NotImplementedError("Use offline store for historical features")


# =============================================================================
# Feature Store
# =============================================================================

class FeatureStore:
    """
    Enterprise Feature Store for financial ML.
    
    Provides:
    - Online feature serving (low latency)
    - Offline feature retrieval (point-in-time correct)
    - Feature versioning and lineage
    - Automated aggregations
    """
    
    def __init__(
        self,
        online_store: Optional[StorageBackend] = None,
        offline_store: Optional[StorageBackend] = None,
    ):
        self._online = online_store or InMemoryStorage()
        self._offline = offline_store or InMemoryStorage()
        self._features: Dict[str, FeatureDefinition] = {
            f.full_name: f for f in ALL_FEATURES
        }
        self._views: Dict[str, FeatureView] = {}
        self._lineage: Dict[str, List[Dict]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def register_feature(self, definition: FeatureDefinition) -> None:
        """Register a new feature definition."""
        with self._lock:
            self._features[definition.full_name] = definition
            logger.info(f"Registered feature: {definition.full_name}")
    
    def get_feature_definition(self, name: str) -> Optional[FeatureDefinition]:
        """Get feature definition by full name."""
        return self._features.get(name)
    
    def list_features(
        self,
        category: Optional[FeatureCategory] = None,
        entity: Optional[str] = None,
    ) -> List[FeatureDefinition]:
        """List available features with optional filtering."""
        features = list(self._features.values())
        
        if category:
            features = [f for f in features if f.category == category]
        
        if entity:
            features = [f for f in features if entity in f.entities]
        
        return features
    
    def create_feature_view(self, view: FeatureView) -> None:
        """Create a feature view for a specific use case."""
        with self._lock:
            # Validate features exist
            for fname in view.features:
                if fname not in self._features:
                    raise ValueError(f"Unknown feature: {fname}")
            
            self._views[view.name] = view
            logger.info(f"Created feature view: {view.name}")
    
    def get_online_features(
        self,
        entity_ids: List[str],
        feature_names: List[str],
        timestamp: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Get latest feature values from online store.
        
        Args:
            entity_ids: List of entity identifiers
            feature_names: List of feature full names
            timestamp: Optional timestamp for historical point-in-time
        
        Returns:
            DataFrame with entity_id and feature columns
        """
        # Validate features
        for fname in feature_names:
            if fname not in self._features:
                raise ValueError(f"Unknown feature: {fname}")
        
        return self._online.get_features(entity_ids, feature_names, timestamp)
    
    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_names: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Get historical features with point-in-time correctness.
        
        This ensures no future leakage by only returning features
        that were computed before each event timestamp.
        
        Args:
            entity_df: DataFrame with entity_id and timestamp columns
            feature_names: List of feature full names
            start_date: Start of date range
            end_date: End of date range
        
        Returns:
            DataFrame with point-in-time correct features
        """
        # Validate features
        for fname in feature_names:
            if fname not in self._features:
                raise ValueError(f"Unknown feature: {fname}")
        
        return self._offline.get_historical_features(
            entity_df, feature_names, start_date, end_date
        )
    
    def ingest_features(
        self,
        entity_id: str,
        features: List[FeatureValue],
        store: str = "both",
    ) -> None:
        """
        Ingest computed features into storage.
        
        Args:
            entity_id: Entity identifier
            features: List of feature values
            store: Which store to write to ("online", "offline", "both")
        """
        # Validate and record lineage
        for fv in features:
            if fv.definition.full_name not in self._features:
                raise ValueError(f"Unknown feature: {fv.definition.full_name}")
            
            self._record_lineage(fv)
        
        if store in ("online", "both"):
            self._online.set_features(entity_id, features)
        
        if store in ("offline", "both"):
            self._offline.set_features(entity_id, features)
    
    def _record_lineage(self, feature_value: FeatureValue) -> None:
        """Record feature computation lineage."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "entity_id": feature_value.entity_id,
            "feature_timestamp": feature_value.timestamp.isoformat(),
            "computed_at": feature_value.computed_at.isoformat(),
            "source": feature_value.data_source,
            "version": feature_value.definition.version,
        }
        self._lineage[feature_value.definition.full_name].append(entry)
    
    def get_feature_lineage(
        self,
        feature_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict]:
        """Get computation lineage for a feature."""
        entries = self._lineage.get(feature_name, [])
        
        if start_time:
            entries = [e for e in entries 
                      if datetime.fromisoformat(e["timestamp"]) >= start_time]
        if end_time:
            entries = [e for e in entries 
                      if datetime.fromisoformat(e["timestamp"]) <= end_time]
        
        return entries
    
    def compute_feature(
        self,
        definition: FeatureDefinition,
        data: pd.DataFrame,
    ) -> pd.Series:
        """
        Compute a feature from raw data.
        
        Args:
            definition: Feature definition
            data: Raw data DataFrame
        
        Returns:
            Series with computed feature values
        """
        # Feature computation logic based on definition
        if definition.category == FeatureCategory.TECHNICAL:
            return self._compute_technical_feature(definition, data)
        elif definition.category == FeatureCategory.PRICE:
            return self._compute_price_feature(definition, data)
        else:
            raise NotImplementedError(
                f"Computation not implemented for {definition.category}"
            )
    
    def _compute_technical_feature(
        self,
        definition: FeatureDefinition,
        data: pd.DataFrame,
    ) -> pd.Series:
        """Compute technical indicator features."""
        name = definition.name
        
        if name == "rsi_14":
            return self._compute_rsi(data["close"], 14)
        elif name == "macd":
            return self._compute_macd(data["close"])
        elif name == "sma_20":
            return data["close"] / data["close"].rolling(20).mean()
        elif name == "bollinger_position":
            return self._compute_bollinger_position(data["close"])
        elif name == "atr_14":
            return self._compute_atr(data, 14)
        elif name == "adx_14":
            return self._compute_adx(data, 14)
        else:
            raise NotImplementedError(f"Technical feature {name} not implemented")
    
    def _compute_price_feature(
        self,
        definition: FeatureDefinition,
        data: pd.DataFrame,
    ) -> pd.Series:
        """Compute price-based features."""
        name = definition.name
        
        if name == "returns_1d":
            return np.log(data["close"] / data["close"].shift(1))
        elif name == "returns_5d":
            return np.log(data["close"] / data["close"].shift(5))
        elif name == "volatility_20d":
            returns = np.log(data["close"] / data["close"].shift(1))
            return returns.rolling(20).std() * np.sqrt(252)
        elif name == "volume_ratio":
            return data["volume"] / data["volume"].rolling(20).mean()
        else:
            raise NotImplementedError(f"Price feature {name} not implemented")
    
    def _compute_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Compute Relative Strength Index."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _compute_macd(
        self,
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
    ) -> pd.Series:
        """Compute MACD line."""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        return ema_fast - ema_slow
    
    def _compute_bollinger_position(
        self,
        prices: pd.Series,
        period: int = 20,
        std: int = 2,
    ) -> pd.Series:
        """Compute position within Bollinger Bands."""
        sma = prices.rolling(period).mean()
        upper = sma + std * prices.rolling(period).std()
        lower = sma - std * prices.rolling(period).std()
        return (prices - lower) / (upper - lower)
    
    def _compute_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Compute Average True Range."""
        high = data["high"]
        low = data["low"]
        close = data["close"]
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _compute_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Compute Average Directional Index."""
        high = data["high"]
        low = data["low"]
        close = data["close"]
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = self._compute_atr(data, period) * period
        plus_di = 100 * (plus_dm.rolling(period).sum() / tr)
        minus_di = 100 * (minus_dm.rolling(period).sum() / tr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(period).mean()
    
    def materialize_features(
        self,
        feature_names: List[str],
        entity_ids: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Materialize features for backfill or batch processing.
        
        Args:
            feature_names: Features to materialize
            entity_ids: Entities to process
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame with materialized features
        """
        # Create entity dataframe with all dates
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        entity_df = pd.DataFrame([
            {"entity_id": eid, "timestamp": ts}
            for eid in entity_ids
            for ts in date_range
        ])
        
        return self.get_historical_features(
            entity_df, feature_names, start_date, end_date
        )
    
    def validate_features(
        self,
        df: pd.DataFrame,
        feature_names: List[str],
    ) -> Dict[str, Any]:
        """
        Validate feature data quality.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {},
        }
        
        for fname in feature_names:
            if fname not in df.columns:
                results["errors"].append(f"Missing feature: {fname}")
                results["valid"] = False
                continue
            
            series = df[fname]
            definition = self._features.get(fname)
            
            if definition is None:
                continue
            
            # Check null ratio
            null_ratio = series.isnull().mean()
            if null_ratio > definition.null_threshold:
                results["warnings"].append(
                    f"{fname}: High null ratio ({null_ratio:.2%})"
                )
            
            # Check value range
            if definition.value_range and not series.isnull().all():
                min_val, max_val = definition.value_range
                out_of_range = ((series < min_val) | (series > max_val)).mean()
                if out_of_range > 0.01:  # >1% out of range
                    results["warnings"].append(
                        f"{fname}: {out_of_range:.2%} values out of range"
                    )
            
            # Compute statistics
            results["statistics"][fname] = {
                "mean": series.mean(),
                "std": series.std(),
                "min": series.min(),
                "max": series.max(),
                "null_ratio": null_ratio,
            }
        
        return results


# =============================================================================
# Convenience Functions
# =============================================================================

def create_default_feature_store(
    redis_url: Optional[str] = None,
) -> FeatureStore:
    """Create a feature store with default configuration."""
    online = RedisStorage(redis_url) if redis_url else InMemoryStorage()
    offline = InMemoryStorage()
    
    return FeatureStore(online_store=online, offline_store=offline)
