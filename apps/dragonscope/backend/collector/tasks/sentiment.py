import logging
import time

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch

logger = logging.getLogger(__name__)

BULLISH_WORDS = [
    "moon", "bull", "calls", "buy", "long", "pump", "rocket",
    "gain", "green", "breakout", "ath", "yolo", "tendies",
]
BEARISH_WORDS = [
    "bear", "puts", "sell", "short", "dump", "crash", "red",
    "loss", "dip", "down", "fear", "recession", "bag",
]


@celery_app.task(name="collector.tasks.sentiment.fetch_fear_greed")
def fetch_fear_greed():
    try:
        resp = safe_fetch("https://api.alternative.me/fng/?limit=30&format=json")
        data = resp.json()
        entries = [
            {
                "value": int(d.get("value", 0)),
                "label": d.get("value_classification", ""),
                "timestamp": int(d.get("timestamp", 0)) * 1000,
            }
            for d in data.get("data", [])
        ]
        save_data("fear_greed", entries, ttl=300)
        if entries:
            logger.info(f"[SENTIMENT] Fear & Greed updated: {entries[0]['value']} ({entries[0]['label']})")
    except Exception as e:
        logger.error(f"[SENTIMENT] Fear & Greed error: {e}")


@celery_app.task(name="collector.tasks.sentiment.fetch_reddit")
def fetch_reddit():
    subs = ["wallstreetbets", "cryptocurrency", "stocks", "investing", "CryptoMarkets"]
    all_posts = []

    for sub in subs:
        if not can_request("reddit"):
            break
        consume_token("reddit")
        try:
            resp = safe_fetch(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=15&raw_json=1",
                headers={"User-Agent": "DragonScope/1.0"},
            )
            data = resp.json()
            for child in data.get("data", {}).get("children", []):
                p = child.get("data", {})
                if p.get("stickied"):
                    continue
                all_posts.append({
                    "id": p.get("id", ""),
                    "title": p.get("title", ""),
                    "author": p.get("author", ""),
                    "score": p.get("score", 0),
                    "upvoteRatio": p.get("upvote_ratio", 0),
                    "numComments": p.get("num_comments", 0),
                    "created": int(p.get("created_utc", 0)) * 1000,
                    "subreddit": p.get("subreddit", ""),
                    "flair": p.get("link_flair_text") or "",
                    "url": f"https://reddit.com{p.get('permalink', '')}",
                    "selftext": (p.get("selftext") or "")[:150],
                })
        except Exception as e:
            logger.error(f"[REDDIT] {sub} error: {e}")
        time.sleep(1.5)

    all_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
    top = all_posts[:50]

    if top:
        # Compute sentiment
        bull_count = bear_count = neutral = 0
        for p in top:
            text = (p.get("title", "") + " " + p.get("flair", "")).lower()
            is_bull = any(w in text for w in BULLISH_WORDS)
            is_bear = any(w in text for w in BEARISH_WORDS)
            if is_bull and not is_bear:
                bull_count += 1
            elif is_bear and not is_bull:
                bear_count += 1
            else:
                neutral += 1

        total = len(top) or 1
        sentiment = {
            "bullish": round((bull_count / total) * 100),
            "bearish": round((bear_count / total) * 100),
            "neutral": round((neutral / total) * 100),
            "bullCount": bull_count,
            "bearCount": bear_count,
            "neutralCount": neutral,
            "total": len(top),
        }
        save_data("reddit_posts", top, ttl=1800)
        save_data("reddit_sentiment", sentiment, ttl=1800)
        logger.info(
            f"[REDDIT] Updated: {len(top)} posts | "
            f"Sentiment: {sentiment['bullish']}% bull / {sentiment['bearish']}% bear"
        )
