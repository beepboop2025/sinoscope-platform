import logging
import time
from datetime import datetime
from urllib.parse import quote

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(name="collector.tasks.news.fetch_news")
def fetch_news():
    articles = None

    # 1. Finnhub
    if articles is None and settings.FINNHUB_API_KEY and can_request("finnhub"):
        consume_token("finnhub")
        try:
            resp = safe_fetch(
                f"https://finnhub.io/api/v1/news?category=general&token={settings.FINNHUB_API_KEY}"
            )
            data = resp.json()
            articles = [
                {
                    "id": a.get("id"),
                    "title": a.get("headline", ""),
                    "summary": a.get("summary", ""),
                    "source": a.get("source", ""),
                    "url": a.get("url", ""),
                    "image": a.get("image", ""),
                    "time": (a.get("datetime", 0)) * 1000,
                    "category": a.get("category", ""),
                }
                for a in (data or [])[:20]
            ]
            if not articles:
                articles = None
        except Exception:
            articles = None

    # 2. NewsData.io
    if articles is None and settings.NEWSDATA_API_KEY and can_request("newsdata"):
        consume_token("newsdata")
        try:
            resp = safe_fetch(
                f"https://newsdata.io/api/1/latest?apikey={settings.NEWSDATA_API_KEY}"
                "&q=financial+markets&language=en&category=business"
            )
            data = resp.json()
            if data.get("status") == "success":
                articles = [
                    {
                        "id": a.get("article_id") or a.get("link", ""),
                        "title": a.get("title", ""),
                        "summary": (a.get("description") or "")[:200],
                        "source": a.get("source_name", "NewsData"),
                        "url": a.get("link", ""),
                        "image": a.get("image_url") or "",
                        "time": int(datetime.fromisoformat(a["pubDate"]).timestamp() * 1000)
                        if a.get("pubDate") else int(time.time() * 1000),
                        "category": "business",
                    }
                    for a in (data.get("results") or [])[:20]
                ]
                if not articles:
                    articles = None
        except Exception:
            articles = None

    # 3. NewsAPI.org
    if articles is None and settings.NEWSAPI_API_KEY and can_request("newsapiorg"):
        consume_token("newsapiorg")
        try:
            resp = safe_fetch(
                f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=20"
                f"&apiKey={settings.NEWSAPI_API_KEY}"
            )
            data = resp.json()
            if data.get("status") == "ok":
                articles = [
                    {
                        "id": a.get("url", ""),
                        "title": a.get("title", ""),
                        "summary": a.get("description") or "",
                        "source": (a.get("source") or {}).get("name", "NewsAPI"),
                        "url": a.get("url", ""),
                        "image": a.get("urlToImage") or "",
                        "time": int(datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00")).timestamp() * 1000)
                        if a.get("publishedAt") else int(time.time() * 1000),
                        "category": "business",
                    }
                    for a in (data.get("articles") or [])[:20]
                ]
                if not articles:
                    articles = None
        except Exception:
            articles = None

    # 4. WorldNewsAPI
    if articles is None and settings.WORLD_NEWS_API_KEY and can_request("worldnews"):
        consume_token("worldnews")
        try:
            resp = safe_fetch(
                f"https://api.worldnewsapi.com/search-news?text=stock+market+finance"
                f"&language=en&number=20&api-key={settings.WORLD_NEWS_API_KEY}"
            )
            data = resp.json()
            articles = [
                {
                    "id": str(a.get("id") or a.get("url", "")),
                    "title": a.get("title", ""),
                    "summary": (a.get("text") or "")[:200],
                    "source": a.get("source_country", "WorldNews"),
                    "url": a.get("url", ""),
                    "image": a.get("image") or "",
                    "time": int(datetime.fromisoformat(a["publish_date"]).timestamp() * 1000)
                    if a.get("publish_date") else int(time.time() * 1000),
                    "category": "business",
                }
                for a in (data.get("news") or [])[:20]
            ]
            if not articles:
                articles = None
        except Exception:
            articles = None

    # 5. GNews
    if articles is None and settings.GNEWS_API_KEY and can_request("gnews"):
        consume_token("gnews")
        try:
            q = quote("financial markets")
            resp = safe_fetch(
                f"https://gnews.io/api/v4/search?q={q}&token={settings.GNEWS_API_KEY}&lang=en&max=10"
            )
            data = resp.json()
            articles = [
                {
                    "id": a.get("url", ""),
                    "title": a.get("title", ""),
                    "summary": a.get("description", ""),
                    "source": (a.get("source") or {}).get("name", ""),
                    "url": a.get("url", ""),
                    "image": a.get("image", ""),
                    "time": int(datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00")).timestamp() * 1000)
                    if a.get("publishedAt") else int(time.time() * 1000),
                    "category": "general",
                }
                for a in (data.get("articles") or [])
            ]
            if not articles:
                articles = None
        except Exception:
            articles = None

    if articles:
        save_data("news", articles, ttl=1800)
        logger.info(f"[NEWS] Updated: {len(articles)} articles")
    else:
        logger.warning("[NEWS] No articles from any source")
