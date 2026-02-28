import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';
import type { StockProfile, MarketMover, EarningsEvent } from '../../types';

interface StockQuote {
  symbol: string;
  price: number;
  change: number;
  changePct: number;
  changesPercentage?: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  prevClose: number;
}

interface HistoricalPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface FinnhubQuoteResult {
  symbol: string;
  price: number;
  change: number;
  changePct: number;
  high: number;
  low: number;
  open: number;
  prevClose: number;
}

const FMP_KEY = (): string => import.meta.env.VITE_FMP_API_KEY || '';
const AV_KEY = (): string => import.meta.env.VITE_ALPHA_VANTAGE_API_KEY || '';
const FINNHUB_KEY = (): string => import.meta.env.VITE_FINNHUB_API_KEY || '';

export async function fetchStockQuotes(symbols: string[] = ['AAPL', 'MSFT', 'GOOGL']): Promise<StockQuote[] | null> {
  // Collector-first: pre-fetched stock quotes
  const collected = await getCollectorData('stocks');
  if (collected) {
    const symSet = new Set(symbols.map((s: string) => s.toUpperCase()));
    const filtered = (collected as StockQuote[]).filter((q: StockQuote) => symSet.has(q.symbol?.toUpperCase()));
    if (filtered.length > 0) return filtered;
  }

  const symStr: string = symbols.join(',');
  const cacheKey = `stock_quotes_${symStr}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as StockQuote[];

  // Try Alpha Vantage (25 req/day, 5 req/min free)
  const avKey: string = AV_KEY();
  if (avKey) {
    const results: StockQuote[] = [];
    for (let i = 0; i < symbols.length; i++) {
      if (!canRequest('alphavantage')) break;
      if (i > 0) await new Promise<void>(r => setTimeout(r, 1500)); // 1.5s delay to avoid per-minute throttle
      const quote = await fetchAlphaVantageQuote(symbols[i], avKey);
      if (quote) results.push(quote);
    }
    if (results.length > 0) {
      cacheSet(cacheKey, results, 600000); // Cache 10 min to save API calls
      return results;
    }
  }

  // Fallback to FMP if available
  const key: string = FMP_KEY();
  if (!key) return null;
  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.quote(symStr, key));
    if (!res.ok) throw new Error(`FMP: ${res.status}`);
    const data: unknown = await res.json();
    cacheSet(cacheKey, data, 60000);
    return data as StockQuote[];
  } catch (err) {
    console.warn('[StockAPI FMP]', (err as Error).message);
    return null;
  }
}

async function fetchAlphaVantageQuote(symbol: string, key: string): Promise<StockQuote | null> {
  const cacheKey = `av_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as StockQuote;

  consumeToken('alphavantage');

  try {
    const res = await fetchWithTimeout(API.ALPHA_VANTAGE.quote(symbol, key));
    if (!res.ok) throw new Error(`AV: ${res.status}`);
    const data = await res.json() as Record<string, unknown>;
    if (data['Note'] || data['Information']) {
      console.warn('[StockAPI AV] Rate limited:', symbol);
      return null;
    }
    const gq = data['Global Quote'] as Record<string, string> | undefined;
    if (!gq || !gq['05. price']) return null;

    const result: StockQuote = {
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
    console.warn('[StockAPI AV]', symbol, (err as Error).message);
    return null;
  }
}

export async function fetchStockProfile(symbol: string): Promise<StockProfile | null> {
  const key: string = FMP_KEY();
  if (!key) return null;
  const cacheKey = `stock_profile_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as StockProfile;

  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.profile(symbol, key));
    if (!res.ok) throw new Error(`FMP profile: ${res.status}`);
    const data: unknown = await res.json();
    cacheSet(cacheKey, data, 300000);
    return (data as StockProfile[])?.[0] || null;
  } catch (err) {
    console.warn('[StockAPI profile]', (err as Error).message);
    return null;
  }
}

export async function fetchFinnhubQuote(symbol: string): Promise<FinnhubQuoteResult | null> {
  const key: string = FINNHUB_KEY();
  if (!key) return null;
  const cacheKey = `finnhub_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as FinnhubQuoteResult;

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetchWithTimeout(API.FINNHUB.quote(symbol, key));
    if (!res.ok) throw new Error(`Finnhub: ${res.status}`);
    const data = await res.json() as { c: number; d: number; dp: number; h: number; l: number; o: number; pc: number };
    const result: FinnhubQuoteResult = { symbol, price: data.c, change: data.d, changePct: data.dp, high: data.h, low: data.l, open: data.o, prevClose: data.pc };
    cacheSet(cacheKey, result, 15000);
    return result;
  } catch (err) {
    console.warn('[StockAPI finnhub]', (err as Error).message);
    return null;
  }
}

export async function fetchMarketMovers(type: string = 'gainers'): Promise<MarketMover[] | null> {
  const key: string = FMP_KEY();
  if (!key) return null;
  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.marketMost(type, key));
    if (!res.ok) return null;
    return await res.json() as MarketMover[];
  } catch (err) {
    console.warn('[StockAPI movers]', (err as Error).message);
    return null;
  }
}

export async function fetchHistoricalPrices(symbol: string): Promise<HistoricalPrice[] | null> {
  const key: string = FMP_KEY();
  if (!key) return null;
  const cacheKey = `historical_prices_${symbol}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as HistoricalPrice[];

  if (!canRequest('fmp')) return null;
  consumeToken('fmp');

  try {
    const res = await fetchWithTimeout(API.FMP.historical(symbol, key));
    if (!res.ok) throw new Error(`FMP historical: ${res.status}`);
    const data = await res.json() as { historical?: HistoricalPrice[] };
    const historical: HistoricalPrice[] = (data.historical || []).map((d: HistoricalPrice) => ({
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
    console.warn('[StockAPI historical]', (err as Error).message);
    return null;
  }
}

export async function fetchFinnhubCandles(symbol: string, resolution: string = 'D', from: number, to: number): Promise<HistoricalPrice[] | null> {
  const key: string = FINNHUB_KEY();
  if (!key) return null;
  const cacheKey = `finnhub_candles_${symbol}_${resolution}_${from}_${to}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as HistoricalPrice[];

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetchWithTimeout(API.FINNHUB.candles(symbol, resolution, from, to, key));
    if (!res.ok) throw new Error(`Finnhub candles: ${res.status}`);
    const data = await res.json() as { s: string; t?: number[]; o: number[]; h: number[]; l: number[]; c: number[]; v: number[] };
    if (data.s !== 'ok' || !data.t) return null;

    const candles: HistoricalPrice[] = data.t.map((timestamp: number, i: number) => ({
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
    console.warn('[StockAPI finnhub candles]', (err as Error).message);
    return null;
  }
}

export async function fetchEarningsCalendar(from: string, to: string): Promise<EarningsEvent[] | null> {
  const key: string = FINNHUB_KEY();
  if (!key) return null;
  const cacheKey = `earnings_${from}_${to}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as EarningsEvent[];

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetchWithTimeout(API.FINNHUB.earnings(from, to, key));
    if (!res.ok) throw new Error(`Finnhub earnings: ${res.status}`);
    const data = await res.json() as { earningsCalendar?: Record<string, unknown>[] };
    const results: EarningsEvent[] = (data.earningsCalendar || []).map((e: Record<string, unknown>) => ({
      symbol: e.symbol as string,
      date: e.date as string,
      hour: e.hour as string,
      epsEstimate: e.epsEstimate as number | null,
      epsActual: e.epsActual as number | null,
      revenueEstimate: e.revenueEstimate as number | null,
      revenueActual: e.revenueActual as number | null,
      quarter: e.quarter as number,
      year: e.year as number,
    }));
    cacheSet(cacheKey, results, 3600000); // 1 hour cache
    return results;
  } catch (err) {
    console.warn('[StockAPI earnings]', (err as Error).message);
    return null;
  }
}
