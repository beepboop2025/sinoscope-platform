import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';

const FRED_KEY = () => import.meta.env.VITE_FRED_API_KEY || '';

const ECON_SERIES = {
  GDP: 'GDP',
  CPI: 'CPIAUCSL',
  UNEMPLOYMENT: 'UNRATE',
  FED_RATE: 'FEDFUNDS',
  RETAIL_SALES: 'RSXFS',
  HOUSING_STARTS: 'HOUST',
  M2: 'M2SL',
  TRADE_BALANCE: 'BOPGSTB',
};

export async function fetchEconIndicator(indicator) {
  // Collector-first: pre-fetched economic data keyed by indicator
  const collected = await getCollectorData('economic');
  if (collected && collected[indicator]) return collected[indicator];

  const key = FRED_KEY();
  const seriesId = ECON_SERIES[indicator];
  if (!key || !seriesId) return null;

  const cacheKey = `econ_${indicator}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('fred')) return null;
  consumeToken('fred');

  try {
    const url = `${API.FRED.series(seriesId, key)}&sort_order=desc&limit=24`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`FRED econ: ${res.status}`);
    const data = await res.json();
    const obs = (data.observations || []).filter(o => o.value !== '.').map(o => ({
      date: o.date,
      value: parseFloat(o.value),
    }));
    cacheSet(cacheKey, obs, 600000);
    return obs;
  } catch (err) {
    console.warn('[EconAPI]', err.message);
    return null;
  }
}

export async function fetchWorldBankIndicator(country = 'USA', indicator = 'NY.GDP.MKTP.KD.ZG') {
  const cacheKey = `wb_${country}_${indicator}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  try {
    const url = API.WORLD_BANK.indicator(country, indicator);
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    const entries = (data[1] || []).filter(e => e.value != null).map(e => ({
      date: e.date,
      value: e.value,
    }));
    cacheSet(cacheKey, entries, 600000);
    return entries;
  } catch (err) {
    console.warn('[EconAPI WB]', err.message);
    return null;
  }
}
