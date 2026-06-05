"""Financial sentiment analysis using FinBERT with VADER fallback.

Classifies text as positive/negative/neutral with financial context:
- Policy direction: hawkish/dovish/neutral
- Sector-level sentiment for banking, markets, real estate, etc.
"""

import json
import logging
import math
import os
import re

from core.base_processor import BaseProcessor

try:
    from free_llm_router import AllProvidersFailed, FreeLLMRouter
    from free_llm_router.policy import smart_order

    _FREE_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    _FREE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Keyword-based policy direction detection (pre-compiled with word boundaries)
_HAWKISH_KEYWORDS = [
    "rate hike", "tightening", "inflation concern", "restrictive",
    "higher rates", "tapering", "reducing liquidity", "contractionary",
    "rate increase", "monetary tightening", "crr hike", "slr increase",
]
_DOVISH_KEYWORDS = [
    "rate cut", "easing", "accommodative", "stimulus",
    "lower rates", "quantitative easing", "expansionary", "liquidity injection",
    "rate reduction", "monetary easing", "crr cut", "growth support",
]

HAWKISH_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b' + re.escape(kw) + r'\b') for kw in _HAWKISH_KEYWORDS
]
DOVISH_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b' + re.escape(kw) + r'\b') for kw in _DOVISH_KEYWORDS
]

_SECTOR_KEYWORDS = {
    "banking": ["bank", "npa", "credit growth", "deposit", "lending", "nbfc", "rbi"],
    "markets": ["nifty", "sensex", "ipo", "fii", "dii", "market cap", "equity"],
    "real_estate": ["real estate", "housing", "property", "rera", "construction"],
    "commodities": ["crude", "gold", "silver", "copper", "commodity"],
    "forex": ["rupee", "dollar", "usd/inr", "forex", "exchange rate"],
    "tech": ["it sector", "technology", "digital", "fintech", "startup"],
}

SECTOR_PATTERNS: dict[str, list[re.Pattern]] = {
    sector: [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in keywords]
    for sector, keywords in _SECTOR_KEYWORDS.items()
}


class SentimentAnalyzer(BaseProcessor):
    name = "sentiment"
    batch_size = 16

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.model_name = self.config.get("model", "ProsusAI/finbert")
        self.multilingual_model = self.config.get(
            "multilingual_model", "cardiffnlp/twitter-xlm-roberta-base-sentiment"
        )
        self.fallback = self.config.get("fallback", "vader")
        # LLM tier (free providers) sits ABOVE FinBERT/VADER. Enabled by default
        # when the package is present; degrades to the existing chain on failure.
        self.use_llm = self.config.get(
            "use_llm",
            _FREE_AVAILABLE and os.environ.get("FREE_LLM_ENABLED", "true").lower() == "true",
        )
        self._pipeline = None
        self._multilingual_pipeline = None
        self._vader = None
        self._free_router = None

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline

                self._pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    max_length=512,
                    truncation=True,
                )
                logger.info(f"[Sentiment] Loaded {self.model_name}")
            except Exception as e:
                logger.warning(f"[Sentiment] FinBERT unavailable ({e}), using VADER")
                self._pipeline = "vader"
        return self._pipeline

    def _get_multilingual_pipeline(self):
        """Lazy-load multilingual sentiment model (XLM-RoBERTa)."""
        if self._multilingual_pipeline is None:
            try:
                from transformers import pipeline
                self._multilingual_pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.multilingual_model,
                    tokenizer=self.multilingual_model,
                    max_length=512,
                    truncation=True,
                )
                logger.info(f"[Sentiment] Loaded multilingual model {self.multilingual_model}")
            except Exception as e:
                logger.warning(f"[Sentiment] Multilingual model unavailable ({e}), using VADER")
                self._multilingual_pipeline = "vader"
        return self._multilingual_pipeline

    def _detect_language(self, text: str) -> str:
        """Detect article language using langdetect."""
        try:
            from processors.language_detector import detect_language, get_language_stats
            lang = detect_language(text)
            get_language_stats().record(lang)
            return lang
        except Exception:
            return "en"

    def process_one(self, article: dict) -> dict:
        text = article.get("full_text", "") or article.get("title", "")
        article_id = article.get("id")

        if not text or len(text.strip()) < 10:
            return {"article_id": article_id, "status": "skipped"}

        # Detect language and route to appropriate model
        language = self._detect_language(text)
        score, model_used = self._analyze(text, language=language)
        text_lower = text.lower()
        direction = self._detect_policy_direction(text_lower)
        sectors = self._detect_sectors(text_lower)

        return {
            "article_id": article_id,
            "status": "analyzed",
            "overall": score,
            "policy_direction": direction,
            "sector_scores": sectors,
            "model": model_used,
            "language": language,
        }

    @staticmethod
    def _sanitize_score(score: float) -> float:
        """Guard against NaN and infinity in sentiment scores."""
        if math.isnan(score) or math.isinf(score):
            return 0.0
        return max(-1.0, min(1.0, score))

    def _analyze(self, text: str, language: str = "en") -> tuple[float, str]:
        """Return (sentiment_score, model_used). Score is in [-1, 1].

        Routes to the appropriate model based on language, tracking the model
        that actually produced the score (including fallback paths).
        """
        from processors.language_detector import get_sentiment_model_for_language

        # Top tier: free LLM with financial context. Falls through on any failure.
        if self.use_llm:
            llm = self._llm_score(text)
            if llm is not None:
                return llm

        model_type = get_sentiment_model_for_language(language)

        if model_type == "vader":
            return self._sanitize_score(self._vader_score(text)), "vader"

        if model_type == "xlm-roberta":
            return self._analyze_multilingual(text)

        # Default: FinBERT for English
        pipeline = self._get_pipeline()

        if pipeline == "vader":
            return self._sanitize_score(self._vader_score(text)), "vader"

        try:
            result = pipeline(text[:512])[0]
            label = result["label"].lower()
            score = result["score"]
            if label == "negative":
                return self._sanitize_score(-score), self.model_name
            elif label == "positive":
                return self._sanitize_score(score), self.model_name
            return 0.0, self.model_name
        except Exception as e:
            logger.debug(f"[Sentiment] FinBERT failed: {e}")
            return self._sanitize_score(self._vader_score(text)), "vader"

    def _analyze_multilingual(self, text: str) -> tuple[float, str]:
        """Run sentiment analysis using XLM-RoBERTa multilingual model.

        Returns (score, model_used) tracking the actual model, not assumed.
        """
        pipeline = self._get_multilingual_pipeline()

        if pipeline == "vader":
            return self._sanitize_score(self._vader_score(text)), "vader"

        try:
            result = pipeline(text[:512])[0]
            label = result["label"].lower()
            score = result["score"]
            # XLM-RoBERTa uses "negative", "neutral", "positive" labels
            if "negative" in label:
                return self._sanitize_score(-score), self.multilingual_model
            elif "positive" in label:
                return self._sanitize_score(score), self.multilingual_model
            return 0.0, self.multilingual_model
        except Exception as e:
            logger.debug(f"[Sentiment] Multilingual model failed: {e}")
            return self._sanitize_score(self._vader_score(text)), "vader"

    def _get_free_router(self):
        if not (_FREE_AVAILABLE and self.use_llm):
            return None
        if self._free_router is None:
            self._free_router = FreeLLMRouter(order_fn=smart_order)
        return self._free_router

    @staticmethod
    def _run_async(coro):
        """Run an async coroutine from this sync processor.

        Celery sync workers have no running loop, so asyncio.run is safe. If a loop
        is somehow already running, bail (caller falls back to FinBERT/VADER).
        """
        import asyncio

        try:
            asyncio.get_running_loop()
            return None  # already in a loop — don't risk a nested-run crash
        except RuntimeError:
            pass
        return asyncio.run(coro)

    def _llm_score(self, text: str):
        """Financial sentiment via free LLM. Returns (score, model) or None.

        Asks for a compact JSON object so we get both an intensity score AND the
        financial direction (which keyword/FinBERT scoring conflates with tone).
        """
        router = self._get_free_router()
        if router is None:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a financial sentiment analyst. Read the text and reply "
                    "with ONLY a JSON object: "
                    '{"score": <float -1.0..1.0>, "direction": "bullish"|"bearish"|"neutral"}. '
                    "score reflects market sentiment intensity (negative=bearish). "
                    "No prose, no code fences."
                ),
            },
            {"role": "user", "content": text[:2000]},
        ]
        try:
            result = self._run_async(
                router.chat_completion(
                    messages, task_type="sentiment", temperature=0.0, max_tokens=48
                )
            )
            if result is None:
                return None
            raw = result["text"].strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            score = self._sanitize_score(float(parsed["score"]))
            return score, f"llm:{result.get('provider', 'free')}"
        except AllProvidersFailed as exc:
            logger.debug("[Sentiment] All free providers failed: %s", exc)
            return None
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            logger.debug("[Sentiment] LLM returned unparseable output: %s", exc)
            return None

    def _vader_score(self, text: str) -> float:
        if self._vader is None:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

                self._vader = SentimentIntensityAnalyzer()
            except ImportError:
                return 0.0
        score = self._vader.polarity_scores(text)["compound"]
        return self._sanitize_score(score)

    def _detect_policy_direction(self, text_lower: str) -> str:
        hawkish = sum(1 for p in HAWKISH_PATTERNS if p.search(text_lower))
        dovish = sum(1 for p in DOVISH_PATTERNS if p.search(text_lower))

        if hawkish > dovish and hawkish >= 2:
            return "hawkish"
        elif dovish > hawkish and dovish >= 2:
            return "dovish"
        return "neutral"

    def _detect_sectors(self, text_lower: str) -> dict:
        """Detect which sectors are mentioned and assign per-sector sentiment."""
        sectors = {}
        for sector, patterns in SECTOR_PATTERNS.items():
            mentions = sum(1 for p in patterns if p.search(text_lower))
            if mentions > 0:
                sectors[sector] = {"mentions": mentions}
        return sectors

    def _store_results(self, results: list[dict], db):
        from storage.models import SentimentScore

        for r in results:
            if r.get("status") == "analyzed":
                score = SentimentScore(
                    article_id=r["article_id"],
                    overall=r["overall"],
                    sector_scores=r.get("sector_scores", {}),
                    policy_direction=r.get("policy_direction", "neutral"),
                    model_name=r.get("model", "vader"),
                )
                db.add(score)
        try:
            db.commit()
        except Exception as e:
            logger.error(f"[Sentiment] Failed to store results: {e}")
            db.rollback()
