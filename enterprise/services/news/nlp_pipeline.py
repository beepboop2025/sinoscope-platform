"""
DragonScope NLP Pipeline

Enterprise-grade natural language processing for financial news.
Includes FinBERT sentiment analysis, financial NER, topic modeling,
and summarization capabilities.
"""

import asyncio
import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict

import numpy as np
import redis.asyncio as redis
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    pipeline,
    BatchEncoding
)
import spacy
from bertopic import BERTopic
from bertopic.vectorizers import ClassTfidfTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NLPResult:
    """Complete NLP processing result."""
    article_id: str
    processed_at: datetime
    
    # Sentiment
    sentiment_score: float  # -1.0 to +1.0
    sentiment_confidence: float
    sentiment_label: str  # positive, negative, neutral
    
    # Entities
    entities: List[Dict[str, Any]] = field(default_factory=list)
    tickers: List[str] = field(default_factory=list)
    companies: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    
    # Topics
    topics: List[int] = field(default_factory=list)
    topic_keywords: Dict[int, List[str]] = field(default_factory=dict)
    
    # Summary
    summary: Optional[str] = None
    summary_type: str = "extractive"  # extractive or abstractive
    
    # Metadata
    processing_time_ms: float = 0.0
    model_versions: Dict[str, str] = field(default_factory=dict)
    raw_scores: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    """Named entity representation."""
    text: str
    label: str
    start: int
    end: int
    confidence: float
    normalized: Optional[str] = None


class TextPreprocessor:
    """
    Text cleaning and preprocessing for financial documents.
    """
    
    def __init__(self):
        self.financial_abbreviations = {
            "EPS": "earnings per share",
            "EBITDA": "earnings before interest taxes depreciation amortization",
            "P/E": "price to earnings ratio",
            "YoY": "year over year",
            "QoQ": "quarter over quarter",
            "IPO": "initial public offering",
            "M&A": "mergers and acquisitions",
            "CEO": "chief executive officer",
            "CFO": "chief financial officer",
            "COO": "chief operating officer",
            "CTO": "chief technology officer",
            "Fed": "Federal Reserve",
            "GDP": "gross domestic product",
            "CPI": "consumer price index",
            "FOMC": "Federal Open Market Committee",
        }
        
        # Regex patterns
        self.url_pattern = re.compile(r'https?://\S+|www\.\S+')
        self.email_pattern = re.compile(r'\S+@\S+')
        self.ticker_pattern = re.compile(r'\$[A-Z]{1,5}\b')
        self.number_pattern = re.compile(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b')
        
    def clean(self, text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Convert to lowercase (but preserve tickers)
        tickers = self.ticker_pattern.findall(text)
        
        # Remove URLs
        text = self.url_pattern.sub(' [URL] ', text)
        
        # Remove emails
        text = self.email_pattern.sub(' [EMAIL] ', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Restore tickers
        for ticker in tickers:
            text = text.replace(ticker.lower(), ticker)
        
        return text.strip()
    
    def tokenize(self, text: str, max_length: int = 512) -> List[str]:
        """
        Tokenize text into sentences or chunks.
        
        Args:
            text: Input text
            max_length: Maximum token length per chunk
            
        Returns:
            List of text chunks
        """
        # Simple sentence tokenization
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            # Rough token estimate (words * 1.3 for subwords)
            estimated_tokens = len(sentence.split()) * 1.3
            
            if current_length + estimated_tokens > max_length:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = estimated_tokens
            else:
                current_chunk.append(sentence)
                current_length += estimated_tokens
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks if chunks else [text]
    
    def expand_abbreviations(self, text: str) -> str:
        """Expand financial abbreviations."""
        for abbr, full in self.financial_abbreviations.items():
            text = re.sub(rf'\b{abbr}\b', full, text, flags=re.IGNORECASE)
        return text
    
    def extract_financial_metrics(self, text: str) -> List[Dict[str, Any]]:
        """Extract financial metrics from text."""
        metrics = []
        
        # Revenue patterns
        revenue_patterns = [
            r'(revenue|sales)\s+of\s+\$?(\d+(?:\.\d+)?)\s*(billion|million|B|M)?',
            r'\$?(\d+(?:\.\d+)?)\s*(billion|million)\s+(in\s+)?(revenue|sales)',
        ]
        
        for pattern in revenue_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                metrics.append({
                    "type": "revenue",
                    "value": match.group(2) if len(match.groups()) > 1 else match.group(1),
                    "unit": match.group(3) if len(match.groups()) > 2 else None,
                    "context": match.group(0)
                })
        
        # EPS patterns
        eps_pattern = r'(?:EPS|earnings per share)\s+(?:of\s+)?([+-]?\d+(?:\.\d+)?)'
        for match in re.finditer(eps_pattern, text, re.IGNORECASE):
            metrics.append({
                "type": "eps",
                "value": float(match.group(1)),
                "context": match.group(0)
            })
        
        # Percentage changes
        pct_pattern = r'([+-]?\d+(?:\.\d+)?)%\s+(?:increase|decrease|rise|fall|gain|loss|growth|decline)'
        for match in re.finditer(pct_pattern, text, re.IGNORECASE):
            metrics.append({
                "type": "percentage_change",
                "value": float(match.group(1)),
                "context": match.group(0)
            })
        
        return metrics
    
    def preprocess(self, text: str) -> Dict[str, Any]:
        """
        Full preprocessing pipeline.
        
        Returns:
            Dictionary with cleaned text, chunks, and extracted metrics
        """
        cleaned = self.clean(text)
        expanded = self.expand_abbreviations(cleaned)
        chunks = self.tokenize(expanded)
        metrics = self.extract_financial_metrics(text)
        
        return {
            "cleaned_text": cleaned,
            "expanded_text": expanded,
            "chunks": chunks,
            "financial_metrics": metrics,
            "original_length": len(text),
            "cleaned_length": len(cleaned)
        }


class SentimentAnalyzer:
    """
    Financial sentiment analysis using FinBERT.
    
    Models:
    - ProsusAI/finbert: Fine-tuned BERT for financial sentiment
    - Custom ensemble for improved accuracy
    """
    
    MODEL_NAME = "ProsusAI/finbert"
    
    def __init__(self, model_name: str = None, device: str = None, cache: redis.Redis = None):
        self.model_name = model_name or self.MODEL_NAME
        self.device = device or ("cuda" if self._check_cuda() else "cpu")
        self.cache = cache
        
        logger.info(f"Loading FinBERT sentiment model on {self.device}...")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name
        ).to(self.device)
        
        self.model.eval()
        
        # Label mapping
        self.id2label = {0: "negative", 1: "neutral", 2: "positive"}
        self.label2id = {"negative": 0, "neutral": 1, "positive": 2}
        
    def _check_cuda(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    async def analyze(
        self, 
        text: str,
        preprocessor: TextPreprocessor = None
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of financial text.
        
        Args:
            text: Input text
            preprocessor: Optional preprocessor for chunking
            
        Returns:
            Sentiment analysis result
        """
        cache_key = None
        if self.cache:
            cache_key = f"sentiment:{hashlib.md5(text.encode()).hexdigest()}"
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Preprocess if needed
        if preprocessor:
            preprocessed = preprocessor.preprocess(text)
            chunks = preprocessed["chunks"]
        else:
            chunks = [text[:512]]
        
        # Analyze each chunk
        chunk_results = []
        for chunk in chunks:
            result = self._analyze_chunk(chunk)
            chunk_results.append(result)
        
        # Aggregate results (weighted by confidence)
        aggregated = self._aggregate_sentiments(chunk_results)
        
        # Convert to -1 to +1 scale
        sentiment_score = self._normalize_score(
            aggregated["label"], 
            aggregated["confidence"]
        )
        
        result = {
            "sentiment_score": sentiment_score,
            "sentiment_confidence": aggregated["confidence"],
            "sentiment_label": aggregated["label"],
            "raw_scores": aggregated["raw_scores"],
            "chunk_count": len(chunks),
            "model": self.model_name
        }
        
        if self.cache and cache_key:
            await self.cache.setex(cache_key, 3600, json.dumps(result))
        
        return result
    
    def _analyze_chunk(self, text: str) -> Dict[str, Any]:
        """Analyze a single text chunk."""
        import torch
        
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        probs = probabilities[0].cpu().numpy()
        
        # Get predicted label
        pred_id = int(np.argmax(probs))
        confidence = float(probs[pred_id])
        
        return {
            "label": self.id2label[pred_id],
            "confidence": confidence,
            "raw_scores": {
                self.id2label[i]: float(probs[i]) 
                for i in range(len(probs))
            }
        }
    
    def _aggregate_sentiments(
        self, 
        chunk_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate sentiment across chunks."""
        if not chunk_results:
            return {
                "label": "neutral",
                "confidence": 0.0,
                "raw_scores": {"negative": 0.0, "neutral": 1.0, "positive": 0.0}
            }
        
        if len(chunk_results) == 1:
            return chunk_results[0]
        
        # Weight by confidence
        total_weight = sum(r["confidence"] for r in chunk_results)
        
        # Aggregate raw scores
        aggregated_scores = defaultdict(float)
        for result in chunk_results:
            weight = result["confidence"] / total_weight
            for label, score in result["raw_scores"].items():
                aggregated_scores[label] += score * weight
        
        # Get dominant label
        dominant_label = max(aggregated_scores, key=aggregated_scores.get)
        dominant_confidence = aggregated_scores[dominant_label]
        
        return {
            "label": dominant_label,
            "confidence": dominant_confidence,
            "raw_scores": dict(aggregated_scores)
        }
    
    def _normalize_score(self, label: str, confidence: float) -> float:
        """
        Convert label + confidence to -1 to +1 score.
        
        positive: 0 to +1
        neutral: -0.2 to +0.2 (based on confidence)
        negative: -1 to 0
        """
        if label == "positive":
            return confidence
        elif label == "negative":
            return -confidence
        else:
            # Neutral: small random variance based on confidence
            return (confidence - 0.5) * 0.4


class EntityExtractor:
    """
    Named Entity Recognition for financial documents.
    
    Uses spaCy with custom financial entity recognition for:
    - Stock tickers (AAPL, TSLA)
    - Company names
    - Financial instruments
    - People (executives, analysts)
    - Organizations
    - Monetary values
    """
    
    def __init__(self, model_name: str = "en_core_web_trf", cache: redis.Redis = None):
        self.model_name = model_name
        self.cache = cache
        
        logger.info(f"Loading NER model: {model_name}...")
        
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            logger.warning(f"Model {model_name} not found. Downloading...")
            spacy.cli.download(model_name)
            self.nlp = spacy.load(model_name)
        
        # Add custom financial NER patterns
        self._add_financial_patterns()
        
        # Known ticker to company mapping
        self.ticker_companies = self._load_ticker_mapping()
        
    def _add_financial_patterns(self):
        """Add custom entity patterns for financial terms."""
        from spacy.matcher import Matcher
        
        matcher = Matcher(self.nlp.vocab)
        
        # Stock ticker pattern: $AAPL or (NASDAQ: AAPL)
        ticker_patterns = [
            [{"TEXT": {"REGEX": "^\$[A-Z]{1,5}$"}}],
            [{"LOWER": {"IN": ["nasdaq", "nyse"]}}, {"TEXT": ":"}, {"IS_ALPHA": True}],
        ]
        matcher.add("STOCK_TICKER", ticker_patterns)
        
        self.matcher = matcher
    
    def _load_ticker_mapping(self) -> Dict[str, str]:
        """Load ticker to company name mapping."""
        # This would typically load from a database
        # Simplified version with major tickers
        return {
            "AAPL": "Apple Inc.",
            "MSFT": "Microsoft Corporation",
            "GOOGL": "Alphabet Inc.",
            "AMZN": "Amazon.com Inc.",
            "TSLA": "Tesla Inc.",
            "META": "Meta Platforms Inc.",
            "NVDA": "NVIDIA Corporation",
            "JPM": "JPMorgan Chase & Co.",
            "V": "Visa Inc.",
            "JNJ": "Johnson & Johnson",
        }
    
    async def extract(
        self, 
        text: str,
        preprocessor: TextPreprocessor = None
    ) -> Dict[str, Any]:
        """
        Extract entities from text.
        
        Args:
            text: Input text
            preprocessor: Optional preprocessor
            
        Returns:
            Dictionary with extracted entities
        """
        cache_key = None
        if self.cache:
            cache_key = f"entities:{hashlib.md5(text.encode()).hexdigest()}"
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Clean text if preprocessor available
        if preprocessor:
            text = preprocessor.clean(text)
        
        # Process with spaCy
        doc = self.nlp(text)
        
        entities = []
        tickers = set()
        companies = set()
        people = set()
        organizations = set()
        monetary_values = []
        
        for ent in doc.ents:
            entity = Entity(
                text=ent.text,
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                confidence=1.0  # spaCy doesn't provide confidence by default
            )
            entities.append(entity)
            
            # Categorize
            if ent.label_ in ["ORG"]:
                # Check if it's a known company
                company_name = ent.text
                for ticker, name in self.ticker_companies.items():
                    if name.lower() in company_name.lower():
                        tickers.add(ticker)
                        companies.add(name)
                        entity.normalized = ticker
                        break
                else:
                    organizations.add(ent.text)
                    
            elif ent.label_ == "PERSON":
                people.add(ent.text)
                
            elif ent.label_ == "MONEY":
                monetary_values.append({
                    "text": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char
                })
        
        # Extract tickers using regex patterns
        ticker_pattern = re.compile(r'\$([A-Z]{1,5})\b')
        for match in ticker_pattern.finditer(text):
            ticker = match.group(1)
            tickers.add(ticker)
            
            # Add company name if known
            if ticker in self.ticker_companies:
                companies.add(self.ticker_companies[ticker])
        
        # Extract additional financial entities
        financial_entities = self._extract_financial_entities(text)
        
        result = {
            "entities": [
                {
                    "text": e.text,
                    "label": e.label,
                    "start": e.start,
                    "end": e.end,
                    "normalized": e.normalized
                }
                for e in entities
            ],
            "tickers": sorted(list(tickers)),
            "companies": sorted(list(companies)),
            "people": sorted(list(people)),
            "organizations": sorted(list(organizations)),
            "monetary_values": monetary_values,
            "financial_entities": financial_entities
        }
        
        if self.cache and cache_key:
            await self.cache.setex(cache_key, 3600, json.dumps(result))
        
        return result
    
    def _extract_financial_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract financial-specific entities."""
        entities = []
        
        # Financial instrument patterns
        patterns = {
            "options_contract": r'(\d+)\s+(calls?|puts?)\s+(?:on|for)\s+\$?([A-Z]{1,5})',
            "price_target": r'price\s+target\s+(?:of\s+)?\$?(\d+(?:\.\d+)?)',
            "market_cap": r'market\s+cap(?:italization)?\s+(?:of\s+)?\$?(\d+(?:\.\d+)?)\s*(billion|trillion)?',
        }
        
        for entity_type, pattern in patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append({
                    "type": entity_type,
                    "text": match.group(0),
                    "value": match.group(1) if len(match.groups()) > 0 else None,
                    "start": match.start(),
                    "end": match.end()
                })
        
        return entities


class TopicModeler:
    """
    Financial topic modeling using BERTopic.
    
    Identifies themes and topics in financial news for:
    - Trend detection
    - News clustering
    - Thematic investing signals
    """
    
    def __init__(
        self, 
        n_topics: int = 50,
        min_topic_size: int = 10,
        cache: redis.Redis = None
    ):
        self.n_topics = n_topics
        self.min_topic_size = min_topic_size
        self.cache = cache
        
        logger.info("Initializing BERTopic model...")
        
        self.model = BERTopic(
            language="english",
            calculate_probabilities=True,
            n_gram_range=(1, 3),
            min_topic_size=min_topic_size,
            nr_topics=n_topics,
            vectorizer_model=ClassTfidfTransformer()
        )
        
        self.is_fitted = False
        
    async def fit(self, documents: List[str]):
        """
        Fit topic model on corpus.
        
        Args:
            documents: List of documents for training
        """
        if len(documents) < self.min_topic_size * 2:
            logger.warning("Insufficient documents for topic modeling")
            return
        
        logger.info(f"Fitting topic model on {len(documents)} documents...")
        
        topics, probs = self.model.fit_transform(documents)
        
        self.is_fitted = True
        
        logger.info(f"Topic model fitted. Found {len(set(topics)) - 1} topics.")
        
    async def predict(self, text: str) -> Dict[str, Any]:
        """
        Predict topics for a document.
        
        Args:
            text: Input text
            
        Returns:
            Topic predictions
        """
        if not self.is_fitted:
            return {
                "topics": [-1],
                "topic_names": ["Unknown"],
                "probabilities": {},
                "keywords": {}
            }
        
        cache_key = None
        if self.cache:
            cache_key = f"topic:{hashlib.md5(text.encode()).hexdigest()}"
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        topics, probs = self.model.transform([text])
        
        # Get topic info
        topic_info = self.model.get_topic_info()
        
        # Get keywords for top topics
        topic_keywords = {}
        for topic_id in topics:
            if topic_id != -1:
                keywords = self.model.get_topic(topic_id)
                topic_keywords[int(topic_id)] = [kw[0] for kw in keywords[:5]]
        
        # Get topic names
        topic_names = []
        for topic_id in topics:
            if topic_id == -1:
                topic_names.append("Outlier")
            else:
                name_row = topic_info[topic_info["Topic"] == topic_id]
                if not name_row.empty:
                    topic_names.append(name_row["Name"].values[0])
                else:
                    topic_names.append(f"Topic_{topic_id}")
        
        result = {
            "topics": [int(t) for t in topics],
            "topic_names": topic_names,
            "probabilities": {
                int(t): float(p) 
                for t, p in zip(topics, probs[0])
            } if probs is not None and len(probs) > 0 else {},
            "keywords": topic_keywords
        }
        
        if self.cache and cache_key:
            await self.cache.setex(cache_key, 3600, json.dumps(result))
        
        return result
    
    def get_topic_keywords(self, topic_id: int, n_words: int = 10) -> List[str]:
        """Get top keywords for a topic."""
        if not self.is_fitted or topic_id == -1:
            return []
        
        keywords = self.model.get_topic(topic_id)
        return [kw[0] for kw in keywords[:n_words]] if keywords else []


class Summarizer:
    """
    Text summarization for financial news.
    
    Supports:
    - Extractive: TF-IDF based sentence selection
    - Abstractive: BART/CNN fine-tuned for financial news
    """
    
    def __init__(
        self,
        abstractive_model: str = "facebook/bart-large-cnn",
        device: str = None,
        cache: redis.Redis = None
    ):
        self.device = device or ("cuda" if self._check_cuda() else "cpu")
        self.cache = cache
        
        # Initialize extractive components
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000
        )
        
        # Initialize abstractive model
        logger.info(f"Loading abstractive summarization model: {abstractive_model}")
        self.abstractive_tokenizer = AutoTokenizer.from_pretrained(abstractive_model)
        self.abstractive_model = AutoModelForSeq2SeqLM.from_pretrained(
            abstractive_model
        ).to(self.device)
        
    def _check_cuda(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    async def summarize(
        self, 
        text: str,
        method: str = "extractive",
        max_length: int = 150,
        min_length: int = 30
    ) -> Dict[str, Any]:
        """
        Summarize text.
        
        Args:
            text: Input text
            method: 'extractive' or 'abstractive'
            max_length: Maximum summary length
            min_length: Minimum summary length
            
        Returns:
            Summary result
        """
        cache_key = None
        if self.cache:
            cache_key = f"summary:{method}:{hashlib.md5(text.encode()).hexdigest()}"
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        if method == "extractive":
            result = self._extractive_summarize(text, max_length)
        else:
            result = await self._abstractive_summarize(text, max_length, min_length)
        
        result["method"] = method
        result["original_length"] = len(text)
        
        if self.cache and cache_key:
            await self.cache.setex(cache_key, 3600, json.dumps(result))
        
        return result
    
    def _extractive_summarize(self, text: str, max_length: int) -> Dict[str, Any]:
        """Extractive summarization using TF-IDF."""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        if len(sentences) <= 3:
            return {
                "summary": text,
                "sentence_count": len(sentences),
                "compression_ratio": 1.0
            }
        
        # Score sentences
        try:
            tfidf_matrix = self.vectorizer.fit_transform(sentences)
            sentence_scores = np.array(tfidf_matrix.sum(axis=1)).flatten()
            
            # Select top sentences
            num_sentences = max(2, min(len(sentences) // 3, 5))
            top_indices = np.argsort(sentence_scores)[-num_sentences:]
            top_indices = sorted(top_indices)  # Maintain original order
            
            summary_sentences = [sentences[i] for i in top_indices]
            summary = ' '.join(summary_sentences)
            
            return {
                "summary": summary,
                "sentence_count": num_sentences,
                "compression_ratio": len(summary) / len(text)
            }
            
        except ValueError:
            # Fallback for very short texts
            return {
                "summary": text[:max_length] + "..." if len(text) > max_length else text,
                "sentence_count": 1,
                "compression_ratio": len(text[:max_length]) / len(text) if len(text) > max_length else 1.0
            }
    
    async def _abstractive_summarize(
        self, 
        text: str, 
        max_length: int,
        min_length: int
    ) -> Dict[str, Any]:
        """Abstractive summarization using BART."""
        import torch
        
        # Truncate if too long
        inputs = self.abstractive_tokenizer(
            text[:1024],
            return_tensors="pt",
            truncation=True,
            max_length=1024
        ).to(self.device)
        
        with torch.no_grad():
            summary_ids = self.abstractive_model.generate(
                inputs["input_ids"],
                max_length=max_length,
                min_length=min_length,
                num_beams=4,
                early_stopping=True
            )
        
        summary = self.abstractive_tokenizer.decode(
            summary_ids[0], 
            skip_special_tokens=True
        )
        
        return {
            "summary": summary,
            "sentence_count": len(re.split(r'(?<=[.!?])\s+', summary)),
            "compression_ratio": len(summary) / len(text)
        }


class NLPPipeline:
    """
    End-to-end NLP pipeline for financial news processing.
    
    Orchestrates multiple NLP components with caching and async processing.
    """
    
    def __init__(
        self,
        config: Dict[str, Any] = None,
        cache_url: str = None,
        device: str = None
    ):
        self.config = config or {}
        self.cache = redis.from_url(cache_url) if cache_url else None
        self.device = device
        
        # Initialize components
        self.preprocessor = TextPreprocessor()
        self.sentiment_analyzer = None
        self.entity_extractor = None
        self.topic_modeler = None
        self.summarizer = None
        
        self._initialized = False
        
    async def initialize(self):
        """Initialize all NLP components."""
        if self._initialized:
            return
        
        logger.info("Initializing NLP Pipeline...")
        
        # Initialize sentiment analyzer
        if self.config.get("sentiment", {}).get("enabled", True):
            self.sentiment_analyzer = SentimentAnalyzer(
                model_name=self.config.get("sentiment", {}).get("model"),
                device=self.device,
                cache=self.cache
            )
        
        # Initialize entity extractor
        if self.config.get("ner", {}).get("enabled", True):
            self.entity_extractor = EntityExtractor(
                model_name=self.config.get("ner", {}).get("model", "en_core_web_trf"),
                cache=self.cache
            )
        
        # Initialize topic modeler
        if self.config.get("topic_modeling", {}).get("enabled", True):
            self.topic_modeler = TopicModeler(
                n_topics=self.config.get("topic_modeling", {}).get("n_topics", 50),
                cache=self.cache
            )
        
        # Initialize summarizer
        if self.config.get("summarization", {}).get("enabled", True):
            self.summarizer = Summarizer(
                abstractive_model=self.config.get("summarization", {}).get("model"),
                device=self.device,
                cache=self.cache
            )
        
        self._initialized = True
        logger.info("NLP Pipeline initialized successfully")
    
    async def shutdown(self):
        """Cleanup resources."""
        if self.cache:
            await self.cache.close()
    
    async def process(
        self, 
        article: Any,
        include_sentiment: bool = True,
        include_entities: bool = True,
        include_topics: bool = True,
        include_summary: bool = True
    ) -> NLPResult:
        """
        Process article through full NLP pipeline.
        
        Args:
            article: Article object or dict with title, content
            include_*: Flags to enable/disable specific components
            
        Returns:
            Complete NLP processing result
        """
        if not self._initialized:
            await self.initialize()
        
        import time
        start_time = time.time()
        
        # Extract text
        if hasattr(article, 'content'):
            text = f"{article.title}. {article.content}"
            article_id = getattr(article, 'id', 'unknown')
        else:
            text = f"{article.get('title', '')}. {article.get('content', '')}"
            article_id = article.get('id', 'unknown')
        
        # Preprocess
        preprocessed = self.preprocessor.preprocess(text)
        
        # Initialize result
        result = NLPResult(
            article_id=article_id,
            processed_at=datetime.now()
        )
        
        # Run components concurrently where possible
        tasks = []
        
        if include_sentiment and self.sentiment_analyzer:
            tasks.append(self._run_sentiment(preprocessed["cleaned_text"]))
        else:
            tasks.append(asyncio.sleep(0))
        
        if include_entities and self.entity_extractor:
            tasks.append(self._run_ner(preprocessed["cleaned_text"]))
        else:
            tasks.append(asyncio.sleep(0))
        
        if include_topics and self.topic_modeler:
            tasks.append(self._run_topic_modeling(preprocessed["cleaned_text"]))
        else:
            tasks.append(asyncio.sleep(0))
        
        if include_summary and self.summarizer:
            tasks.append(self._run_summarization(text))
        else:
            tasks.append(asyncio.sleep(0))
        
        # Execute all tasks
        sentiment_result, ner_result, topic_result, summary_result = await asyncio.gather(*tasks)
        
        # Populate result
        if sentiment_result:
            result.sentiment_score = sentiment_result["sentiment_score"]
            result.sentiment_confidence = sentiment_result["sentiment_confidence"]
            result.sentiment_label = sentiment_result["sentiment_label"]
            result.raw_scores["sentiment"] = sentiment_result["raw_scores"]
        
        if ner_result:
            result.entities = ner_result["entities"]
            result.tickers = ner_result["tickers"]
            result.companies = ner_result["companies"]
            result.people = ner_result["people"]
        
        if topic_result:
            result.topics = topic_result["topics"]
            result.topic_keywords = topic_result["keywords"]
        
        if summary_result:
            result.summary = summary_result["summary"]
            result.summary_type = summary_result["method"]
        
        # Add metadata
        result.processing_time_ms = (time.time() - start_time) * 1000
        result.model_versions = {
            "sentiment": getattr(self.sentiment_analyzer, 'model_name', 'N/A') if self.sentiment_analyzer else 'N/A',
            "ner": getattr(self.entity_extractor, 'model_name', 'N/A') if self.entity_extractor else 'N/A',
        }
        
        return result
    
    async def _run_sentiment(self, text: str) -> Dict[str, Any]:
        """Run sentiment analysis."""
        return await self.sentiment_analyzer.analyze(text, self.preprocessor)
    
    async def _run_ner(self, text: str) -> Dict[str, Any]:
        """Run named entity recognition."""
        return await self.entity_extractor.extract(text, self.preprocessor)
    
    async def _run_topic_modeling(self, text: str) -> Dict[str, Any]:
        """Run topic modeling."""
        return await self.topic_modeler.predict(text)
    
    async def _run_summarization(self, text: str) -> Dict[str, Any]:
        """Run summarization."""
        method = self.config.get("summarization", {}).get("method", "extractive")
        max_length = self.config.get("summarization", {}).get("max_length", 150)
        min_length = self.config.get("summarization", {}).get("min_length", 30)
        
        return await self.summarizer.summarize(text, method, max_length, min_length)
    
    async def batch_process(
        self, 
        articles: List[Any],
        **kwargs
    ) -> List[NLPResult]:
        """
        Process multiple articles in batch.
        
        Args:
            articles: List of articles
            **kwargs: Additional arguments for process()
            
        Returns:
            List of NLP results
        """
        tasks = [self.process(article, **kwargs) for article in articles]
        return await asyncio.gather(*tasks)
    
    async def fit_topics(self, documents: List[str]):
        """Fit topic model on corpus."""
        if self.topic_modeler:
            await self.topic_modeler.fit(documents)


# Example usage
async def main():
    """Demo NLP pipeline capabilities."""
    
    config = {
        "sentiment": {"enabled": True},
        "ner": {"enabled": True},
        "topic_modeling": {"enabled": True, "n_topics": 10},
        "summarization": {"enabled": True, "method": "extractive"}
    }
    
    pipeline = NLPPipeline(config)
    await pipeline.initialize()
    
    # Sample articles
    articles = [
        {
            "id": "1",
            "title": "Apple Reports Record Q4 Earnings, Beats Wall Street Expectations",
            "content": """
            Apple Inc. (AAPL) reported record-breaking fourth quarter earnings today,
            beating Wall Street expectations with revenue of $89.5 billion. CEO Tim Cook
            attributed the strong performance to robust iPhone 15 sales and growth in
            services revenue. The company announced a dividend increase and additional
            share buybacks. Analysts at Goldman Sachs raised their price target to $220.
            The stock gained 3.5% in after-hours trading.
            """
        },
        {
            "id": "2", 
            "title": "Federal Reserve Signals Potential Rate Cuts in 2024",
            "content": """
            The Federal Reserve indicated it may begin cutting interest rates in 2024
            as inflation shows signs of cooling. Fed Chair Jerome Powell noted that
            the central bank is confident in the trajectory toward its 2% inflation target.
            The comments sparked a rally in growth stocks, particularly in the technology
            sector. Treasury yields fell sharply following the announcement.
            """
        }
    ]
    
    print("Processing articles through NLP pipeline...\n")
    
    for article in articles:
        result = await pipeline.process(article)
        
        print(f"Article: {article['title'][:50]}...")
        print(f"  Sentiment: {result.sentiment_label} ({result.sentiment_score:.3f})")
        print(f"  Tickers: {', '.join(result.tickers)}")
        print(f"  People: {', '.join(result.people)}")
        print(f"  Topics: {result.topics}")
        print(f"  Summary: {result.summary[:100]}...")
        print(f"  Processing time: {result.processing_time_ms:.1f}ms")
        print()
    
    await pipeline.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
