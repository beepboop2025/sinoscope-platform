"""On-demand API proxy endpoints.

These endpoints serve data that the Celery collector does NOT pre-fetch:
individual stock profiles, coin details, historical prices, candles, etc.
Each endpoint checks Redis cache first, fetches from the external API on
cache miss using server-side API keys, caches the result, and returns JSON.

Cache-Control policy:
- Real-time data (quotes, candles): no-cache (revalidate every request)
- Semi-static data (profiles, coin details): max-age=300 (5 min)
- Static reference data (earnings calendar, world bank): max-age=3600 (1 hour)
"""

import logging
import re
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.services.cache import get_cached_json, set_cached_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proxy")
settings = get_settings()

FETCH_TIMEOUT = 15.0


def _cached_response(data: dict | list, max_age: int = 0) -> JSONResponse:
    """Return a JSON response with appropriate Cache-Control headers.

    Args:
        data: The response payload.
        max_age: Cache duration in seconds.
            0 = no-cache (real-time data)
            300 = 5 minutes (semi-static: profiles, details)
            3600 = 1 hour (static reference: earnings, world bank)
    """
    if max_age <= 0:
        cache_control = "no-cache, no-store, must-revalidate"
    else:
        cache_control = f"public, max-age={max_age}, stale-while-revalidate={max_age // 2}"
    return JSONResponse(
        content=data,
        headers={"Cache-Control": cache_control},
    )


async def _fetch_json(url: str, headers: dict | None = None) -> dict | list | None:
    """Fetch JSON from an external API with timeout."""
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
            resp = await client.get(url, headers=headers or {})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning(f"[Proxy] Fetch failed: {url[:80]}... -> {e}")
        return None


def _validate_symbol(symbol: str) -> str:
    """Validate and sanitize a stock/crypto symbol."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", symbol)
    if not cleaned or len(cleaned) > 20:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    return cleaned.upper()


# ── Stock Profile (FMP) ────────────────────────────────────────────────────

@router.get("/stock-profile/{symbol}")
async def get_stock_profile(symbol: str):
    symbol = _validate_symbol(symbol)
    cache_key = f"proxy:stock_profile:{symbol}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=300)

    key = settings.FMP_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="FMP API key not configured")

    data = await _fetch_json(f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={key}")
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    result = data[0] if isinstance(data, list) and data else data
    await set_cached_json(cache_key, result, ttl=300)  # 5 min
    return _cached_response(result, max_age=300)  # semi-static


# ── Coin Detail (CoinGecko) ───────────────────────────────────────────────

@router.get("/coin-detail/{coin_id}")
async def get_coin_detail(coin_id: str):
    coin_id = re.sub(r"[^a-z0-9-]", "", coin_id.lower())
    if not coin_id:
        raise HTTPException(status_code=400, detail="Invalid coin ID")

    cache_key = f"proxy:coin_detail:{coin_id}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=300)

    data = await _fetch_json(f"https://api.coingecko.com/api/v3/coins/{coin_id}")
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    # Extract relevant fields to reduce payload size
    md = data.get("market_data", {})
    links = data.get("links", {})
    desc = data.get("description", {})
    result = {
        "name": data.get("name"),
        "symbol": data.get("symbol"),
        "market_cap": (md.get("market_cap") or {}).get("usd", 0),
        "total_supply": md.get("total_supply", 0),
        "description": (desc.get("en") or "")[:500],
        "links": {
            "homepage": (links.get("homepage") or [""])[0],
            "blockchain_site": (links.get("blockchain_site") or [""])[0],
            "subreddit": links.get("subreddit_url", ""),
            "github": ((links.get("repos_url") or {}).get("github") or [""])[0],
        },
    }
    await set_cached_json(cache_key, result, ttl=120)  # 2 min
    return _cached_response(result, max_age=300)  # semi-static


# ── Historical Prices (FMP) ───────────────────────────────────────────────

@router.get("/historical/{symbol}")
async def get_historical_prices(symbol: str):
    symbol = _validate_symbol(symbol)
    cache_key = f"proxy:historical:{symbol}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=300)

    key = settings.FMP_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="FMP API key not configured")

    data = await _fetch_json(f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?apikey={key}")
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    historical = data.get("historical", [])
    result = [{"date": d["date"], "open": d["open"], "high": d["high"], "low": d["low"], "close": d["close"], "volume": d["volume"]} for d in historical[:365]]
    await set_cached_json(cache_key, result, ttl=300)  # 5 min
    return _cached_response(result, max_age=300)


# ── Candles (Finnhub) ─────────────────────────────────────────────────────

@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    resolution: str = Query(default="D", pattern="^(1|5|15|30|60|D|W|M)$"),
    from_ts: int = Query(alias="from", default=0),
    to_ts: int = Query(alias="to", default=0),
):
    symbol = _validate_symbol(symbol)
    cache_key = f"proxy:candles:{symbol}:{resolution}:{from_ts}:{to_ts}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=0)  # real-time

    key = settings.FINNHUB_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="Finnhub API key not configured")

    data = await _fetch_json(
        f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution={resolution}&from={from_ts}&to={to_ts}&token={key}"
    )
    if not data or data.get("s") != "ok" or not data.get("t"):
        raise HTTPException(status_code=502, detail="No candle data")

    result = [
        {"date": datetime.fromtimestamp(data["t"][i], tz=timezone.utc).strftime("%Y-%m-%d"), "open": data["o"][i], "high": data["h"][i], "low": data["l"][i], "close": data["c"][i], "volume": data["v"][i]}
        for i in range(len(data["t"]))
    ]
    await set_cached_json(cache_key, result, ttl=60)  # 1 min
    return _cached_response(result, max_age=0)  # real-time


# ── Market Movers (FMP) ───────────────────────────────────────────────────

@router.get("/market-movers/{mover_type}")
async def get_market_movers(mover_type: str):
    if mover_type not in ("gainers", "losers", "actives"):
        raise HTTPException(status_code=400, detail="Invalid mover type")

    cache_key = f"proxy:movers:{mover_type}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=300)

    key = settings.FMP_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="FMP API key not configured")

    data = await _fetch_json(f"https://financialmodelingprep.com/api/v3/stock_market/{mover_type}?apikey={key}")
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    await set_cached_json(cache_key, data, ttl=120)  # 2 min
    return _cached_response(data, max_age=300)


# ── Earnings Calendar (Finnhub) ───────────────────────────────────────────

@router.get("/earnings")
async def get_earnings(
    from_date: str = Query(alias="from", default="", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str = Query(alias="to", default="", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    if not from_date or not to_date:
        raise HTTPException(status_code=400, detail="from and to date params required (YYYY-MM-DD)")

    cache_key = f"proxy:earnings:{from_date}:{to_date}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=3600)

    key = settings.FINNHUB_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="Finnhub API key not configured")

    data = await _fetch_json(f"https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={key}")
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    result = data.get("earningsCalendar", [])
    await set_cached_json(cache_key, result, ttl=3600)  # 1 hour
    return _cached_response(result, max_age=3600)  # static reference


# ── Treasury Yield (FRED) ─────────────────────────────────────────────────

@router.get("/yield/{maturity}")
async def get_yield(maturity: str):
    series_map = {
        "1m": "DGS1MO", "3m": "DGS3MO", "6m": "DGS6MO", "1y": "DGS1",
        "2y": "DGS2", "3y": "DGS3", "5y": "DGS5", "7y": "DGS7",
        "10y": "DGS10", "20y": "DGS20", "30y": "DGS30",
    }
    series_id = series_map.get(maturity.lower())
    if not series_id:
        raise HTTPException(status_code=400, detail=f"Invalid maturity. Valid: {', '.join(series_map.keys())}")

    cache_key = f"proxy:yield:{maturity}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=300)

    key = settings.FRED_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="FRED API key not configured")

    data = await _fetch_json(
        f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={key}&file_type=json&sort_order=desc&limit=30"
    )
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    result = data.get("observations", [])
    await set_cached_json(cache_key, result, ttl=600)  # 10 min
    return _cached_response(result, max_age=300)


# ── Commodity (FRED) ──────────────────────────────────────────────────────

@router.get("/commodity/{name}")
async def get_commodity(name: str):
    commodity_map = {
        "oil": "DCOILWTICO", "gas": "DHHNGSP", "gold": "GOLDAMGBD228NLBM",
        "copper": "PCOPPUSDM", "gasoline": "GASREGW",
    }
    series_id = commodity_map.get(name.lower())
    if not series_id:
        raise HTTPException(status_code=400, detail=f"Invalid commodity. Valid: {', '.join(commodity_map.keys())}")

    cache_key = f"proxy:commodity:{name}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=300)

    key = settings.FRED_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="FRED API key not configured")

    data = await _fetch_json(
        f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={key}&file_type=json&sort_order=desc&limit=30"
    )
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    result = data.get("observations", [])
    await set_cached_json(cache_key, result, ttl=600)  # 10 min
    return _cached_response(result, max_age=300)


# ── Economic Indicator (FRED) ─────────────────────────────────────────────

@router.get("/econ/{indicator}")
async def get_econ_indicator(indicator: str):
    indicator_map = {
        "gdp": "GDP", "cpi": "CPIAUCSL", "unemployment": "UNRATE",
        "fed_rate": "FEDFUNDS", "retail_sales": "RSAFS", "housing": "HOUST",
        "m2": "M2SL", "trade_balance": "BOPGSTB", "pce": "PCE",
        "industrial": "INDPRO", "consumer_sentiment": "UMCSENT",
    }
    series_id = indicator_map.get(indicator.lower())
    if not series_id:
        raise HTTPException(status_code=400, detail=f"Invalid indicator. Valid: {', '.join(indicator_map.keys())}")

    cache_key = f"proxy:econ:{indicator}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=300)

    key = settings.FRED_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="FRED API key not configured")

    data = await _fetch_json(
        f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={key}&file_type=json&sort_order=desc&limit=30"
    )
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    result = data.get("observations", [])
    await set_cached_json(cache_key, result, ttl=600)  # 10 min
    return _cached_response(result, max_age=300)


# ── World Bank Indicator ──────────────────────────────────────────────────

@router.get("/worldbank/{country}/{indicator}")
async def get_worldbank(country: str, indicator: str):
    country = re.sub(r"[^A-Za-z]", "", country)[:3].upper()
    indicator = re.sub(r"[^A-Za-z0-9._]", "", indicator)
    if not country or not indicator:
        raise HTTPException(status_code=400, detail="Invalid country or indicator")

    cache_key = f"proxy:worldbank:{country}:{indicator}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=3600)

    data = await _fetch_json(
        f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=50"
    )
    if not data or not isinstance(data, list) or len(data) < 2:
        raise HTTPException(status_code=502, detail="Upstream API error")

    result = data[1] if len(data) > 1 else data
    await set_cached_json(cache_key, result, ttl=21600)  # 6 hours
    return _cached_response(result, max_age=3600)  # static reference


# ── Finnhub Quote (single stock) ──────────────────────────────────────────

@router.get("/finnhub-quote/{symbol}")
async def get_finnhub_quote(symbol: str):
    symbol = _validate_symbol(symbol)
    cache_key = f"proxy:finnhub_quote:{symbol}"
    cached = await get_cached_json(cache_key)
    if cached:
        return _cached_response(cached, max_age=0)  # real-time

    key = settings.FINNHUB_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="Finnhub API key not configured")

    data = await _fetch_json(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={key}")
    if not data:
        raise HTTPException(status_code=502, detail="Upstream API error")

    result = {
        "symbol": symbol,
        "price": data.get("c", 0),
        "change": data.get("d", 0),
        "changePct": data.get("dp", 0),
        "high": data.get("h", 0),
        "low": data.get("l", 0),
        "open": data.get("o", 0),
        "prevClose": data.get("pc", 0),
    }
    await set_cached_json(cache_key, result, ttl=15)  # 15 sec
    return _cached_response(result, max_age=0)  # real-time
