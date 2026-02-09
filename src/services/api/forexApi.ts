import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';
import type { ForexRates, ForexTimeseries } from '../../types';

export async function fetchForexRates(base: string = 'USD'): Promise<ForexRates | null> {
  // Collector-first: pre-fetched forex data
  if (base === 'USD') {
    const collected = await getCollectorData('forex');
    if (collected) return collected as ForexRates;
  }

  const cacheKey = `forex_${base}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as ForexRates;

  if (!canRequest('frankfurter')) return null;
  consumeToken('frankfurter');

  try {
    const res = await fetchWithTimeout(`${API.FRANKFURTER.latest}?base=${base}`);
    if (!res.ok) throw new Error(`Frankfurter: ${res.status}`);
    const data: unknown = await res.json();
    const parsed = data as { base: string; date: string; rates: Record<string, number> };
    const result: ForexRates = { base: parsed.base, date: parsed.date, rates: parsed.rates, timestamp: Date.now() };
    cacheSet(cacheKey, result, 60000);
    return result;
  } catch (err) {
    console.warn('[ForexAPI]', (err as Error).message);
    return null;
  }
}

export async function fetchForexTimeseries(base: string = 'USD', symbols: string = 'CNY,EUR,GBP,JPY', days: number = 30): Promise<ForexTimeseries | null> {
  const to: string = new Date().toISOString().split('T')[0];
  const from: string = new Date(Date.now() - days * 86400000).toISOString().split('T')[0];
  const cacheKey = `forex_ts_${base}_${symbols}_${from}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as ForexTimeseries;

  if (!canRequest('frankfurter')) return null;
  consumeToken('frankfurter');

  try {
    const res = await fetchWithTimeout(`${API.FRANKFURTER.timeseries(from, to)}?base=${base}&symbols=${symbols}`);
    if (!res.ok) throw new Error(`Frankfurter timeseries: ${res.status}`);
    const data: unknown = await res.json();
    cacheSet(cacheKey, data, 300000);
    return data as ForexTimeseries;
  } catch (err) {
    console.warn('[ForexAPI timeseries]', (err as Error).message);
    return null;
  }
}
