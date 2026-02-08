import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';

const COMMODITY_INDICATORS = {
  GASOLINE: 'GASREGW',
  OIL_WTI: 'DCOILWTICO',
  OIL_BRENT: 'DCOILBRENTEU',
  NATGAS: 'DHHNGSP',
  COPPER: 'PCOPPUSDM',
};

const FRED_KEY = () => import.meta.env.VITE_FRED_API_KEY || '';

export async function fetchCommodityPrice(commodity) {
  const key = FRED_KEY();
  const seriesId = COMMODITY_INDICATORS[commodity];
  if (!key || !seriesId) return null;

  const cacheKey = `commodity_${commodity}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('fred')) return null;
  consumeToken('fred');

  try {
    const url = `${API.FRED.series(seriesId, key)}&sort_order=desc&limit=30`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`FRED commodity: ${res.status}`);
    const data = await res.json();
    const obs = (data.observations || []).filter(o => o.value !== '.').map(o => ({
      date: o.date,
      value: parseFloat(o.value),
    }));
    cacheSet(cacheKey, obs, 300000);
    return obs;
  } catch (err) {
    console.warn('[CommodityAPI]', err.message);
    return null;
  }
}

export async function fetchAllCommodities() {
  const results = {};
  for (const [name, _] of Object.entries(COMMODITY_INDICATORS)) {
    const data = await fetchCommodityPrice(name);
    if (data && data.length > 0) {
      results[name] = { price: data[0].value, date: data[0].date, history: data.slice(0, 10) };
    }
  }
  return results;
}
