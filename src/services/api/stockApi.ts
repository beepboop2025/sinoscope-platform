import { getCollectorData } from '../CollectorClient';
import {
  getStockProfile as proxyStockProfile,
  getFinnhubQuote as proxyFinnhubQuote,
  getMarketMovers as proxyMarketMovers,
  getHistoricalPrices as proxyHistoricalPrices,
  getCandles as proxyCandles,
  getEarningsCalendar as proxyEarningsCalendar,
} from '../BackendProxyClient';
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

export async function fetchStockQuotes(symbols: string[] = ['AAPL', 'MSFT', 'GOOGL']): Promise<StockQuote[] | null> {
  const collected = await getCollectorData('stocks');
  if (collected) {
    const symSet = new Set(symbols.map((s: string) => s.toUpperCase()));
    const filtered = (collected as StockQuote[]).filter((q: StockQuote) => symSet.has(q.symbol?.toUpperCase()));
    if (filtered.length > 0) return filtered;
    return collected as StockQuote[];
  }
  return null;
}

export async function fetchStockProfile(symbol: string): Promise<StockProfile | null> {
  return proxyStockProfile(symbol) as Promise<StockProfile | null>;
}

export async function fetchFinnhubQuote(symbol: string): Promise<FinnhubQuoteResult | null> {
  return proxyFinnhubQuote(symbol) as Promise<FinnhubQuoteResult | null>;
}

export async function fetchMarketMovers(type: string = 'gainers'): Promise<MarketMover[] | null> {
  return proxyMarketMovers(type) as Promise<MarketMover[] | null>;
}

export async function fetchHistoricalPrices(symbol: string): Promise<HistoricalPrice[] | null> {
  return proxyHistoricalPrices(symbol) as Promise<HistoricalPrice[] | null>;
}

export async function fetchFinnhubCandles(symbol: string, resolution: string = 'D', from: number, to: number): Promise<HistoricalPrice[] | null> {
  return proxyCandles(symbol, resolution, from, to) as Promise<HistoricalPrice[] | null>;
}

export async function fetchEarningsCalendar(from: string, to: string): Promise<EarningsEvent[] | null> {
  return proxyEarningsCalendar(from, to) as Promise<EarningsEvent[] | null>;
}
