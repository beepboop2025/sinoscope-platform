import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

interface CommodityObservation {
  date: string;
  value: number;
}

interface CommodityResult {
  price: number;
  date: string;
  history: CommodityObservation[];
}

const COMMODITY_INDICATORS: Record<string, string> = {
  GASOLINE: 'GASREGW',
  OIL_WTI: 'DCOILWTICO',
  OIL_BRENT: 'DCOILBRENTEU',
  NATGAS: 'DHHNGSP',
  COPPER: 'PCOPPUSDM',
};

const FRED_KEY = (): string => import.meta.env.VITE_FRED_API_KEY || '';

export async function fetchCommodityPrice(commodity: string): Promise<CommodityObservation[] | null> {
  // Collector-first: backend may have pre-fetched commodity data keyed by commodity name
  const collected = await getCollectorData('commodities');
  if (collected && typeof collected === 'object') {
    const commodities = collected as Record<string, unknown>;
    const entry = commodities[commodity];
    if (entry && Array.isArray(entry)) return entry as CommodityObservation[];
  }

  const key: string = FRED_KEY();
  const seriesId: string | undefined = COMMODITY_INDICATORS[commodity];
  if (!key || !seriesId) return null;

  const cacheKey = `commodity_${commodity}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as CommodityObservation[];

  if (!canRequest('fred')) return null;
  consumeToken('fred');

  try {
    const url = `${API.FRED.series(seriesId, key)}&sort_order=desc&limit=30`;
    const res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error(`FRED commodity: ${res.status}`);
    const data: unknown = await res.json();
    const parsed = data as { observations?: { date: string; value: string }[] };
    const obs: CommodityObservation[] = (parsed.observations || []).filter((o: { value: string }) => o.value !== '.').map((o: { date: string; value: string }) => ({
      date: o.date,
      value: parseFloat(o.value),
    }));
    cacheSet(cacheKey, obs, 300000);
    return obs;
  } catch (err) {
    console.warn('[CommodityAPI]', (err as Error).message);
    return null;
  }
}

export async function fetchAllCommodities(): Promise<Record<string, CommodityResult>> {
  // Collector-first: pre-fetched commodities
  const collected = await getCollectorData('commodities');
  if (collected) return collected as Record<string, CommodityResult>;

  const results: Record<string, CommodityResult> = {};
  for (const [name, _] of Object.entries(COMMODITY_INDICATORS)) {
    const data = await fetchCommodityPrice(name);
    if (data && data.length > 0) {
      results[name] = { price: data[0].value, date: data[0].date, history: data.slice(0, 10) };
    }
  }
  return results;
}
