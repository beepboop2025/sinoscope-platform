import logging

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch

logger = logging.getLogger(__name__)


@celery_app.task(name="collector.tasks.crypto.fetch_crypto_markets")
def fetch_crypto_markets():
    if not can_request("coingecko"):
        return
    consume_token("coingecko")
    try:
        resp = safe_fetch(
            "https://api.coingecko.com/api/v3/coins/markets"
            "?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
            "&sparkline=true&price_change_percentage=1h,24h,7d"
        )
        data = resp.json()
        save_data("crypto_markets", data)
        logger.info(f"[CRYPTO] Markets updated: {len(data)} coins")
    except Exception as e:
        logger.error(f"[CRYPTO] Markets error: {e}")


@celery_app.task(name="collector.tasks.crypto.fetch_crypto_global")
def fetch_crypto_global():
    if not can_request("coingecko"):
        return
    consume_token("coingecko")
    try:
        resp = safe_fetch("https://api.coingecko.com/api/v3/global")
        raw = resp.json()
        d = raw.get("data", {})
        save_data("crypto_global", {
            "totalMarketCap": d.get("total_market_cap", {}).get("usd", 0),
            "totalVolume": d.get("total_volume", {}).get("usd", 0),
            "btcDominance": d.get("market_cap_percentage", {}).get("btc", 0),
            "ethDominance": d.get("market_cap_percentage", {}).get("eth", 0),
            "activeCryptos": d.get("active_cryptocurrencies", 0),
            "markets": d.get("markets", 0),
            "marketCapChange24h": d.get("market_cap_change_percentage_24h_usd", 0),
        })
        logger.info("[CRYPTO] Global data updated")
    except Exception as e:
        logger.error(f"[CRYPTO] Global error: {e}")


@celery_app.task(name="collector.tasks.crypto.fetch_trending_coins")
def fetch_trending_coins():
    if not can_request("coingecko"):
        return
    consume_token("coingecko")
    try:
        resp = safe_fetch("https://api.coingecko.com/api/v3/search/trending")
        data = resp.json()
        coins = []
        for c in data.get("coins", []):
            item = c.get("item", {})
            coins.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "rank": item.get("market_cap_rank"),
                "priceBtc": item.get("price_btc"),
                "score": item.get("score"),
            })
        save_data("crypto_trending", coins, ttl=21600)
        logger.info(f"[CRYPTO] Trending updated: {len(coins)} coins")
    except Exception as e:
        logger.error(f"[CRYPTO] Trending error: {e}")
