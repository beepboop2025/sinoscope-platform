import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

interface FREDObservation {
  date: string;
  value: number;
}

interface YieldCurvePoint {
  maturity: string;
  yield: number;
  date: string;
}

const FRED_KEY = (): string => import.meta.env.VITE_FRED_API_KEY || '';

const TREASURY_SERIES: Record<string, string> = {
  '1M': 'DGS1MO', '3M': 'DGS3MO', '6M': 'DGS6MO',
  '1Y': 'DGS1', '2Y': 'DGS2', '3Y': 'DGS3', '5Y': 'DGS5',
  '7Y': 'DGS7', '10Y': 'DGS10', '20Y': 'DGS20', '30Y': 'DGS30',
};

export async function fetchTreasuryYield(maturity: string = '10Y'): Promise<FREDObservation[] | null> {
  const key: string = FRED_KEY();
  if (!key) return null;
  const seriesId: string | undefined = TREASURY_SERIES[maturity];
  if (!seriesId) return null;

  const cacheKey = `treasury_${maturity}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as FREDObservation[];

  if (!canRequest('fred')) return null;
  consumeToken('fred');

  try {
    const url = `${API.FRED.series(seriesId, key)}&sort_order=desc&limit=30`;
    const res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error(`FRED: ${res.status}`);
    const data: unknown = await res.json();
    const parsed = data as { observations?: { date: string; value: string }[] };
    const obs: FREDObservation[] = (parsed.observations || []).filter((o: { value: string }) => o.value !== '.').map((o: { date: string; value: string }) => ({
      date: o.date,
      value: parseFloat(o.value),
    }));
    cacheSet(cacheKey, obs, 300000);
    return obs;
  } catch (err) {
    console.warn('[BondAPI]', (err as Error).message);
    return null;
  }
}

export async function fetchYieldCurve(): Promise<YieldCurvePoint[] | null> {
  // Collector-first: pre-fetched yield curve
  const collected = await getCollectorData('yield_curve');
  if (collected) return collected as YieldCurvePoint[];

  const key: string = FRED_KEY();
  if (!key) return null;

  const cacheKey = 'yield_curve';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as YieldCurvePoint[];

  const maturities: string[] = Object.keys(TREASURY_SERIES);
  const results: YieldCurvePoint[] = [];

  for (const mat of maturities) {
    const data = await fetchTreasuryYield(mat);
    if (data && data.length > 0) {
      results.push({ maturity: mat, yield: data[0].value, date: data[0].date });
    }
  }

  cacheSet(cacheKey, results, 300000);
  return results;
}
