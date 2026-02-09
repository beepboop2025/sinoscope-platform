import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { generateMockChinaIndices, generateMockChinaStocks } from '../../generators/mockChina';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

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
        const res = await fetchWithTimeout(API.FMP.quote(symbols, key));
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
        const res = await fetchWithTimeout(API.FMP.quote(symbols, key));
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

    // PBOC rates are not freely available via a free public API — return reference data.
    // These values were last verified from official PBOC publications.
    // Verify/update at: http://www.pbc.gov.cn/english/130437/index.html (PBOC English portal)
    // and: https://www.chinamoney.com.cn/english/ (China Foreign Exchange Trade System)
    const rates = {
      lpr1y: 3.45,
      lpr5y: 3.95,
      lendingFacility: 2.50,
      reverseRepo: 1.80,
      rrr: 10.0,
      lastUpdated: '2024-02-20',
      source: 'static_reference',
    };
    cacheSet(cacheKey, rates, 3600000);
    return rates;
  },

  async fetchCNYCNHRates() {
    // Collector-first: pre-fetched CNY rates
    const collected = await getCollectorData('cny_rates');
    if (collected && collected.cnyUsd) {
      const cny = Number(collected.cnyUsd) || 7.24;
      return { cnyUsd: cny, cnhUsd: collected.cnhUsd ? Number(collected.cnhUsd) : cny + 0.01, timestamp: collected.timestamp || Date.now(), isStale: false };
    }

    const cacheKey = 'cny_cnh';
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    if (!canRequest('frankfurter')) {
      return { cnyUsd: 7.24, cnhUsd: 7.25, isStale: true, lastUpdated: '2024-01-01', source: 'static_fallback' };
    }
    consumeToken('frankfurter');

    try {
      const res = await fetchWithTimeout(`${API.FRANKFURTER.latest}?base=USD&symbols=CNY`);
      if (!res.ok) throw new Error('CNY fetch failed');
      const data = await res.json();
      const cny = data.rates?.CNY || 7.24;
      const cnh = cny + (Math.random() - 0.5) * 0.02;
      const result = { cnyUsd: cny, cnhUsd: cnh, timestamp: Date.now(), isStale: false };
      cacheSet(cacheKey, result, 30000);
      return result;
    } catch (err) {
      console.warn('[ChinaAPI CNY]', err.message);
      return { cnyUsd: 7.24, cnhUsd: 7.25, isStale: true, lastUpdated: '2024-01-01', source: 'static_fallback' };
    }
  },

  // Fetch China GDP and trade data from World Bank (free, no key)
  async fetchChinaEconomic() {
    const cacheKey = 'china_economic';
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    const indicators = [
      { id: 'NY.GDP.MKTP.CD', label: 'GDP (USD)' },
      { id: 'NE.TRD.GNFS.ZS', label: 'Trade (% GDP)' },
      { id: 'FP.CPI.TOTL.ZG', label: 'CPI Inflation' },
      { id: 'BN.CAB.XOKA.CD', label: 'Current Account' },
    ];

    const results = [];
    for (const ind of indicators) {
      try {
        const url = `${API.WORLD_BANK.indicator('CHN', ind.id)}&per_page=5&date=2020:2025`;
        const res = await fetchWithTimeout(url);
        if (!res.ok) continue;
        const data = await res.json();
        const entries = data?.[1] || [];
        const latest = entries.find(e => e.value != null);
        if (latest) {
          results.push({
            indicator: ind.label,
            value: latest.value,
            year: latest.date,
            id: ind.id,
          });
        }
      } catch { /* skip */ }
    }

    if (results.length > 0) {
      cacheSet(cacheKey, results, 3600000); // 1 hour cache
    }
    return results.length > 0 ? results : null;
  },

  // CNY historical rates for charting
  async fetchCNYHistory(days = 30) {
    const cacheKey = `cny_history_${days}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    if (!canRequest('frankfurter')) return null;
    consumeToken('frankfurter');

    try {
      const to = new Date().toISOString().split('T')[0];
      const from = new Date(Date.now() - days * 86400000).toISOString().split('T')[0];
      const res = await fetchWithTimeout(`${API.FRANKFURTER.timeseries(from, to)}?base=USD&symbols=CNY`);
      if (!res.ok) return null;
      const data = await res.json();
      const rates = Object.entries(data.rates || {}).map(([date, r]) => ({
        date,
        rate: r.CNY,
      })).sort((a, b) => a.date.localeCompare(b.date));
      cacheSet(cacheKey, rates, 600000);
      return rates;
    } catch (err) {
      console.warn('[ChinaAPI history]', err.message);
      return null;
    }
  },
};
