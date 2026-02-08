import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { generateMockChinaIndices, generateMockChinaStocks } from '../../generators/mockChina';

const FMP_KEY = () => import.meta.env.VITE_FMP_API_KEY || '';

export const ChinaAPI = {
  async fetchChinaIndices(apiKey) {
    const key = apiKey || FMP_KEY();

    const cacheKey = 'china_indices';
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    // Try FMP API if key available
    if (key) {
      if (!canRequest('fmp')) return generateMockChinaIndices();
      consumeToken('fmp');
      try {
        const symbols = '^SSEC,^HSI,000300.SS';
        const res = await fetch(API.FMP.quote(symbols, key));
        if (res.ok) {
          const data = await res.json();
          if (data && data.length > 0) {
            cacheSet(cacheKey, data, 60000);
            return data;
          }
        }
      } catch (err) {
        console.warn('[ChinaAPI indices]', err.message);
      }
    }

    // Fall back to mock data
    const mock = generateMockChinaIndices();
    cacheSet(cacheKey, mock, 30000);
    return mock;
  },

  async fetchChinaStocks(apiKey) {
    const key = apiKey || FMP_KEY();

    const cacheKey = 'china_stocks';
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    // Try FMP API if key available
    if (key) {
      if (!canRequest('fmp')) return generateMockChinaStocks();
      consumeToken('fmp');
      try {
        const symbols = '601398.SS,002594.SZ,300750.SZ,600519.SS';
        const res = await fetch(API.FMP.quote(symbols, key));
        if (res.ok) {
          const data = await res.json();
          if (data && data.length > 0) {
            cacheSet(cacheKey, data, 60000);
            return data;
          }
        }
      } catch (err) {
        console.warn('[ChinaAPI stocks]', err.message);
      }
    }

    // Fall back to mock data
    const mock = generateMockChinaStocks();
    cacheSet(cacheKey, mock, 30000);
    return mock;
  },

  async fetchPBOCRates() {
    const cacheKey = 'pboc_rates';
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    // PBOC rates are not freely available via API — return reference data
    const rates = {
      lpr1y: 3.45,
      lpr5y: 3.95,
      lendingFacility: 2.50,
      reverseRepo: 1.80,
      rrr: 10.0,
      lastUpdate: Date.now(),
    };
    cacheSet(cacheKey, rates, 3600000);
    return rates;
  },

  async fetchCNYCNHRates() {
    const cacheKey = 'cny_cnh';
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    if (!canRequest('frankfurter')) return { cnyUsd: 7.24, cnhUsd: 7.25 };
    consumeToken('frankfurter');

    try {
      const res = await fetch(`${API.FRANKFURTER.latest}?base=USD&symbols=CNY`);
      if (!res.ok) throw new Error('CNY fetch failed');
      const data = await res.json();
      const cny = data.rates?.CNY || 7.24;
      const cnh = cny + (Math.random() - 0.5) * 0.02;
      const result = { cnyUsd: cny, cnhUsd: cnh, timestamp: Date.now() };
      cacheSet(cacheKey, result, 30000);
      return result;
    } catch (err) {
      console.warn('[ChinaAPI CNY]', err.message);
      return { cnyUsd: 7.24, cnhUsd: 7.25 };
    }
  },
};
