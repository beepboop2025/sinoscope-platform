import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

const FMP_KEY = () => import.meta.env.VITE_FMP_API_KEY || '';
const AV_KEY = () => import.meta.env.VITE_ALPHA_VANTAGE_API_KEY || '';
const FINNHUB_KEY = () => import.meta.env.VITE_FINNHUB_API_KEY || '';

export async function fetchStockQuotes(symbols = ['AAPL', 'MSFT', 'GOOGL']) {
  // Collector-first: pre-fetched stock quotes
  const collected = await getCollectorData('stocks');
  if (collected) {
    const symSet = new Set(symbols.map(s => s.toUpperCase()));
    const filtered = collected.filter(q => symSet.has(q.symbol?.toUpperCase()));
    if (filtered.length > 0) return filtered;
  }

  const symStr = symbols.join(',');
  const cacheKey = `stock_quotes_${symStr}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  // Try Alpha Vantage (25 req/day, 5 req/min free)
  const avKey = AV_KEY();
  if (avKey) {
    const results = [];
    for (let i = 0; i < symbols.length; i++) {
      if (!canRequest('alphavantage')) break;
      if (i > 0) await new Promise(r => setTimeout(r, 1500)); // 1.5s delay to avoid per-minute throttle
      const quote = await fetchAlphaVantageQuote(symbols[i], avKey);
      if (quote) results.push(quote);
    }
    if (results.length > 0) {
      cacheSet(cacheKey, results, 600000); // Cache 10 min to save API calls
      return results;
    }
  }

  // Fallback to FMP if available
  const key = FMP_KEY();
  if (!key) return null;
  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.quote(symStr, key));
    if (!res.ok) throw new Error(`FMP: ${res.status}`);
    const data = await res.json();
    cacheSet(cacheKey, data, 60000);
    return data;
  } catch (err) {
    console.warn('[StockAPI FMP]', err.message);
    return null;
  }
}

async function fetchAlphaVantageQuote(symbol, key) {
  const cacheKey = `av_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  consumeToken('alphavantage');

  try {
    const res = await fetchWithTimeout(API.ALPHA_VANTAGE.quote(symbol, key));
    if (!res.ok) throw new Error(`AV: ${res.status}`);
    const data = await res.json();
    if (data['Note'] || data['Information']) {
      console.warn('[StockAPI AV] Rate limited:', symbol);
      return null;
    }
    const gq = data['Global Quote'];
    if (!gq || !gq['05. price']) return null;

    const result = {
      symbol: gq['01. symbol'],
      price: parseFloat(gq['05. price']) || 0,
      change: parseFloat(gq['09. change']) || 0,
      changePct: parseFloat(gq['10. change percent']) || 0,
      changesPercentage: parseFloat(gq['10. change percent']) || 0,
      volume: parseInt(gq['06. volume'], 10) || 0,
      high: parseFloat(gq['03. high']) || 0,
      low: parseFloat(gq['04. low']) || 0,
      open: parseFloat(gq['02. open']) || 0,
      prevClose: parseFloat(gq['08. previous close']) || 0,
    };
    cacheSet(cacheKey, result, 600000);
    return result;
  } catch (err) {
    console.warn('[StockAPI AV]', symbol, err.message);
    return null;
  }
}

export async function fetchStockProfile(symbol) {
  const key = FMP_KEY();
  if (!key) return null;
  const cacheKey = `stock_profile_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.profile(symbol, key));
    if (!res.ok) throw new Error(`FMP profile: ${res.status}`);
    const data = await res.json();
    cacheSet(cacheKey, data, 300000);
    return data?.[0] || null;
  } catch (err) {
    console.warn('[StockAPI profile]', err.message);
    return null;
  }
}

export async function fetchFinnhubQuote(symbol) {
  const key = FINNHUB_KEY();
  if (!key) return null;
  const cacheKey = `finnhub_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetchWithTimeout(API.FINNHUB.quote(symbol, key));
    if (!res.ok) throw new Error(`Finnhub: ${res.status}`);
    const data = await res.json();
    const result = { symbol, price: data.c, change: data.d, changePct: data.dp, high: data.h, low: data.l, open: data.o, prevClose: data.pc };
    cacheSet(cacheKey, result, 15000);
    return result;
  } catch (err) {
    console.warn('[StockAPI finnhub]', err.message);
    return null;
  }
}

export async function fetchMarketMovers(type = 'gainers') {
  const key = FMP_KEY();
  if (!key) return null;
  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.marketMost(type, key));
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn('[StockAPI movers]', err.message);
    return null;
  }
}

export async function fetchHistoricalPrices(symbol) {
  const key = FMP_KEY();
  if (!key) return null;
  const cacheKey = `historical_prices_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.historical(symbol, key));
    if (!res.ok) throw new Error(`FMP historical: ${res.status}`);
    const data = await res.json();
    const historical = (data.historical || []).map(d => ({
      date: d.date,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.volume,
    }));
    cacheSet(cacheKey, historical, 300000);
    return historical;
  } catch (err) {
    console.warn('[StockAPI historical]', err.message);
    return null;
  }
}

export async function fetchFinnhubCandles(symbol, resolution = 'D', from, to) {
  const key = FINNHUB_KEY();
  if (!key) return null;
  const cacheKey = `finnhub_candles_${symbol}_${resolution}_${from}_${to}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetchWithTimeout(API.FINNHUB.candles(symbol, resolution, from, to, key));
    if (!res.ok) throw new Error(`Finnhub candles: ${res.status}`);
    const data = await res.json();
    if (data.s !== 'ok' || !data.t) return null;

    const candles = data.t.map((timestamp, i) => ({
      date: new Date(timestamp * 1000).toISOString().split('T')[0],
      open: data.o[i],
      high: data.h[i],
      low: data.l[i],
      close: data.c[i],
      volume: data.v[i],
    }));
    cacheSet(cacheKey, candles, 60000);
    return candles;
  } catch (err) {
    console.warn('[StockAPI finnhub candles]', err.message);
    return null;
  }
}

export async function fetchEarningsCalendar(from, to) {
  const key = FINNHUB_KEY();
  if (!key) return null;
  const cacheKey = `earnings_${from}_${to}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetchWithTimeout(API.FINNHUB.earnings(from, to, key));
    if (!res.ok) throw new Error(`Finnhub earnings: ${res.status}`);
    const data = await res.json();
    const results = (data.earningsCalendar || []).map(e => ({
      symbol: e.symbol,
      date: e.date,
      hour: e.hour,
      epsEstimate: e.epsEstimate,
      epsActual: e.epsActual,
      revenueEstimate: e.revenueEstimate,
      revenueActual: e.revenueActual,
      quarter: e.quarter,
      year: e.year,
    }));
    cacheSet(cacheKey, results, 3600000); // 1 hour cache
    return results;
  } catch (err) {
    console.warn('[StockAPI earnings]', err.message);
    return null;
  }
}
