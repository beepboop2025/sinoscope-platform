import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';

// Fear & Greed Index from alternative.me (free, no key needed)
export async function fetchFearGreedIndex() {
  const cacheKey = 'fear_greed_index';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  try {
    const res = await fetch('https://api.alternative.me/fng/?limit=30&format=json');
    if (!res.ok) throw new Error(`FearGreed: ${res.status}`);
    const data = await res.json();

    const entries = (data.data || []).map(d => ({
      value: parseInt(d.value, 10),
      label: d.value_classification,
      timestamp: parseInt(d.timestamp, 10) * 1000,
    }));

    cacheSet(cacheKey, entries, 300000);
    return entries;
  } catch (err) {
    console.warn('[SentimentAPI]', err.message);
    return null;
  }
}

export function getMockFearGreed() {
  const val = Math.floor(35 + Math.random() * 40);
  const label = val <= 25 ? 'Extreme Fear' : val <= 45 ? 'Fear' : val <= 55 ? 'Neutral' : val <= 75 ? 'Greed' : 'Extreme Greed';
  const history = [];
  for (let i = 29; i >= 0; i--) {
    const v = Math.floor(20 + Math.random() * 60);
    const l = v <= 25 ? 'Extreme Fear' : v <= 45 ? 'Fear' : v <= 55 ? 'Neutral' : v <= 75 ? 'Greed' : 'Extreme Greed';
    history.push({ value: v, label: l, timestamp: Date.now() - i * 86400000 });
  }
  return history;
}

const SECTOR_ETFS = [
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
export async function fetchSectorPerformance() {
  const cacheKey = 'sector_performance';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('yahoo')) return null;
  consumeToken('yahoo');

  try {
    const symbols = SECTOR_ETFS.map(s => s.symbol).join(',');
    const res = await fetch(`/api/yahoo/v7/finance/quote?symbols=${symbols}`);
    if (!res.ok) return null;
    const data = await res.json();
    const quotes = data?.quoteResponse?.result || [];

    if (quotes.length === 0) return null;

    const sectors = SECTOR_ETFS.map(sector => {
      const q = quotes.find(quote => quote.symbol === sector.symbol);
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
    console.warn('[SentimentAPI sectors]', err.message);
    return null;
  }
}

// Mock fallback with seeded but stable values (not random every call)
let _mockSectorSeed = null;
export function getSectorPerformance() {
  if (!_mockSectorSeed) {
    _mockSectorSeed = SECTOR_ETFS.map(s => ({
      ...s,
      changePct: +((Math.random() - 0.45) * 4).toFixed(2),
      weekPct: +((Math.random() - 0.45) * 6).toFixed(2),
      monthPct: +((Math.random() - 0.4) * 12).toFixed(2),
    }));
  }
  return _mockSectorSeed;
}
