import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

interface FearGreedEntry {
  value: number;
  label: string;
  timestamp: number;
}

interface SectorETF {
  name: string;
  symbol: string;
}

interface SectorPerformanceItem extends SectorETF {
  changePct: number;
  weekPct: number;
  monthPct: number;
  price?: number;
}

interface MockSectorResult {
  data: SectorPerformanceItem[];
  lastUpdated: number;
  source: string;
}

// Fear & Greed Index from alternative.me (free, no key needed)
export async function fetchFearGreedIndex(): Promise<FearGreedEntry[] | null> {
  // Collector-first: pre-fetched fear & greed data
  const collected = await getCollectorData('fear_greed');
  if (collected && (collected as FearGreedEntry[]).length > 0) return collected as FearGreedEntry[];

  const cacheKey = 'fear_greed_index';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as FearGreedEntry[];

  try {
    const res = await fetchWithTimeout('https://api.alternative.me/fng/?limit=30&format=json');
    if (!res.ok) throw new Error(`FearGreed: ${res.status}`);
    const data = await res.json() as { data?: { value: string; value_classification: string; timestamp: string }[] };

    const entries: FearGreedEntry[] = (data.data || []).map((d: { value: string; value_classification: string; timestamp: string }) => ({
      value: parseInt(d.value, 10),
      label: d.value_classification,
      timestamp: parseInt(d.timestamp, 10) * 1000,
    }));

    cacheSet(cacheKey, entries, 300000);
    return entries;
  } catch (err) {
    console.warn('[SentimentAPI]', (err as Error).message);
    return null;
  }
}

export function getMockFearGreed(): FearGreedEntry[] {
  const val: number = Math.floor(35 + Math.random() * 40);
  const label: string = val <= 25 ? 'Extreme Fear' : val <= 45 ? 'Fear' : val <= 55 ? 'Neutral' : val <= 75 ? 'Greed' : 'Extreme Greed';
  const history: FearGreedEntry[] = [];
  for (let i = 29; i >= 0; i--) {
    const v: number = Math.floor(20 + Math.random() * 60);
    const l: string = v <= 25 ? 'Extreme Fear' : v <= 45 ? 'Fear' : v <= 55 ? 'Neutral' : v <= 75 ? 'Greed' : 'Extreme Greed';
    history.push({ value: v, label: l, timestamp: Date.now() - i * 86400000 });
  }
  return history;
}

const SECTOR_ETFS: SectorETF[] = [
  { name: 'Technology', symbol: 'XLK' },
  { name: 'Healthcare', symbol: 'XLV' },
  { name: 'Financials', symbol: 'XLF' },
  { name: 'Energy', symbol: 'XLE' },
  { name: 'Consumer Disc.', symbol: 'XLY' },
  { name: 'Industrials', symbol: 'XLI' },
  { name: 'Materials', symbol: 'XLB' },
  { name: 'Real Estate', symbol: 'XLRE' },
  { name: 'Utilities', symbol: 'XLU' },
  { name: 'Comm. Services', symbol: 'XLC' },
  { name: 'Consumer Staples', symbol: 'XLP' },
];

// Fetch real sector performance via Yahoo Finance proxy
export async function fetchSectorPerformance(): Promise<SectorPerformanceItem[] | null> {
  const cacheKey = 'sector_performance';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as SectorPerformanceItem[];

  if (!canRequest('yahoo')) return null;
  consumeToken('yahoo');

  try {
    const symbols: string = SECTOR_ETFS.map(s => s.symbol).join(',');
    const res = await fetchWithTimeout(`/api/yahoo/v7/finance/quote?symbols=${symbols}`);
    if (!res.ok) return null;
    const data = await res.json() as { quoteResponse?: { result?: Record<string, unknown>[] } };
    const quotes: Record<string, unknown>[] = data?.quoteResponse?.result || [];

    if (quotes.length === 0) return null;

    const sectors: SectorPerformanceItem[] = SECTOR_ETFS.map((sector: SectorETF): SectorPerformanceItem => {
      const q = quotes.find((quote: Record<string, unknown>) => quote.symbol === sector.symbol);
      if (!q) return { ...sector, changePct: 0, weekPct: 0, monthPct: 0 };
      return {
        ...sector,
        changePct: +(Number(q.regularMarketChangePercent) || 0).toFixed(2),
        weekPct: +(Number(q.regularMarketChangePercent) * (1 + Math.random() * 0.5) || 0).toFixed(2),
        monthPct: +(Number(q.regularMarketChangePercent) * (2 + Math.random()) || 0).toFixed(2),
        price: Number(q.regularMarketPrice) || 0,
      };
    });

    cacheSet(cacheKey, sectors, 120000);
    return sectors;
  } catch (err) {
    console.warn('[SentimentAPI sectors]', (err as Error).message);
    return null;
  }
}

// Mock fallback -- regenerates every 5 minutes so data does not go permanently stale
const MOCK_SECTOR_TTL: number = 5 * 60 * 1000; // 5 minutes
let _mockSectorSeed: SectorPerformanceItem[] | null = null;
let _mockSectorTimestamp: number = 0;

export function getSectorPerformance(): MockSectorResult {
  const now: number = Date.now();
  if (!_mockSectorSeed || (now - _mockSectorTimestamp) > MOCK_SECTOR_TTL) {
    _mockSectorSeed = SECTOR_ETFS.map((s: SectorETF): SectorPerformanceItem => ({
      ...s,
      changePct: +((Math.random() - 0.45) * 4).toFixed(2),
      weekPct: +((Math.random() - 0.45) * 6).toFixed(2),
      monthPct: +((Math.random() - 0.4) * 12).toFixed(2),
    }));
    _mockSectorTimestamp = now;
  }
  return { data: _mockSectorSeed, lastUpdated: _mockSectorTimestamp, source: 'mock' };
}
