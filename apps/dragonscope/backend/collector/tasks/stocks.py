import logging
import time

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "V", "WMT"]


@celery_app.task(name="collector.tasks.stocks.fetch_stocks")
def fetch_stocks():
    av_key = settings.ALPHA_VANTAGE_API_KEY
    if not av_key:
        logger.warning("[STOCKS] No Alpha Vantage key")
        return

    results = []
    for sym in SYMBOLS:
        if not can_request("alphavantage"):
            break
        consume_token("alphavantage")
        try:
            resp = safe_fetch(
                f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={sym}&apikey={av_key}"
            )
            data = resp.json()
            if data.get("Note") or data.get("Information"):
                logger.warning(f"[STOCKS] AV rate limited at {sym}")
                break
            gq = data.get("Global Quote", {})
            if gq.get("05. price"):
                results.append({
                    "symbol": gq.get("01. symbol", sym),
                    "price": float(gq.get("05. price", 0) or 0),
                    "change": float(gq.get("09. change", 0) or 0),
                    "changePct": float(str(gq.get("10. change percent", "0")).replace("%", "") or 0),
                    "volume": int(gq.get("06. volume", 0) or 0),
                    "high": float(gq.get("03. high", 0) or 0),
                    "low": float(gq.get("04. low", 0) or 0),
                    "open": float(gq.get("02. open", 0) or 0),
                    "prevClose": float(gq.get("08. previous close", 0) or 0),
                })
        except Exception as e:
            logger.error(f"[STOCKS] {sym} error: {e}")
        time.sleep(1.5)

    if results:
        save_data("stocks", results, ttl=3600)
        logger.info(f"[STOCKS] Updated {len(results)} quotes")
