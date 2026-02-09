import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

interface EconObservation {
  date: string;
  value: number;
}

const FRED_KEY = (): string => import.meta.env.VITE_FRED_API_KEY || '';

const ECON_SERIES: Record<string, string> = {
  GDP: 'GDP',
  CPI: 'CPIAUCSL',
  UNEMPLOYMENT: 'UNRATE',
  FED_RATE: 'FEDFUNDS',
  RETAIL_SALES: 'RSXFS',
  HOUSING_STARTS: 'HOUST',
  M2: 'M2SL',
  TRADE_BALANCE: 'BOPGSTB',
};

export async function fetchEconIndicator(indicator: string): Promise<EconObservation[] | null> {
  // Collector-first: pre-fetched economic data keyed by indicator
  const collected = await getCollectorData('economic');
  if (collected && (collected as Record<string, unknown>)[indicator]) return (collected as Record<string, EconObservation[]>)[indicator];

  const key: string = FRED_KEY();
  const seriesId: string | undefined = ECON_SERIES[indicator];
  if (!key || !seriesId) return null;

  const cacheKey = `econ_${indicator}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as EconObservation[];

  if (!canRequest('fred')) return null;
  consumeToken('fred');

  try {
    const url = `${API.FRED.series(seriesId, key)}&sort_order=desc&limit=24`;
    const res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error(`FRED econ: ${res.status}`);
    const data: unknown = await res.json();
    const parsed = data as { observations?: { date: string; value: string }[] };
    const obs: EconObservation[] = (parsed.observations || []).filter((o: { value: string }) => o.value !== '.').map((o: { date: string; value: string }) => ({
      date: o.date,
      value: parseFloat(o.value),
    }));
    cacheSet(cacheKey, obs, 600000);
    return obs;
  } catch (err) {
    console.warn('[EconAPI]', (err as Error).message);
    return null;
  }
}

export async function fetchWorldBankIndicator(country: string = 'USA', indicator: string = 'NY.GDP.MKTP.KD.ZG'): Promise<EconObservation[] | null> {
  const cacheKey = `wb_${country}_${indicator}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as EconObservation[];

  try {
    const url = API.WORLD_BANK.indicator(country, indicator);
    const res = await fetchWithTimeout(url);
    if (!res.ok) return null;
    const data: unknown = await res.json();
    const parsed = data as unknown[];
    const entries: EconObservation[] = ((parsed[1] || []) as { date: string; value: number | null }[]).filter((e: { value: number | null }) => e.value != null).map((e: { date: string; value: number | null }) => ({
      date: e.date,
      value: e.value as number,
    }));
    cacheSet(cacheKey, entries, 600000);
    return entries;
  } catch (err) {
    console.warn('[EconAPI WB]', (err as Error).message);
    return null;
  }
}
