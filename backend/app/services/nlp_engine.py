"""Rule-based NLP engine — no external ML dependencies.

Provides sentiment analysis, entity extraction, extractive summarization,
topic extraction, fake-news heuristics, and market briefing generation.
"""

import json
import logging
import math
import os
import re
from collections import Counter
from datetime import date, datetime

logger = logging.getLogger(__name__)

# Optional free-LLM router for abstractive summarization. Guarded so the rule-based
# engine still works standalone if the package is absent.
try:
    from free_llm_router import AllProvidersFailed, FreeLLMRouter
    from free_llm_router.policy import smart_order

    _FREE_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    _FREE_AVAILABLE = False

_FREE_ROUTER = None


def _get_free_router():
    """Lazy singleton free router, or None if disabled/unavailable."""
    global _FREE_ROUTER
    if not (_FREE_AVAILABLE and os.environ.get("FREE_LLM_ENABLED", "true").lower() == "true"):
        return None
    if _FREE_ROUTER is None:
        _FREE_ROUTER = FreeLLMRouter(order_fn=smart_order)
    return _FREE_ROUTER

# ── Sentiment word lists ──────────────────────────────────────────────────────

POSITIVE_WORDS: set[str] = {
    "bull", "bullish", "gain", "gains", "surge", "surges", "surging", "rally",
    "rallied", "rallying", "profit", "profits", "profitable", "growth", "grow",
    "growing", "upgrade", "upgraded", "upside", "outperform", "outperforms",
    "beat", "beats", "beating", "strong", "strength", "positive", "optimistic",
    "recovery", "recover", "recovering", "boom", "booming", "record", "high",
    "soar", "soaring", "jump", "jumping", "improve", "improved", "improvement",
    "exceed", "exceeded", "exceeds", "favorable", "opportunity", "buy",
    "breakout", "momentum", "innovation", "innovative", "success", "successful",
    "accelerate", "accelerating", "dividend", "earnings", "revenue", "up",
    "increase", "increased", "increasing", "expand", "expanding", "expansion",
    "win", "winning", "advance", "advancing", "robust", "solid", "healthy",
}

NEGATIVE_WORDS: set[str] = {
    "bear", "bearish", "loss", "losses", "losing", "decline", "declining",
    "drop", "drops", "dropping", "crash", "crashed", "crashing", "plunge",
    "plunging", "sell", "selloff", "sell-off", "downgrade", "downgraded",
    "downside", "underperform", "underperforms", "miss", "missed", "misses",
    "weak", "weakness", "negative", "pessimistic", "recession", "recessionary",
    "bust", "slump", "slumping", "low", "fall", "falling", "fell", "worsen",
    "worsened", "worsening", "fail", "failed", "failure", "risk", "risky",
    "bankruptcy", "bankrupt", "default", "defaults", "crisis", "panic",
    "fear", "fearful", "volatile", "volatility", "cut", "cuts", "layoff",
    "layoffs", "downturn", "correction", "debt", "deficit", "inflation",
    "overvalued", "bubble", "fraud", "scandal", "investigation", "lawsuit",
    "fine", "penalty", "warning", "concern", "concerns", "troubled", "down",
    "decrease", "decreased", "decreasing", "shrink", "shrinking", "contraction",
}

# ── Common organization names (for entity extraction) ─────────────────────────

KNOWN_ORGANIZATIONS: set[str] = {
    "Apple", "Microsoft", "Google", "Alphabet", "Amazon", "Meta", "Tesla",
    "NVIDIA", "Netflix", "JPMorgan", "Goldman Sachs", "Morgan Stanley",
    "Bank of America", "Citigroup", "Wells Fargo", "Berkshire Hathaway",
    "Johnson & Johnson", "Pfizer", "Moderna", "UnitedHealth", "Visa",
    "Mastercard", "Walmart", "Costco", "Home Depot", "Disney", "Coca-Cola",
    "PepsiCo", "Intel", "AMD", "Qualcomm", "Broadcom", "Salesforce",
    "Adobe", "Oracle", "IBM", "Samsung", "Toyota", "HSBC", "Alibaba",
    "Tencent", "ByteDance", "Federal Reserve", "Fed", "SEC", "CFTC",
    "Treasury", "ECB", "BOJ", "PBOC", "IMF", "World Bank", "OPEC",
    "S&P", "Moody's", "Fitch", "NYSE", "NASDAQ", "CME", "CBOE",
}

# ── Stop words for topic extraction ───────────────────────────────────────────

STOP_WORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "about", "up", "it",
    "its", "this", "that", "these", "those", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them", "their",
    "what", "which", "who", "whom", "said", "also", "new", "like", "one",
    "two", "first", "time", "way", "even", "back", "any", "well", "much",
}


class SentimentResult:
    """Container for sentiment analysis output."""

    def __init__(self, score: float, label: str):
        self.score = score
        self.label = label

    def to_dict(self) -> dict:
        return {"score": round(self.score, 4), "label": self.label}


class Entity:
    """Container for an extracted entity."""

    def __init__(self, text: str, entity_type: str, start: int | None = None, end: int | None = None):
        self.text = text
        self.entity_type = entity_type
        self.start = start
        self.end = end

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
        }


class NlpEngine:
    """Rule-based NLP engine for financial text analysis."""

    # ── Regex patterns for entity extraction ──────────────────────────────────

    TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")
    MONETARY_PATTERN = re.compile(
        r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s?(?:billion|million|trillion|B|M|T|bn|mn|tn)?",
        re.IGNORECASE,
    )
    PERCENTAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s?%")
    DATE_PATTERN = re.compile(
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
        re.IGNORECASE,
    )

    def analyze_sentiment(self, text: str) -> SentimentResult:
        """Keyword-based sentiment analysis.

        Scores each word against positive/negative lists, normalizes by total
        sentiment word count, and produces a score in [-1, 1].
        """
        if not text or not text.strip():
            return SentimentResult(score=0.0, label="neutral")

        words = re.findall(r"[a-zA-Z]+", text.lower())
        if not words:
            return SentimentResult(score=0.0, label="neutral")

        pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
        total_sentiment = pos_count + neg_count

        if total_sentiment == 0:
            return SentimentResult(score=0.0, label="neutral")

        # Score is (positive - negative) / total_sentiment, clamped to [-1, 1]
        raw_score = (pos_count - neg_count) / total_sentiment
        score = max(-1.0, min(1.0, raw_score))

        if score > 0.1:
            label = "positive"
        elif score < -0.1:
            label = "negative"
        else:
            label = "neutral"

        return SentimentResult(score=round(score, 4), label=label)

    def extract_entities(self, text: str) -> list[Entity]:
        """Regex-based extraction of tickers, monetary amounts, percentages,
        dates, and known organizations."""
        if not text:
            return []

        entities: list[Entity] = []
        seen: set[str] = set()

        # Ticker symbols ($AAPL)
        for m in self.TICKER_PATTERN.finditer(text):
            ticker = m.group(1)
            key = f"ticker:{ticker}"
            if key not in seen:
                seen.add(key)
                entities.append(Entity(
                    text=f"${ticker}",
                    entity_type="ticker",
                    start=m.start(),
                    end=m.end(),
                ))

        # Monetary amounts
        for m in self.MONETARY_PATTERN.finditer(text):
            full = m.group(0)
            key = f"monetary:{full}"
            if key not in seen:
                seen.add(key)
                entities.append(Entity(
                    text=full,
                    entity_type="monetary",
                    start=m.start(),
                    end=m.end(),
                ))

        # Percentages
        for m in self.PERCENTAGE_PATTERN.finditer(text):
            full = m.group(0)
            key = f"percentage:{full}"
            if key not in seen:
                seen.add(key)
                entities.append(Entity(
                    text=full,
                    entity_type="percentage",
                    start=m.start(),
                    end=m.end(),
                ))

        # Dates
        for m in self.DATE_PATTERN.finditer(text):
            full = m.group(0)
            key = f"date:{full}"
            if key not in seen:
                seen.add(key)
                entities.append(Entity(
                    text=full,
                    entity_type="date",
                    start=m.start(),
                    end=m.end(),
                ))

        # Known organizations
        for org in KNOWN_ORGANIZATIONS:
            idx = text.find(org)
            if idx != -1:
                key = f"organization:{org}"
                if key not in seen:
                    seen.add(key)
                    entities.append(Entity(
                        text=org,
                        entity_type="organization",
                        start=idx,
                        end=idx + len(org),
                    ))

        return entities

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        """Extractive summarization — score sentences by keyword frequency
        and return the top-N most informative sentences in order."""
        if not text or not text.strip():
            return ""

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        if len(sentences) <= max_sentences:
            return text.strip()

        # Build word frequency (excluding stop words)
        words = re.findall(r"[a-zA-Z]+", text.lower())
        word_freq: Counter[str] = Counter()
        for w in words:
            if w not in STOP_WORDS and len(w) > 2:
                word_freq[w] += 1

        if not word_freq:
            return " ".join(sentences[:max_sentences])

        # Normalize frequencies
        max_freq = max(word_freq.values())
        if max_freq > 0:
            for w in word_freq:
                word_freq[w] = word_freq[w] / max_freq

        # Score each sentence
        scored: list[tuple[int, float, str]] = []
        for idx, sent in enumerate(sentences):
            sent_words = re.findall(r"[a-zA-Z]+", sent.lower())
            if not sent_words:
                continue
            score = sum(word_freq.get(w, 0) for w in sent_words) / len(sent_words)
            # Boost first sentence slightly (often contains the main point)
            if idx == 0:
                score *= 1.2
            scored.append((idx, score, sent))

        # Pick top-N sentences, preserve original order
        scored.sort(key=lambda x: x[1], reverse=True)
        top = sorted(scored[:max_sentences], key=lambda x: x[0])

        return " ".join(item[2] for item in top)

    async def summarize_async(self, text: str, max_sentences: int = 3) -> str:
        """Abstractive summary via free LLM, falling back to extractive summarize().

        Use this from async (FastAPI) contexts. The rule-based extractive summary
        is the fallback when free providers are disabled, absent, or all fail.
        """
        router = _get_free_router()
        if router is not None and text and text.strip():
            try:
                result = await router.chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a financial market analyst. Write a concise, "
                                f"factual summary in at most {max_sentences} sentences. "
                                "Plain text only — no preamble, no bullet points."
                            ),
                        },
                        {"role": "user", "content": text[:6000]},
                    ],
                    task_type="summarization",
                    temperature=0.2,
                    max_tokens=320,
                )
                summary = (result.get("text") or "").strip()
                if summary:
                    return summary
            except AllProvidersFailed as exc:
                logger.warning(
                    "Free LLM summarization failed (%s) — using extractive fallback", exc
                )
        return self.summarize(text, max_sentences)

    def extract_topics(self, text: str, max_topics: int = 5) -> list[str]:
        """TF-IDF-like keyword extraction for topic identification."""
        if not text or not text.strip():
            return []

        words = re.findall(r"[a-zA-Z]+", text.lower())
        if not words:
            return []

        # Term frequency (excluding stop words and short words)
        tf: Counter[str] = Counter()
        for w in words:
            if w not in STOP_WORDS and len(w) > 3:
                tf[w] += 1

        if not tf:
            return []

        total_words = sum(tf.values())
        # IDF-like boost: rarer words in document get higher score
        # Using simple log(total / freq) weighting
        scored: dict[str, float] = {}
        for word, count in tf.items():
            tf_score = count / total_words
            idf_score = math.log(total_words / (1 + count)) + 1
            scored[word] = tf_score * idf_score

        # Sort by score descending and return top topics
        sorted_topics = sorted(scored.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_topics[:max_topics]]

    def detect_fake_news_signals(self, text: str) -> dict:
        """Simple heuristics to flag potential misinformation.

        Returns ALL CAPS ratio, exclamation density, a simple credibility score,
        and a list of flag descriptions.
        """
        if not text or not text.strip():
            return {
                "all_caps_ratio": 0.0,
                "exclamation_density": 0.0,
                "credibility_score": 1.0,
                "flags": [],
            }

        words = text.split()
        total_words = len(words) or 1
        flags: list[str] = []

        # ALL CAPS ratio
        caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
        all_caps_ratio = round(caps_words / total_words, 4)
        if all_caps_ratio > 0.3:
            flags.append("High ALL-CAPS usage")

        # Exclamation density
        exclamation_count = text.count("!")
        exclamation_density = round(exclamation_count / total_words, 4)
        if exclamation_density > 0.1:
            flags.append("Excessive exclamation marks")

        # Clickbait phrases
        clickbait_phrases = [
            "you won't believe", "breaking:", "urgent:", "shocking",
            "guaranteed", "100%", "act now", "limited time",
            "secret", "they don't want you to know",
        ]
        text_lower = text.lower()
        for phrase in clickbait_phrases:
            if phrase in text_lower:
                flags.append(f"Clickbait phrase: '{phrase}'")

        # Credibility score: starts at 1.0, penalize for each flag
        credibility = max(0.0, 1.0 - (len(flags) * 0.2))

        return {
            "all_caps_ratio": all_caps_ratio,
            "exclamation_density": exclamation_density,
            "credibility_score": round(credibility, 4),
            "flags": flags,
        }

    def generate_briefing(self, documents: list[dict]) -> dict:
        """Aggregate sentiment and entities from recent documents into a
        daily market briefing.

        Args:
            documents: list of dicts with keys title, content, source,
                       and optionally sentiment_score, entities_json.

        Returns:
            dict suitable for creating a MarketBriefing row.
        """
        if not documents:
            return {
                "date": date.today().isoformat(),
                "summary": "No documents available for briefing.",
                "market_mood": "neutral",
                "key_events_json": json.dumps([]),
                "sector_highlights_json": None,
            }

        # Aggregate sentiment
        sentiment_scores: list[float] = []
        all_entities: list[dict] = []
        key_events: list[str] = []

        for doc in documents:
            # Compute sentiment if not already done
            score = doc.get("sentiment_score")
            if score is None:
                result = self.analyze_sentiment(doc.get("content", ""))
                score = result.score
            sentiment_scores.append(float(score))

            # Collect entities
            ents_raw = doc.get("entities_json")
            if ents_raw:
                try:
                    ents = json.loads(ents_raw) if isinstance(ents_raw, str) else ents_raw
                    all_entities.extend(ents)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Use titles as key events
            title = doc.get("title", "")
            if title:
                key_events.append(title)

        # Average sentiment
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

        if avg_sentiment > 0.15:
            mood = "bullish"
        elif avg_sentiment < -0.15:
            mood = "bearish"
        else:
            mood = "neutral"

        # Sector highlights from organization entities
        org_counts: Counter[str] = Counter()
        for ent in all_entities:
            if ent.get("entity_type") == "organization":
                org_counts[ent["text"]] += 1
        sector_highlights = [
            {"entity": name, "mentions": count}
            for name, count in org_counts.most_common(10)
        ]

        # Build summary
        summary_parts = [
            f"Market sentiment is {mood} with an average score of {avg_sentiment:.2f}.",
            f"Analyzed {len(documents)} documents.",
        ]
        if org_counts:
            top_org = org_counts.most_common(1)[0][0]
            summary_parts.append(f"Most mentioned: {top_org}.")

        return {
            "date": date.today().isoformat(),
            "summary": " ".join(summary_parts),
            "market_mood": mood,
            "key_events_json": json.dumps(key_events[:20]),
            "sector_highlights_json": json.dumps(sector_highlights) if sector_highlights else None,
        }
