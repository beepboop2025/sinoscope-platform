import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';

const FMP_KEY = () => import.meta.env.VITE_FMP_API_KEY || '';
const AV_KEY = () => import.meta.env.VITE_ALPHA_VANTAGE_API_KEY || '';
const FINNHUB_KEY = () => import.meta.env.VITE_FINNHUB_API_KEY || '';

export async function fetchStockQuotes(symbols = ['AAPL', 'MSFT', 'GOOGL']) {
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
    const res = await fetch(API.FMP.quote(symStr, key));
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
    const res = await fetch(API.ALPHA_VANTAGE.quote(symbol, key));
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
      price: parseFloat(gq['05. price']),
      change: parseFloat(gq['09. change']),
      changePct: parseFloat(gq['10. change percent']),
      changesPercentage: parseFloat(gq['10. change percent']),
      volume: parseInt(gq['06. volume'], 10),
      high: parseFloat(gq['03. high']),
      low: parseFloat(gq['04. low']),
      open: parseFloat(gq['02. open']),
      prevClose: parseFloat(gq['08. previous close']),
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
    const res = await fetch(API.FMP.profile(symbol, key));
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
    const res = await fetch(API.FINNHUB.quote(symbol, key));
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
    const res = await fetch(API.FMP.marketMost(type, key));
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
