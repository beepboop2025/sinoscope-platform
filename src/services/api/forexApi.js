import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';

export async function fetchForexRates(base = 'USD') {
  const cacheKey = `forex_${base}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('frankfurter')) return null;
  consumeToken('frankfurter');

  try {
    const res = await fetch(`${API.FRANKFURTER.latest}?base=${base}`);
    if (!res.ok) throw new Error(`Frankfurter: ${res.status}`);
    const data = await res.json();
    const result = { base: data.base, date: data.date, rates: data.rates, timestamp: Date.now() };
    cacheSet(cacheKey, result, 60000);
    return result;
  } catch (err) {
    console.warn('[ForexAPI]', err.message);
    return null;
  }
}

export async function fetchForexTimeseries(base = 'USD', symbols = 'CNY,EUR,GBP,JPY', days = 30) {
  const to = new Date().toISOString().split('T')[0];
  const from = new Date(Date.now() - days * 86400000).toISOString().split('T')[0];
  const cacheKey = `forex_ts_${base}_${symbols}_${from}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('frankfurter')) return null;
  consumeToken('frankfurter');

  try {
    const res = await fetch(`${API.FRANKFURTER.timeseries(from, to)}?base=${base}&symbols=${symbols}`);
    if (!res.ok) throw new Error(`Frankfurter timeseries: ${res.status}`);
    const data = await res.json();
    cacheSet(cacheKey, data, 300000);
    return data;
  } catch (err) {
    console.warn('[ForexAPI timeseries]', err.message);
    return null;
  }
}
