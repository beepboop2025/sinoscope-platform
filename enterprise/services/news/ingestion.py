"""
DragonScope News Ingestion Service

Enterprise-grade news aggregation from 50+ sources including premium APIs,
social media, regulatory filings, and alternative data sources.
"""

import asyncio
import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set, Union
from urllib.parse import urlparse
import aiohttp
import feedparser
import redis.asyncio as redis
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SourceType(Enum):
    """News source categories."""
    PREMIUM_API = "premium_api"
    FINANCIAL_MEDIA = "financial_media"
    SOCIAL_MEDIA = "social_media"
    REGULATORY = "regulatory"
    ALTERNATIVE = "alternative"
    RSS = "rss"


class Priority(Enum):
    """Article priority levels."""
    BREAKING = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class Article:
    """Standardized news article format."""
    id: str
    title: str
    content: str
    summary: Optional[str]
    source: str
    source_type: SourceType
    url: str
    published_at: datetime
    tickers: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    raw_content: Optional[Dict] = None

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique article ID."""
        content_hash = hashlib.sha256(
            f"{self.title}{self.source}{self.published_at}".encode()
        ).hexdigest()[:16]
        return f"article_{content_hash}"


@dataclass
class NewsFilter:
    """Filter configuration for news ingestion."""
    tickers: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    source_types: Optional[List[SourceType]] = None
    categories: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    keywords: Optional[List[str]] = None
    min_priority: Priority = Priority.LOW
    exclude_patterns: Optional[List[str]] = None

    def matches(self, article: Article) -> bool:
        """Check if article matches filter criteria."""
        if self.tickers and not any(t in article.tickers for t in self.tickers):
            return False
        if self.sources and article.source not in self.sources:
            return False
        if self.source_types and article.source_type not in self.source_types:
            return False
        if self.start_date and article.published_at < self.start_date:
            return False
        if self.end_date and article.published_at > self.end_date:
            return False
        if self.keywords and not any(
            kw.lower() in article.title.lower() or 
            kw.lower() in article.content.lower() 
            for kw in self.keywords
        ):
            return False
        if article.priority.value > self.min_priority.value:
            return False
        if self.exclude_patterns:
            for pattern in self.exclude_patterns:
                if re.search(pattern, article.title, re.IGNORECASE):
                    return False
        return True


class BaseConnector(ABC):
    """Abstract base class for news connectors."""
    
    def __init__(self, config: Dict[str, Any], cache: Optional[redis.Redis] = None):
        self.config = config
        self.cache = cache
        self.name = self.__class__.__name__.replace("Connector", "").lower()
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = asyncio.Semaphore(config.get("rate_limit", 10))
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch articles from source."""
        pass
    
    @abstractmethod
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream real-time articles."""
        pass
    
    async def _fetch_with_cache(self, cache_key: str, fetch_fn: Callable) -> Any:
        """Fetch with Redis caching."""
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        result = await fetch_fn()
        
        if self.cache and result:
            await self.cache.setex(
                cache_key, 
                self.config.get("cache_ttl", 300),
                json.dumps(result, default=str)
            )
        
        return result
    
    async def _make_request(self, url: str, headers: Dict = None, **kwargs) -> Any:
        """Make rate-limited HTTP request."""
        async with self._rate_limiter:
            try:
                async with self.session.get(url, headers=headers, **kwargs) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except Exception as e:
                logger.error(f"Request failed for {url}: {e}")
                raise


class BloombergConnector(BaseConnector):
    """Bloomberg API connector (premium)."""
    
    BASE_URL = "https://api.bloomberg.com/news"
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch Bloomberg news."""
        headers = {"Authorization": f"Bearer {self.config['api_key']}"}
        
        params = {"limit": self.config.get("limit", 100)}
        if filter_config and filter_config.tickers:
            params["tickers"] = ",".join(filter_config.tickers)
        
        data = await self._make_request(
            f"{self.BASE_URL}/v1/stories",
            headers=headers,
            params=params
        )
        
        articles = []
        for item in data.get("stories", []):
            article = Article(
                id=f"bloomberg_{item['id']}",
                title=item["headline"],
                content=item.get("body", ""),
                summary=item.get("abstract"),
                source="Bloomberg",
                source_type=SourceType.PREMIUM_API,
                url=item.get("url", ""),
                published_at=datetime.fromisoformat(item["published_at"]),
                tickers=item.get("tickers", []),
                authors=item.get("authors", []),
                categories=item.get("categories", []),
                priority=Priority.BREAKING if item.get("is_breaking") else Priority.HIGH,
                raw_content=item
            )
            articles.append(article)
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream Bloomberg real-time news."""
        ws_url = f"{self.BASE_URL}/v1/stream"
        # WebSocket implementation for real-time streaming
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 30))


class ReutersConnector(BaseConnector):
    """Reuters API connector (premium)."""
    
    BASE_URL = "https://api.reuters.com/content"
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch Reuters news."""
        headers = {"X-Api-Key": self.config["api_key"]}
        
        params = {"size": self.config.get("limit", 100)}
        if filter_config and filter_config.tickers:
            params["q"] = " OR ".join(filter_config.tickers)
        
        data = await self._make_request(
            f"{self.BASE_URL}/news",
            headers=headers,
            params=params
        )
        
        articles = []
        for item in data.get("newsItems", []):
            article = Article(
                id=f"reuters_{item['id']}",
                title=item["headline"],
                content=item.get("body", ""),
                summary=item.get("snippet"),
                source="Reuters",
                source_type=SourceType.PREMIUM_API,
                url=item.get("uri", ""),
                published_at=datetime.fromisoformat(item["versionCreated"]),
                tickers=self._extract_tickers(item.get("subjects", [])),
                authors=[item.get("byline", "")] if item.get("byline") else [],
                categories=item.get("subjects", []),
                priority=Priority.HIGH,
                raw_content=item
            )
            articles.append(article)
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream Reuters real-time news."""
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 60))
    
    def _extract_tickers(self, subjects: List[str]) -> List[str]:
        """Extract ticker symbols from Reuters subjects."""
        tickers = []
        for subject in subjects:
            if subject.startswith("R:"):
                tickers.append(subject.replace("R:", ""))
        return tickers


class CNBCConnector(BaseConnector):
    """CNBC API connector."""
    
    BASE_URL = "https://www.cnbc.com/api/v1"
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch CNBC news."""
        endpoints = [
            f"{self.BASE_URL}/topStories",
            f"{self.BASE_URL}/marketNews",
            f"{self.BASE_URL}/breakingNews"
        ]
        
        articles = []
        for endpoint in endpoints:
            try:
                data = await self._make_request(endpoint)
                for item in data.get("articles", []):
                    article = Article(
                        id=f"cnbc_{item['id']}",
                        title=item["headline"],
                        content=item.get("description", ""),
                        summary=item.get("description"),
                        source="CNBC",
                        source_type=SourceType.FINANCIAL_MEDIA,
                        url=item.get("url", ""),
                        published_at=datetime.fromtimestamp(item["datePublished"]),
                        tickers=item.get("relatedSymbols", []),
                        authors=[item.get("author", "")] if item.get("author") else [],
                        categories=item.get("sections", []),
                        priority=Priority.BREAKING if "breaking" in endpoint else Priority.NORMAL,
                        raw_content=item
                    )
                    articles.append(article)
            except Exception as e:
                logger.error(f"CNBC fetch error: {e}")
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream CNBC real-time news."""
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 45))


class TwitterConnector(BaseConnector):
    """Twitter/X API connector for financial accounts."""
    
    BASE_URL = "https://api.twitter.com/2"
    
    DEFAULT_ACCOUNTS = [
        "DeItaone",
        "FirstSquawk",
        "CNBCnow",
        "WSJ",
        "FT",
        "BloombergDeals",
        "markhufty",
        "NickTimiraos",
    ]
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch tweets from financial accounts."""
        headers = {"Authorization": f"Bearer {self.config['bearer_token']}"}
        
        accounts = self.config.get("accounts", self.DEFAULT_ACCOUNTS)
        articles = []
        
        for username in accounts:
            try:
                cache_key = f"twitter:{username}"
                
                async def fetch_tweets():
                    user_url = f"{self.BASE_URL}/users/by/username/{username}"
                    async with self._rate_limiter:
                        async with self.session.get(user_url, headers=headers) as resp:
                            user_data = await resp.json()
                            user_id = user_data["data"]["id"]
                    
                    tweets_url = f"{self.BASE_URL}/users/{user_id}/tweets"
                    params = {
                        "max_results": 20,
                        "tweet.fields": "created_at,public_metrics,entities",
                        "exclude": "retweets,replies"
                    }
                    
                    async with self._rate_limiter:
                        async with self.session.get(tweets_url, headers=headers, params=params) as resp:
                            return await resp.json()
                
                data = await self._fetch_with_cache(cache_key, fetch_tweets)
                
                for tweet in data.get("data", []):
                    metrics = tweet.get("public_metrics", {})
                    
                    if metrics.get("like_count", 0) < self.config.get("min_likes", 50):
                        continue
                    
                    tickers = []
                    entities = tweet.get("entities", {})
                    for cashtag in entities.get("cashtags", []):
                        tickers.append(cashtag["tag"].upper())
                    
                    article = Article(
                        id=f"twitter_{tweet['id']}",
                        title=tweet["text"][:100] + "..." if len(tweet["text"]) > 100 else tweet["text"],
                        content=tweet["text"],
                        summary=None,
                        source=f"Twitter/@{username}",
                        source_type=SourceType.SOCIAL_MEDIA,
                        url=f"https://twitter.com/{username}/status/{tweet['id']}",
                        published_at=datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00")),
                        tickers=tickers,
                        authors=[username],
                        categories=["social_media"],
                        priority=Priority.BREAKING if metrics.get("retweet_count", 0) > 1000 else Priority.NORMAL,
                        raw_content={"tweet": tweet, "metrics": metrics}
                    )
                    articles.append(article)
                    
            except Exception as e:
                logger.error(f"Twitter fetch error for {username}: {e}")
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream tweets via filtered stream API."""
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 30))


class RedditConnector(BaseConnector):
    """Reddit API connector for financial subreddits."""
    
    BASE_URL = "https://www.reddit.com"
    OAUTH_URL = "https://oauth.reddit.com"
    
    DEFAULT_SUBREDDITS = [
        "wallstreetbets",
        "stocks",
        "investing",
        "SecurityAnalysis",
        "finance",
        "options",
        "pennystocks"
    ]
    
    async def __aenter__(self):
        await super().__aenter__()
        await self._authenticate()
        return self
    
    async def _authenticate(self):
        """Authenticate with Reddit API."""
        auth = aiohttp.BasicAuth(
            self.config["client_id"],
            self.config["client_secret"]
        )
        
        data = {
            "grant_type": "password",
            "username": self.config["username"],
            "password": self.config["password"]
        }
        
        headers = {"User-Agent": self.config.get("user_agent", "DragonScope/1.0")}
        
        async with self.session.post(
            f"{self.BASE_URL}/api/v1/access_token",
            auth=auth,
            data=data,
            headers=headers
        ) as resp:
            token_data = await resp.json()
            self._access_token = token_data["access_token"]
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch posts from financial subreddits."""
        subreddits = self.config.get("subreddits", self.DEFAULT_SUBREDDITS)
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": self.config.get("user_agent", "DragonScope/1.0")
        }
        
        articles = []
        
        for subreddit in subreddits:
            try:
                cache_key = f"reddit:{subreddit}"
                
                async def fetch_posts():
                    url = f"{self.OAUTH_URL}/r/{subreddit}/hot"
                    params = {"limit": 25}
                    async with self._rate_limiter:
                        async with self.session.get(url, headers=headers, params=params) as resp:
                            return await resp.json()
                
                data = await self._fetch_with_cache(cache_key, fetch_posts)
                
                for post in data.get("data", {}).get("children", []):
                    post_data = post["data"]
                    
                    score = post_data.get("score", 0)
                    if score < self.config.get("min_score", 100):
                        continue
                    
                    tickers = self._extract_tickers(post_data.get("title", ""))
                    
                    article = Article(
                        id=f"reddit_{post_data['id']}",
                        title=post_data["title"],
                        content=post_data.get("selftext", ""),
                        summary=post_data.get("selftext", "")[:200] if post_data.get("selftext") else None,
                        source=f"Reddit/r/{subreddit}",
                        source_type=SourceType.SOCIAL_MEDIA,
                        url=f"https://reddit.com{post_data['permalink']}",
                        published_at=datetime.fromtimestamp(post_data["created_utc"]),
                        tickers=tickers,
                        authors=[post_data.get("author", "")],
                        categories=[subreddit],
                        priority=Priority.HIGH if score > 1000 else Priority.NORMAL,
                        raw_content={
                            "post": post_data,
                            "score": score,
                            "upvote_ratio": post_data.get("upvote_ratio")
                        }
                    )
                    articles.append(article)
                    
            except Exception as e:
                logger.error(f"Reddit fetch error for r/{subreddit}: {e}")
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream Reddit posts."""
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 60))
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract ticker symbols from text using regex."""
        patterns = [
            r'\$([A-Z]{1,5})\b',
            r'\b([A-Z]{2,5})\b'
        ]
        
        tickers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            tickers.extend(matches)
        
        common_words = {"CEO", "CFO", "CTO", "THE", "AND", "FOR", "IPO", "EPS", "GDP", "FED", "USA"}
        return [t for t in tickers if t not in common_words]


class SECConnector(BaseConnector):
    """SEC EDGAR filings connector."""
    
    BASE_URL = "https://www.sec.gov/Archives/edgar"
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch recent SEC filings."""
        headers = {"User-Agent": self.config.get("user_agent", "DragonScope Enterprise contact@dragonscope.com")}
        
        current_date = datetime.now()
        articles = []
        
        for days_back in range(1, self.config.get("lookback_days", 3)):
            date = current_date - timedelta(days=days_back)
            date_str = date.strftime("%Y%m%d")
            
            try:
                cache_key = f"sec:filings:{date_str}"
                
                async def fetch_filings():
                    url = f"{self.BASE_URL}/daily-index/form-idx/form.{date_str}.idx"
                    async with self._rate_limiter:
                        async with self.session.get(url, headers=headers) as resp:
                            return await resp.text()
                
                content = await self._fetch_with_cache(cache_key, fetch_filings)
                filings = self._parse_idx(content)
                
                for filing in filings:
                    form_type = filing.get("form_type", "")
                    if form_type not in ["8-K", "6-K", "425", "SC 13D", "SC 13G"]:
                        continue
                    
                    if filter_config and filter_config.tickers:
                        if filing.get("cik") not in filter_config.tickers:
                            continue
                    
                    article = Article(
                        id=f"sec_{filing['accession_number']}",
                        title=f"{filing['company_name']} - {form_type} Filing",
                        content=f"SEC {form_type} filing for {filing['company_name']}",
                        summary=f"Form {form_type} filed with SEC",
                        source="SEC EDGAR",
                        source_type=SourceType.REGULATORY,
                        url=filing.get("url", ""),
                        published_at=date,
                        tickers=[filing.get("cik", "")],
                        authors=["SEC"],
                        categories=["regulatory", form_type],
                        priority=Priority.HIGH,
                        raw_content=filing
                    )
                    articles.append(article)
                    
            except Exception as e:
                logger.error(f"SEC fetch error for {date_str}: {e}")
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream new SEC filings."""
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 300))
    
    def _parse_idx(self, content: str) -> List[Dict]:
        """Parse SEC IDX file format."""
        filings = []
        lines = content.split("\n")
        
        data_started = False
        for line in lines:
            if "-" * 50 in line:
                data_started = True
                continue
            
            if data_started and line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    filings.append({
                        "company_name": " ".join(parts[:-4]),
                        "form_type": parts[-4],
                        "cik": parts[-3],
                        "date_filed": parts[-2],
                        "accession_number": parts[-1]
                    })
        
        return filings


class RSSAggregator(BaseConnector):
    """Generic RSS feed aggregator."""
    
    DEFAULT_FEEDS = [
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "Yahoo Finance"),
        ("https://www.marketwatch.com/rss/topstories", "MarketWatch"),
        ("https://seekingalpha.com/feed.xml", "Seeking Alpha"),
        ("https://www.fool.com/feed/index.xml", "Motley Fool"),
        ("https://www.federalreserve.gov/feeds/press_all.xml", "Federal Reserve"),
        ("https://www.bls.gov/feed/news.rss", "BLS Economic News"),
        ("https://techcrunch.com/feed/", "TechCrunch"),
        ("https://cointelegraph.com/rss", "Cointelegraph"),
        ("https://coindesk.com/arc/outboundfeeds/rss/", "CoinDesk"),
    ]
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Fetch RSS feeds."""
        feeds = self.config.get("feeds", self.DEFAULT_FEEDS)
        articles = []
        
        for feed_url, feed_name in feeds:
            try:
                cache_key = f"rss:{hashlib.md5(feed_url.encode()).hexdigest()}"
                
                async def fetch_feed():
                    async with self._rate_limiter:
                        async with self.session.get(feed_url) as resp:
                            return await resp.text()
                
                content = await self._fetch_with_cache(cache_key, fetch_feed)
                parsed = feedparser.parse(content)
                
                for entry in parsed.entries[:self.config.get("entries_per_feed", 20)]:
                    article = Article(
                        id=f"rss_{hashlib.md5(entry.link.encode()).hexdigest()[:16]}",
                        title=entry.title,
                        content=entry.get("summary", entry.get("description", "")),
                        summary=entry.get("summary", "")[:200] if entry.get("summary") else None,
                        source=feed_name,
                        source_type=SourceType.RSS,
                        url=entry.link,
                        published_at=self._parse_date(entry),
                        tickers=self._extract_tickers(entry),
                        authors=[entry.get("author", "")] if entry.get("author") else [],
                        categories=[tag.term for tag in entry.get("tags", [])],
                        priority=Priority.NORMAL,
                        raw_content=dict(entry)
                    )
                    articles.append(article)
                    
            except Exception as e:
                logger.error(f"RSS fetch error for {feed_name}: {e}")
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream RSS feeds."""
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 300))
    
    def _parse_date(self, entry) -> datetime:
        """Parse various date formats from RSS."""
        for field in ["published_parsed", "updated_parsed", "created_parsed"]:
            if hasattr(entry, field):
                import time
                t = getattr(entry, field)
                if t:
                    return datetime.fromtimestamp(time.mktime(t))
        return datetime.now()
    
    def _extract_tickers(self, entry) -> List[str]:
        """Extract tickers from RSS entry."""
        tickers = []
        text = f"{entry.title} {entry.get('summary', '')}"
        
        if hasattr(entry, 'yfinance_ticker'):
            tickers.append(entry.yfinance_ticker)
        
        pattern = r'\$([A-Z]{1,5})\b'
        tickers.extend(re.findall(pattern, text))
        
        return list(set(tickers))


class WebScraper(BaseConnector):
    """Generic web scraper for news sites without APIs."""
    
    SCRAPER_CONFIGS = {
        "investopedia": {
            "url": "https://www.investopedia.com/news/",
            "article_selector": "article",
            "title_selector": "h2 a",
            "link_selector": "h2 a",
            "content_selector": ".article-body",
            "base_url": "https://www.investopedia.com"
        }
    }
    
    async def fetch(self, filter_config: Optional[NewsFilter] = None) -> List[Article]:
        """Scrape configured websites."""
        configs = self.config.get("sites", self.SCRAPER_CONFIGS)
        articles = []
        
        for site_name, site_config in configs.items():
            try:
                cache_key = f"scrape:{site_name}"
                
                async def scrape_site():
                    async with self._rate_limiter:
                        async with self.session.get(
                            site_config["url"],
                            headers={"User-Agent": self.config.get("user_agent", "DragonScopeBot/1.0")}
                        ) as resp:
                            return await resp.text()
                
                html = await self._fetch_with_cache(cache_key, scrape_site)
                soup = BeautifulSoup(html, 'html.parser')
                
                article_elements = soup.select(site_config["article_selector"])
                
                for elem in article_elements[:10]:
                    title_elem = elem.select_one(site_config["title_selector"])
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get("href", "")
                    if link and not link.startswith("http"):
                        link = site_config["base_url"] + link
                    
                    article = Article(
                        id=f"scrape_{hashlib.md5(link.encode()).hexdigest()[:16]}",
                        title=title,
                        content="",
                        summary=None,
                        source=site_name.capitalize(),
                        source_type=SourceType.FINANCIAL_MEDIA,
                        url=link,
                        published_at=datetime.now(),
                        tickers=[],
                        authors=[],
                        categories=[],
                        priority=Priority.NORMAL,
                        raw_content={"source": site_name}
                    )
                    articles.append(article)
                    
            except Exception as e:
                logger.error(f"Scrape error for {site_name}: {e}")
        
        return articles
    
    async def stream(self, filter_config: Optional[NewsFilter] = None) -> AsyncIterator[Article]:
        """Stream scraped articles."""
        while True:
            articles = await self.fetch(filter_config)
            for article in articles:
                yield article
            await asyncio.sleep(self.config.get("poll_interval", 600))


class NewsIngestor:
    """
    Main news ingestion orchestrator.
    
    Aggregates news from all configured sources with deduplication
    and filtering capabilities.
    """
    
    CONNECTOR_MAP = {
        "bloomberg": BloombergConnector,
        "reuters": ReutersConnector,
        "cnbc": CNBCConnector,
        "twitter": TwitterConnector,
        "reddit": RedditConnector,
        "sec": SECConnector,
        "rss": RSSAggregator,
        "web_scraper": WebScraper,
    }
    
    def __init__(self, config: Dict[str, Any] = None, cache_url: str = None):
        self.config = config or {}
        self.cache = redis.from_url(cache_url) if cache_url else None
        self.connectors: Dict[str, BaseConnector] = {}
        self._dedup_cache: Set[str] = set()
        self._dedup_max_size = 100000
        
    async def __aenter__(self):
        """Initialize all configured connectors."""
        for source_name, source_config in self.config.get("sources", {}).items():
            if not source_config.get("enabled", True):
                continue
                
            connector_class = self.CONNECTOR_MAP.get(source_name)
            if connector_class:
                connector = connector_class(source_config, self.cache)
                await connector.__aenter__()
                self.connectors[source_name] = connector
                logger.info(f"Initialized connector: {source_name}")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup connectors."""
        for connector in self.connectors.values():
            await connector.__aexit__(exc_type, exc_val, exc_tb)
        
        if self.cache:
            await self.cache.close()
    
    async def fetch_all(
        self, 
        filter_config: Optional[NewsFilter] = None,
        max_articles: int = 1000
    ) -> List[Article]:
        """Fetch articles from all sources."""
        all_articles = []
        
        tasks = [
            connector.fetch(filter_config)
            for connector in self.connectors.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for articles in results:
            if isinstance(articles, Exception):
                logger.error(f"Fetch error: {articles}")
                continue
            
            for article in articles:
                if self._is_duplicate(article):
                    continue
                if filter_config and not filter_config.matches(article):
                    continue
                
                all_articles.append(article)
                self._mark_duplicate(article)
                
                if len(all_articles) >= max_articles:
                    break
        
        all_articles.sort(key=lambda a: (a.priority.value, a.published_at), reverse=True)
        
        return all_articles[:max_articles]
    
    async def stream(
        self, 
        filter_config: Optional[NewsFilter] = None
    ) -> AsyncIterator[Article]:
        """
        Real-time stream from all sources.
        
        Yields deduplicated articles as they arrive.
        """
        queues: Dict[str, asyncio.Queue] = {
            name: asyncio.Queue(maxsize=1000)
            for name in self.connectors.keys()
        }
        
        async def producer(name: str, connector: BaseConnector):
            """Produce articles from a connector."""
            try:
                async for article in connector.stream(filter_config):
                    try:
                        queues[name].put_nowait(article)
                    except asyncio.QueueFull:
                        try:
                            queues[name].get_nowait()
                            queues[name].put_nowait(article)
                        except asyncio.QueueEmpty:
                            pass
            except Exception as e:
                logger.error(f"Stream error from {name}: {e}")
        
        producers = [
            asyncio.create_task(producer(name, conn))
            for name, conn in self.connectors.items()
        ]
        
        try:
            while True:
                for name, queue in queues.items():
                    try:
                        article = queue.get_nowait()
                        
                        if self._is_duplicate(article):
                            continue
                        if filter_config and not filter_config.matches(article):
                            continue
                        
                        self._mark_duplicate(article)
                        yield article
                        
                    except asyncio.QueueEmpty:
                        continue
                
                await asyncio.sleep(0.1)
                
        finally:
            for task in producers:
                task.cancel()
    
    async def fetch_historical(
        self,
        start: datetime,
        end: datetime,
        sources: Optional[List[str]] = None,
        tickers: Optional[List[str]] = None
    ) -> List[Article]:
        """
        Fetch historical articles from specified sources.
        
        Note: Historical data availability varies by source.
        """
        filter_config = NewsFilter(
            start_date=start,
            end_date=end,
            sources=sources,
            tickers=tickers
        )
        
        return await self.fetch_all(filter_config)
    
    def _is_duplicate(self, article: Article) -> bool:
        """Check if article is duplicate using content hash."""
        content_hash = hashlib.md5(
            f"{article.title}{article.source}".encode()
        ).hexdigest()
        return content_hash in self._dedup_cache
    
    def _mark_duplicate(self, article: Article):
        """Mark article as seen."""
        content_hash = hashlib.md5(
            f"{article.title}{article.source}".encode()
        ).hexdigest()
        
        if len(self._dedup_cache) >= self._dedup_max_size:
            self._dedup_cache.clear()
        
        self._dedup_cache.add(content_hash)
    
    def get_source_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics by source."""
        return {
            "active_sources": list(self.connectors.keys()),
            "dedup_cache_size": len(self._dedup_cache),
            "cache_max_size": self._dedup_max_size
        }


# Example usage
async def main():
    """Demo of NewsIngestor capabilities."""
    config = {
        "sources": {
            "rss": {
                "enabled": True,
                "poll_interval": 300,
                "entries_per_feed": 20
            },
            "web_scraper": {
                "enabled": True,
                "poll_interval": 600
            }
        }
    }
    
    async with NewsIngestor(config) as ingestor:
        print("Fetching recent articles...")
        articles = await ingestor.fetch_all(max_articles=10)
        for article in articles:
            print(f"[{article.source}] {article.title[:60]}...")
        
        print("\nStreaming real-time articles...")
        filter_config = NewsFilter(
            tickers=["AAPL", "TSLA"],
            min_priority=Priority.NORMAL
        )
        
        count = 0
        async for article in ingestor.stream(filter_config):
            print(f"[LIVE] [{article.source}] {article.title[:60]}...")
            count += 1
            if count >= 5:
                break


if __name__ == "__main__":
    asyncio.run(main())
