"""
DragonScope Signal Generation Engine

Generates actionable trading signals from NLP-processed news.
Includes price impact prediction, sentiment momentum, breaking news detection,
and rumor verification.
"""

import asyncio
import hashlib
import json
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import defaultdict, deque

import numpy as np
import redis.asyncio as redis
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of trading signals."""
    PRICE_IMPACT = "price_impact"
    SENTIMENT_MOMENTUM = "sentiment_momentum"
    BREAKING_NEWS = "breaking_news"
    RUMOR_VERIFIED = "rumor_verified"
    EARNINGS_SURPRISE = "earnings_surprise"
    MERGER_ACQUISITION = "merger_acquisition"
    REGULATORY = "regulatory"
    SECTOR_ROTATION = "sector_rotation"


class SignalDirection(Enum):
    """Signal direction."""
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


@dataclass
class Signal:
    """Trading signal output."""
    id: str
    timestamp: datetime
    signal_type: SignalType
    direction: SignalDirection
    ticker: str
    confidence: float  # 0.0 to 1.0
    
    # Signal metadata
    source_articles: List[str] = field(default_factory=list)
    time_horizon: str = "intraday"  # intraday, swing, long_term
    expected_return: Optional[float] = None  # Expected return percentage
    risk_level: str = "medium"  # low, medium, high
    
    # Rationale
    reasoning: str = ""
    key_factors: List[str] = field(default_factory=list)
    
    # Validation
    verified: bool = False
    verification_source: Optional[str] = None
    
    # Execution
    suggested_action: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique signal ID."""
        content = f"{self.ticker}{self.signal_type.value}{self.timestamp.isoformat()}"
        return f"sig_{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "signal_type": self.signal_type.value,
            "direction": self.direction.name,
            "ticker": self.ticker,
            "confidence": self.confidence,
            "source_articles": self.source_articles,
            "time_horizon": self.time_horizon,
            "expected_return": self.expected_return,
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "verified": self.verified,
            "verification_source": self.verification_source,
            "suggested_action": self.suggested_action,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit
        }


class BaseSignalGenerator(ABC):
    """Base class for signal generators."""
    
    def __init__(
        self,
        config: Dict[str, Any] = None,
        cache: redis.Redis = None
    ):
        self.config = config or {}
        self.cache = cache
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self.enabled = self.config.get("enabled", True)
    
    @abstractmethod
    async def generate(
        self, 
        nlp_result: Any,
        market_data: Optional[Dict] = None
    ) -> Optional[Signal]:
        """Generate signal from NLP result."""
        pass
    
    @abstractmethod
    def get_signal_type(self) -> SignalType:
        """Return signal type."""
        pass
    
    def _should_emit(self, confidence: float) -> bool:
        """Check if signal should be emitted based on confidence."""
        return confidence >= self.min_confidence and self.enabled


class NewsImpactScorer(BaseSignalGenerator):
    """
    Predicts price impact of news using ML models.
    
    Features:
    - Sentiment magnitude and confidence
    - Source credibility
    - Historical impact patterns
    - Market regime context
    - Entity importance
    
    Model: Gradient Boosting with custom financial features
    """
    
    def __init__(self, config: Dict[str, Any] = None, cache: redis.Redis = None):
        super().__init__(config, cache)
        
        # Source credibility scores
        self.source_credibility = {
            "Bloomberg": 0.95,
            "Reuters": 0.95,
            "CNBC": 0.85,
            "WSJ": 0.90,
            "SEC EDGAR": 1.0,
            "Twitter": 0.60,
            "Reddit": 0.40,
        }
        
        # Initialize ML model (simplified version)
        self.model = None
        self.scaler = StandardScaler()
        self._is_fitted = False
        
        if self.config.get("use_ml", False):
            self._init_model()
    
    def _init_model(self):
        """Initialize ML model."""
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1
        )
    
    def get_signal_type(self) -> SignalType:
        return SignalType.PRICE_IMPACT
    
    async def generate(
        self, 
        nlp_result: Any,
        market_data: Optional[Dict] = None
    ) -> Optional[Signal]:
        """
        Generate price impact signal.
        
        Args:
            nlp_result: NLP processing result
            market_data: Optional market context
            
        Returns:
            Signal if confidence threshold met
        """
        # Extract features
        features = self._extract_features(nlp_result)
        
        # Calculate impact score
        impact_score = self._calculate_impact(features)
        
        # Determine direction
        sentiment = getattr(nlp_result, 'sentiment_score', 0)
        if sentiment > 0.3:
            direction = SignalDirection.BULLISH
        elif sentiment < -0.3:
            direction = SignalDirection.BEARISH
        else:
            direction = SignalDirection.NEUTRAL
        
        # Check threshold
        if not self._should_emit(impact_score):
            return None
        
        # Get primary ticker
        tickers = getattr(nlp_result, 'tickers', [])
        ticker = tickers[0] if tickers else "UNKNOWN"
        
        # Determine time horizon based on impact score
        if impact_score > 0.85:
            time_horizon = "intraday"
        elif impact_score > 0.7:
            time_horizon = "swing"
        else:
            time_horizon = "long_term"
        
        # Generate reasoning
        reasoning = self._generate_reasoning(features, direction)
        
        # Calculate expected return (simplified model)
        expected_return = self._estimate_return(impact_score, direction)
        
        return Signal(
            id="",
            timestamp=datetime.now(),
            signal_type=self.get_signal_type(),
            direction=direction,
            ticker=ticker,
            confidence=impact_score,
            source_articles=[getattr(nlp_result, 'article_id', 'unknown')],
            time_horizon=time_horizon,
            expected_return=expected_return,
            risk_level=self._calculate_risk(features),
            reasoning=reasoning,
            key_factors=features.get("key_factors", []),
            suggested_action=self._suggest_action(direction, time_horizon)
        )
    
    def _extract_features(self, nlp_result: Any) -> Dict[str, Any]:
        """Extract features from NLP result."""
        features = {
            "sentiment_magnitude": abs(getattr(nlp_result, 'sentiment_score', 0)),
            "sentiment_confidence": getattr(nlp_result, 'sentiment_confidence', 0),
            "entity_count": len(getattr(nlp_result, 'entities', [])),
            "ticker_count": len(getattr(nlp_result, 'tickers', [])),
            "breaking_news_score": 0,
            "source_credibility": 0.5,
            "key_factors": []
        }
        
        # Check for breaking news indicators
        if hasattr(nlp_result, 'raw_scores'):
            sentiment_raw = nlp_result.raw_scores.get('sentiment', {})
            if sentiment_raw.get('positive', 0) > 0.8 or sentiment_raw.get('negative', 0) > 0.8:
                features["breaking_news_score"] = 1.0
                features["key_factors"].append("High sentiment polarity")
        
        # Entity-based features
        people = getattr(nlp_result, 'people', [])
        if people:
            features["key_factors"].append(f"Mentions: {', '.join(people[:2])}")
        
        companies = getattr(nlp_result, 'companies', [])
        if len(companies) > 1:
            features["key_factors"].append("Multiple companies mentioned")
        
        return features
    
    def _calculate_impact(self, features: Dict[str, Any]) -> float:
        """Calculate price impact score."""
        score = 0.0
        
        # Sentiment contribution (30%)
        score += features["sentiment_magnitude"] * 0.3
        
        # Confidence contribution (25%)
        score += features["sentiment_confidence"] * 0.25
        
        # Breaking news (20%)
        score += features["breaking_news_score"] * 0.2
        
        # Entity richness (15%)
        entity_score = min(features["entity_count"] / 10, 1.0)
        score += entity_score * 0.15
        
        # Source credibility (10%)
        score += features["source_credibility"] * 0.1
        
        return min(score, 1.0)
    
    def _generate_reasoning(
        self, 
        features: Dict[str, Any], 
        direction: SignalDirection
    ) -> str:
        """Generate human-readable reasoning."""
        direction_str = "positive" if direction == SignalDirection.BULLISH else \
                       "negative" if direction == SignalDirection.BEARISH else "neutral"
        
        reasoning_parts = [
            f"Detected {direction_str} sentiment with "
            f"{features['sentiment_confidence']:.0%} confidence."
        ]
        
        if features["breaking_news_score"] > 0.5:
            reasoning_parts.append("High-polarity sentiment suggests significant news impact.")
        
        if features["key_factors"]:
            reasoning_parts.append(f"Key factors: {'; '.join(features['key_factors'][:3])}.")
        
        return " ".join(reasoning_parts)
    
    def _estimate_return(self, impact_score: float, direction: SignalDirection) -> float:
        """Estimate expected return percentage."""
        # Simplified model
        base_return = impact_score * 5  # 0-5% based on impact
        
        if direction == SignalDirection.BEARISH:
            base_return = -base_return
        elif direction == SignalDirection.NEUTRAL:
            base_return = base_return * 0.3
        
        return round(base_return, 2)
    
    def _calculate_risk(self, features: Dict[str, Any]) -> str:
        """Calculate risk level."""
        if features["sentiment_confidence"] < 0.5:
            return "high"
        elif features["breaking_news_score"] > 0.8:
            return "high"
        elif features["sentiment_magnitude"] > 0.7:
            return "medium"
        return "low"
    
    def _suggest_action(self, direction: SignalDirection, horizon: str) -> str:
        """Suggest trading action."""
        if direction == SignalDirection.BULLISH:
            if horizon == "intraday":
                return "Consider long position with tight stop"
            return "Accumulate on dips"
        elif direction == SignalDirection.BEARISH:
            if horizon == "intraday":
                return "Consider short or exit longs"
            return "Reduce exposure"
        return "Monitor for clearer signals"


class SentimentMomentum(BaseSignalGenerator):
    """
    Detects sentiment trends and momentum shifts.
    
    Tracks sentiment over time to identify:
    - Trend acceleration/deceleration
    - Sentiment extremes (contrarian signals)
    - Multi-timeframe alignment
    """
    
    def __init__(self, config: Dict[str, Any] = None, cache: redis.Redis = None):
        super().__init__(config, cache)
        
        # Sentiment history by ticker
        self.sentiment_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.config.get("history_window", 100))
        )
        
        # Lookback periods for momentum calculation
        self.short_window = self.config.get("short_window", 5)
        self.medium_window = self.config.get("medium_window", 20)
        self.long_window = self.config.get("long_window", 50)
        
        # Momentum thresholds
        self.momentum_threshold = self.config.get("momentum_threshold", 0.2)
        self.extreme_threshold = self.config.get("extreme_threshold", 0.8)
    
    def get_signal_type(self) -> SignalType:
        return SignalType.SENTIMENT_MOMENTUM
    
    async def generate(
        self, 
        nlp_result: Any,
        market_data: Optional[Dict] = None
    ) -> Optional[Signal]:
        """Generate sentiment momentum signal."""
        tickers = getattr(nlp_result, 'tickers', [])
        if not tickers:
            return None
        
        ticker = tickers[0]
        sentiment = getattr(nlp_result, 'sentiment_score', 0)
        
        # Update history
        self.sentiment_history[ticker].append({
            "timestamp": datetime.now(),
            "sentiment": sentiment,
            "confidence": getattr(nlp_result, 'sentiment_confidence', 0)
        })
        
        # Need enough history
        if len(self.sentiment_history[ticker]) < self.medium_window:
            return None
        
        # Calculate momentum
        momentum = self._calculate_momentum(ticker)
        
        if momentum["score"] < self.momentum_threshold:
            return None
        
        # Determine direction and type
        if momentum["type"] == "extreme_bullish":
            direction = SignalDirection.BEARISH  # Contrarian
            reasoning = "Extreme bullish sentiment suggests potential reversal"
        elif momentum["type"] == "extreme_bearish":
            direction = SignalDirection.BULLISH  # Contrarian
            reasoning = "Extreme bearish sentiment suggests potential reversal"
        elif momentum["type"] == "accelerating":
            direction = SignalDirection.BULLISH if sentiment > 0 else SignalDirection.BEARISH
            reasoning = "Sentiment momentum accelerating in current direction"
        elif momentum["type"] == "decelerating":
            direction = SignalDirection.NEUTRAL
            reasoning = "Sentiment momentum decelerating, caution warranted"
        else:
            return None
        
        # Calculate confidence
        confidence = min(momentum["score"] + 0.5, 0.95)
        
        if not self._should_emit(confidence):
            return None
        
        return Signal(
            id="",
            timestamp=datetime.now(),
            signal_type=self.get_signal_type(),
            direction=direction,
            ticker=ticker,
            confidence=confidence,
            source_articles=[getattr(nlp_result, 'article_id', 'unknown')],
            time_horizon="swing",
            reasoning=reasoning,
            key_factors=[
                f"Short-term MA: {momentum['short_ma']:.3f}",
                f"Medium-term MA: {momentum['medium_ma']:.3f}",
                f"Momentum type: {momentum['type']}"
            ]
        )
    
    def _calculate_momentum(self, ticker: str) -> Dict[str, Any]:
        """Calculate sentiment momentum metrics."""
        history = list(self.sentiment_history[ticker])
        sentiments = [h["sentiment"] for h in history]
        
        # Calculate moving averages
        short_ma = np.mean(sentiments[-self.short_window:])
        medium_ma = np.mean(sentiments[-self.medium_window:])
        long_ma = np.mean(sentiments[-self.long_window:]) if len(sentiments) >= self.long_window else medium_ma
        
        # Detect extremes
        current = sentiments[-1]
        extreme_bullish = current > self.extreme_threshold and short_ma > self.extreme_threshold * 0.9
        extreme_bearish = current < -self.extreme_threshold and short_ma < -self.extreme_threshold * 0.9
        
        # Detect acceleration/deceleration
        if len(sentiments) >= self.short_window * 2:
            prev_short_ma = np.mean(sentiments[-self.short_window*2:-self.short_window])
            acceleration = abs(short_ma) > abs(prev_short_ma) * 1.2
            deceleration = abs(short_ma) < abs(prev_short_ma) * 0.8
        else:
            acceleration = False
            deceleration = False
        
        # Calculate momentum score
        score = 0.0
        momentum_type = "neutral"
        
        if extreme_bullish:
            score = abs(current)
            momentum_type = "extreme_bullish"
        elif extreme_bearish:
            score = abs(current)
            momentum_type = "extreme_bearish"
        elif acceleration:
            score = abs(short_ma - long_ma)
            momentum_type = "accelerating"
        elif deceleration:
            score = abs(short_ma - long_ma) * 0.5
            momentum_type = "decelerating"
        
        return {
            "score": score,
            "type": momentum_type,
            "short_ma": short_ma,
            "medium_ma": medium_ma,
            "long_ma": long_ma,
            "current": current
        }


class BreakingNewsDetector(BaseSignalGenerator):
    """
    Detects breaking news with high market impact potential.
    
    Monitors for:
    - High-velocity news (rapid publication across sources)
    - Key word triggers (M&A, FDA, bankruptcy, etc.)
    - Source authority escalation
    - Social media amplification
    """
    
    # High-impact keywords
    IMPACT_KEYWORDS = {
        "merger": 0.9,
        "acquisition": 0.9,
        "buyout": 0.9,
        "bankruptcy": 0.95,
        "default": 0.9,
        "FDA approval": 0.9,
        "FDA rejection": 0.95,
        "earnings": 0.7,
        "guidance": 0.75,
        "layoffs": 0.8,
        "CEO departure": 0.85,
        "investigation": 0.8,
        "lawsuit": 0.75,
        "recall": 0.8,
        "data breach": 0.85,
    }
    
    def __init__(self, config: Dict[str, Any] = None, cache: redis.Redis = None):
        super().__init__(config, cache)
        
        # News velocity tracking
        self.velocity_window = timedelta(minutes=self.config.get("velocity_window_minutes", 30))
        self.recent_articles: Dict[str, List[datetime]] = defaultdict(list)
        
        # Minimum sources for breaking news
        self.min_sources = self.config.get("min_sources", 2)
        
        # Priority sources (count more)
        self.priority_sources = {"Bloomberg", "Reuters", "CNBC Breaking", "WSJ"}
    
    def get_signal_type(self) -> SignalType:
        return SignalType.BREAKING_NEWS
    
    async def generate(
        self, 
        nlp_result: Any,
        market_data: Optional[Dict] = None
    ) -> Optional[Signal]:
        """Generate breaking news signal."""
        
        # Get text content
        summary = getattr(nlp_result, 'summary', '')
        if not summary:
            return None
        
        text = summary.lower()
        tickers = getattr(nlp_result, 'tickers', [])
        
        if not tickers:
            return None
        
        ticker = tickers[0]
        
        # Check for impact keywords
        keyword_score, matched_keywords = self._check_keywords(text)
        
        if keyword_score < 0.7:
            return None
        
        # Check velocity (articles on same ticker recently)
        velocity_score = self._check_velocity(ticker)
        
        # Calculate source authority
        source_score = self._calculate_source_authority(
            getattr(nlp_result, 'source', '')
        )
        
        # Combined score
        confidence = (keyword_score * 0.5 + velocity_score * 0.3 + source_score * 0.2)
        
        if not self._should_emit(confidence):
            return None
        
        # Determine direction from sentiment
        sentiment = getattr(nlp_result, 'sentiment_score', 0)
        if sentiment > 0.3:
            direction = SignalDirection.BULLISH
        elif sentiment < -0.3:
            direction = SignalDirection.BEARISH
        else:
            direction = SignalDirection.NEUTRAL
        
        # Generate signal
        reasoning = f"Breaking news detected: {', '.join(matched_keywords[:3])}. "
        reasoning += f"Article velocity: {velocity_score:.0%}. "
        reasoning += f"Source authority: {source_score:.0%}."
        
        return Signal(
            id="",
            timestamp=datetime.now(),
            signal_type=self.get_signal_type(),
            direction=direction,
            ticker=ticker,
            confidence=confidence,
            source_articles=[getattr(nlp_result, 'article_id', 'unknown')],
            time_horizon="intraday",
            risk_level="high",
            reasoning=reasoning,
            key_factors=matched_keywords[:5],
            suggested_action="Immediate review required"
        )
    
    def _check_keywords(self, text: str) -> Tuple[float, List[str]]:
        """Check for high-impact keywords."""
        matched = []
        max_score = 0.0
        
        for keyword, score in self.IMPACT_KEYWORDS.items():
            if keyword in text:
                matched.append(keyword)
                max_score = max(max_score, score)
        
        return max_score, matched
    
    def _check_velocity(self, ticker: str) -> float:
        """Check article velocity for ticker."""
        now = datetime.now()
        cutoff = now - self.velocity_window
        
        # Clean old entries
        self.recent_articles[ticker] = [
            t for t in self.recent_articles[ticker] if t > cutoff
        ]
        
        # Add current
        self.recent_articles[ticker].append(now)
        
        # Calculate velocity score
        count = len(self.recent_articles[ticker])
        
        if count >= 5:
            return 1.0
        elif count >= 3:
            return 0.8
        elif count >= 2:
            return 0.6
        return 0.4
    
    def _calculate_source_authority(self, source: str) -> float:
        """Calculate source authority score."""
        source_base = source.split('/')[0]  # Remove sub-source
        
        if source_base in self.priority_sources:
            return 1.0
        elif any(ps in source for ps in self.priority_sources):
            return 0.8
        elif "SEC" in source:
            return 1.0
        elif "Twitter" in source or "Reddit" in source:
            return 0.5
        
        return 0.7


class RumorVerification(BaseSignalGenerator):
    """
    Verifies rumors against authoritative sources.
    
    Tracks rumors and validates when:
    - Confirming official statement found
    - Multiple credible sources corroborate
    - Time window exceeded without confirmation
    
    Also generates signals when rumors are verified or debunked.
    """
    
    def __init__(self, config: Dict[str, Any] = None, cache: redis.Redis = None):
        super().__init__(config, cache)
        
        # Pending rumors
        self.pending_rumors: Dict[str, Dict] = {}
        self.rumor_ttl_hours = self.config.get("rumor_ttl_hours", 48)
        
        # Credible verification sources
        self.credible_sources = {
            "Bloomberg", "Reuters", "SEC EDGAR", "Company Press Release",
            "CNBC", "WSJ", "FT"
        }
        
        # Keywords that suggest rumor vs fact
        self.rumor_keywords = [
            "reportedly", "sources say", "rumored", "speculation",
            "unconfirmed", "allegedly", "reportedly considering"
        ]
        
        self.confirmation_keywords = [
            "announced", "confirms", "official", "statement",
            "press release", "filing shows", "regulatory filing"
        ]
    
    def get_signal_type(self) -> SignalType:
        return SignalType.RUMOR_VERIFIED
    
    async def generate(
        self, 
        nlp_result: Any,
        market_data: Optional[Dict] = None
    ) -> Optional[Signal]:
        """
        Generate signal based on rumor verification.
        
        Either:
        1. Detects a new rumor and adds to tracking
        2. Verifies an existing rumor
        3. Generates signal when verified
        """
        text = (getattr(nlp_result, 'summary', '') or '').lower()
        source = getattr(nlp_result, 'source', '')
        tickers = getattr(nlp_result, 'tickers', [])
        
        if not tickers:
            return None
        
        ticker = tickers[0]
        
        # Check if this is a verification of existing rumor
        verification = self._check_verification(text, source, ticker)
        
        if verification["is_verification"] and verification["rumor_id"]:
            # Verify the rumor
            rumor = self.pending_rumors.get(verification["rumor_id"])
            if rumor:
                return self._create_verification_signal(
                    rumor, nlp_result, verification["verified"]
                )
        
        # Check if this is a new rumor
        if self._is_rumor(text, source):
            rumor_id = self._add_rumor(nlp_result)
            
            # Low confidence initial signal
            sentiment = getattr(nlp_result, 'sentiment_score', 0)
            direction = SignalDirection.BULLISH if sentiment > 0 else SignalDirection.BEARISH
            
            return Signal(
                id="",
                timestamp=datetime.now(),
                signal_type=SignalType.RUMOR_VERIFIED,
                direction=direction,
                ticker=ticker,
                confidence=0.4,  # Low confidence for unverified
                verified=False,
                source_articles=[getattr(nlp_result, 'article_id', 'unknown')],
                time_horizon="swing",
                risk_level="high",
                reasoning=f"Unverified rumor detected: {self._extract_rumor_topic(text)}",
                key_factors=["Awaiting verification", "Unconfirmed source"],
                suggested_action="Wait for official confirmation"
            )
        
        return None
    
    def _is_rumor(self, text: str, source: str) -> bool:
        """Check if article contains a rumor."""
        # Check for rumor keywords
        has_rumor_kw = any(kw in text for kw in self.rumor_keywords)
        
        # Check if source is less credible
        is_less_credible = not any(cs in source for cs in self.credible_sources)
        
        return has_rumor_kw and is_less_credible
    
    def _check_verification(
        self, 
        text: str, 
        source: str, 
        ticker: str
    ) -> Dict[str, Any]:
        """Check if article verifies any pending rumor."""
        result = {"is_verification": False, "rumor_id": None, "verified": False}
        
        # Must be from credible source for verification
        if not any(cs in source for cs in self.credible_sources):
            return result
        
        # Check for confirmation keywords
        has_confirmation = any(kw in text for kw in self.confirmation_keywords)
        
        if not has_confirmation:
            return result
        
        # Check against pending rumors
        now = datetime.now()
        for rumor_id, rumor in list(self.pending_rumors.items()):
            # Check TTL
            if (now - rumor["timestamp"]).total_seconds() > self.rumor_ttl_hours * 3600:
                del self.pending_rumors[rumor_id]
                continue
            
            # Check if same ticker and similar content
            if rumor["ticker"] == ticker:
                similarity = self._text_similarity(text, rumor["text"])
                if similarity > 0.6:
                    result = {
                        "is_verification": True,
                        "rumor_id": rumor_id,
                        "verified": True
                    }
                    del self.pending_rumors[rumor_id]
                    return result
        
        return result
    
    def _add_rumor(self, nlp_result: Any) -> str:
        """Add new rumor to tracking."""
        rumor_id = hashlib.md5(
            f"{getattr(nlp_result, 'article_id', '')}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        self.pending_rumors[rumor_id] = {
            "id": rumor_id,
            "timestamp": datetime.now(),
            "ticker": getattr(nlp_result, 'tickers', [''])[0],
            "text": getattr(nlp_result, 'summary', ''),
            "source": getattr(nlp_result, 'source', ''),
            "sentiment": getattr(nlp_result, 'sentiment_score', 0)
        }
        
        return rumor_id
    
    def _create_verification_signal(
        self, 
        rumor: Dict, 
        nlp_result: Any,
        verified: bool
    ) -> Signal:
        """Create signal for verified rumor."""
        sentiment = getattr(nlp_result, 'sentiment_score', rumor["sentiment"])
        
        if sentiment > 0.3:
            direction = SignalDirection.BULLISH
        elif sentiment < -0.3:
            direction = SignalDirection.BEARISH
        else:
            direction = SignalDirection.NEUTRAL
        
        return Signal(
            id="",
            timestamp=datetime.now(),
            signal_type=self.get_signal_type(),
            direction=direction,
            ticker=rumor["ticker"],
            confidence=0.85,
            verified=True,
            verification_source=getattr(nlp_result, 'source', ''),
            source_articles=[rumor.get("id", ""), getattr(nlp_result, 'article_id', '')],
            time_horizon="intraday",
            risk_level="medium",
            reasoning=f"Previously unverified rumor now confirmed by {getattr(nlp_result, 'source', 'authoritative source')}",
            key_factors=["Rumor verified", "Authoritative confirmation"],
            suggested_action="Consider position based on confirmed information"
        )
    
    def _extract_rumor_topic(self, text: str) -> str:
        """Extract the topic of a rumor."""
        # Simplified extraction - look for nouns after rumor keywords
        for kw in self.rumor_keywords:
            if kw in text:
                start = text.find(kw) + len(kw)
                return text[start:start+50].strip()
        return "unknown topic"
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)


class SignalEngine:
    """
    Main signal generation orchestrator.
    
    Combines multiple signal generators with:
    - Conflict resolution
    - Signal deduplication
    - Confidence weighting
    - Historical performance tracking
    """
    
    def __init__(
        self,
        config: Dict[str, Any] = None,
        cache_url: str = None
    ):
        self.config = config or {}
        self.cache = redis.from_url(cache_url) if cache_url else None
        
        # Initialize generators
        self.generators: List[BaseSignalGenerator] = []
        self._init_generators()
        
        # Signal history for deduplication
        self.signal_history: deque = deque(maxlen=10000)
        self.dedup_window = timedelta(minutes=self.config.get("dedup_minutes", 60))
        
        # Signal performance tracking
        self.performance: Dict[str, List[Dict]] = defaultdict(list)
    
    def _init_generators(self):
        """Initialize all signal generators."""
        generator_classes = [
            (NewsImpactScorer, "news_impact"),
            (SentimentMomentum, "sentiment_momentum"),
            (BreakingNewsDetector, "breaking_news"),
            (RumorVerification, "rumor_verification"),
        ]
        
        for gen_class, config_key in generator_classes:
            gen_config = self.config.get(config_key, {})
            if gen_config.get("enabled", True):
                generator = gen_class(gen_config, self.cache)
                self.generators.append(generator)
                logger.info(f"Initialized signal generator: {gen_class.__name__}")
    
    async def generate(
        self, 
        nlp_result: Any,
        market_data: Optional[Dict] = None
    ) -> List[Signal]:
        """
        Generate all applicable signals from NLP result.
        
        Args:
            nlp_result: NLP processing result
            market_data: Optional market context
            
        Returns:
            List of signals
        """
        signals = []
        
        # Run all generators
        tasks = [
            gen.generate(nlp_result, market_data)
            for gen in self.generators
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Signal generation error: {result}")
                continue
            
            if result and self._is_valid_signal(result):
                signals.append(result)
                self.signal_history.append(result)
        
        # Resolve conflicts
        signals = self._resolve_conflicts(signals)
        
        # Update performance tracking
        self._track_signals(signals)
        
        return signals
    
    async def batch_generate(
        self, 
        nlp_results: List[Any],
        market_data: Optional[Dict] = None
    ) -> List[Signal]:
        """Generate signals for multiple NLP results."""
        all_signals = []
        
        for result in nlp_results:
            signals = await self.generate(result, market_data)
            all_signals.extend(signals)
        
        return all_signals
    
    def _is_valid_signal(self, signal: Signal) -> bool:
        """Check if signal passes validation rules."""
        # Check for duplicates
        for hist_signal in self.signal_history:
            if (hist_signal.ticker == signal.ticker and
                hist_signal.signal_type == signal.signal_type and
                hist_signal.direction == signal.direction):
                
                # Check time window
                if (signal.timestamp - hist_signal.timestamp) < self.dedup_window:
                    return False
        
        return True
    
    def _resolve_conflicts(self, signals: List[Signal]) -> List[Signal]:
        """Resolve conflicting signals."""
        # Group by ticker
        by_ticker: Dict[str, List[Signal]] = defaultdict(list)
        for signal in signals:
            by_ticker[signal.ticker].append(signal)
        
        resolved = []
        
        for ticker, ticker_signals in by_ticker.items():
            if len(ticker_signals) == 1:
                resolved.append(ticker_signals[0])
                continue
            
            # Check for direction conflicts
            bullish = [s for s in ticker_signals if s.direction == SignalDirection.BULLISH]
            bearish = [s for s in ticker_signals if s.direction == SignalDirection.BEARISH]
            
            if bullish and bearish:
                # Conflict - keep highest confidence from each side
                best_bull = max(bullish, key=lambda s: s.confidence)
                best_bear = max(bearish, key=lambda s: s.confidence)
                
                # Keep the stronger signal
                if best_bull.confidence > best_bear.confidence:
                    resolved.append(best_bull)
                else:
                    resolved.append(best_bear)
            else:
                # No conflict - keep all
                resolved.extend(ticker_signals)
        
        return resolved
    
    def _track_signals(self, signals: List[Signal]):
        """Track signals for performance analysis."""
        for signal in signals:
            self.performance[signal.ticker].append({
                "timestamp": signal.timestamp,
                "signal_type": signal.signal_type.value,
                "direction": signal.direction.name,
                "confidence": signal.confidence
            })
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get signal generation performance statistics."""
        total_signals = sum(len(sigs) for sigs in self.performance.values())
        
        by_type = defaultdict(int)
        by_direction = defaultdict(int)
        
        for ticker_signals in self.performance.values():
            for sig in ticker_signals:
                by_type[sig["signal_type"]] += 1
                by_direction[sig["direction"]] += 1
        
        return {
            "total_signals_generated": total_signals,
            "unique_tickers": len(self.performance),
            "signals_by_type": dict(by_type),
            "signals_by_direction": dict(by_direction),
            "active_generators": [g.__class__.__name__ for g in self.generators]
        }
    
    async def shutdown(self):
        """Cleanup resources."""
        if self.cache:
            await self.cache.close()


# Example usage
async def main():
    """Demo signal generation."""
    
    from nlp_pipeline import NLPResult
    
    config = {
        "news_impact": {"enabled": True, "min_confidence": 0.7},
        "sentiment_momentum": {"enabled": True, "min_confidence": 0.6},
        "breaking_news": {"enabled": True, "min_confidence": 0.75},
        "rumor_verification": {"enabled": True, "min_confidence": 0.5},
        "dedup_minutes": 30
    }
    
    engine = SignalEngine(config)
    
    # Sample NLP results
    nlp_results = [
        NLPResult(
            article_id="1",
            processed_at=datetime.now(),
            sentiment_score=0.85,
            sentiment_confidence=0.92,
            sentiment_label="positive",
            entities=[],
            tickers=["AAPL"],
            companies=["Apple Inc."],
            people=["Tim Cook"],
            topics=[1],
            topic_keywords={1: ["earnings", "revenue", "growth"]},
            summary="Apple reports record Q4 earnings beating expectations",
            summary_type="extractive",
            processing_time_ms=150.0,
            model_versions={},
            raw_scores={"sentiment": {"positive": 0.92, "neutral": 0.06, "negative": 0.02}}
        ),
        NLPResult(
            article_id="2",
            processed_at=datetime.now(),
            sentiment_score=-0.75,
            sentiment_confidence=0.88,
            sentiment_label="negative",
            entities=[],
            tickers=["TSLA"],
            companies=["Tesla Inc."],
            people=[],
            topics=[2],
            topic_keywords={2: ["recall", "safety", "investigation"]},
            summary="Tesla announces major vehicle recall due to safety concerns",
            summary_type="extractive",
            processing_time_ms=120.0,
            model_versions={},
            raw_scores={"sentiment": {"positive": 0.05, "neutral": 0.07, "negative": 0.88}}
        )
    ]
    
    print("Generating trading signals...\n")
    
    for nlp_result in nlp_results:
        signals = await engine.generate(nlp_result)
        
        print(f"Article: {nlp_result.summary[:50]}...")
        print(f"Ticker: {nlp_result.tickers[0]}")
        print(f"Sentiment: {nlp_result.sentiment_label} ({nlp_result.sentiment_score:.2f})")
        
        for signal in signals:
            print(f"  Signal: {signal.signal_type.value}")
            print(f"    Direction: {signal.direction.name}")
            print(f"    Confidence: {signal.confidence:.1%}")
            print(f"    Time Horizon: {signal.time_horizon}")
            print(f"    Reasoning: {signal.reasoning[:80]}...")
            print()
    
    # Show stats
    stats = engine.get_performance_stats()
    print(f"\nEngine Stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
