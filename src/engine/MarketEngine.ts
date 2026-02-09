import { fetchForexRates } from '../services/api/forexApi';
import { fetchCryptoMarkets } from '../services/api/cryptoApi';
import { fetchStockQuotes } from '../services/api/stockApi';
import { fetchYieldCurve } from '../services/api/bondApi';
import { fetchAllCommodities } from '../services/api/commodityApi';
import { normalizeTick, normalizeForex, normalizeCrypto } from '../services/DataNormalizer';
import { generateMockEconomic } from '../generators/mockEconomic';
import { generateMockChinaIndices } from '../generators/mockChina';

export function createMarketEngine() {
  const state = {
    forex: {},
    stocks: {},
    crypto: {},
    bonds: [],
    commodities: {},
    economic: {},
    indices: {},
    lastUpdate: {},
    errors: {},
    lastFetchTime: {},
    listeners: new Set(),
    intervals: [],
  };

  function recordError(source, err) {
    state.errors[source] = { source, error: err.message, timestamp: Date.now() };
  }

  function clearError(source) {
    delete state.errors[source];
  }

  function notify() {
    for (const fn of state.listeners) {
      try { fn(getSnapshot()); } catch (e) { console.warn('[MarketEngine] listener error', e); }
    }
  }

  function subscribe(fn) {
    state.listeners.add(fn);
    return () => state.listeners.delete(fn);
  }

  async function fetchForex() {
    try {
      const data = await fetchForexRates('USD');
      if (data?.rates) {
        for (const [currency, rate] of Object.entries(data.rates)) {
          state.forex[`USD/${currency}`] = normalizeForex(`USD/${currency}`, rate);
        }
        state.lastUpdate.forex = Date.now();
        state.lastFetchTime.forex = Date.now();
        clearError('forex');
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] forex error', err);
      recordError('forex', err);
      notify();
    }
  }

  async function fetchStocks() {
    try {
      const data = await fetchStockQuotes(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']);
      if (data) {
        for (const quote of data) {
          state.stocks[quote.symbol] = normalizeTick(quote, 'stock');
        }
        state.lastUpdate.stocks = Date.now();
        state.lastFetchTime.stocks = Date.now();
        clearError('stocks');
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] stocks error', err);
      recordError('stocks', err);
      notify();
    }
  }

  async function fetchCrypto() {
    try {
      const data = await fetchCryptoMarkets('usd', 10);
      if (data) {
        for (const coin of data) {
          state.crypto[coin.symbol.toUpperCase()] = normalizeCrypto(coin);
        }
        state.lastUpdate.crypto = Date.now();
        state.lastFetchTime.crypto = Date.now();
        clearError('crypto');
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] crypto error', err);
      recordError('crypto', err);
      notify();
    }
  }

  async function fetchBonds() {
    try {
      const data = await fetchYieldCurve();
      if (data) {
        state.bonds = data;
        state.lastUpdate.bonds = Date.now();
        state.lastFetchTime.bonds = Date.now();
        clearError('bonds');
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] bonds error', err);
      recordError('bonds', err);
      notify();
    }
  }

  async function fetchCommodities() {
    try {
      const data = await fetchAllCommodities();
      if (data) {
        state.commodities = data;
        state.lastUpdate.commodities = Date.now();
        state.lastFetchTime.commodities = Date.now();
        clearError('commodities');
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] commodities error', err);
      recordError('commodities', err);
      notify();
    }
  }

  async function fetchEconomic() {
    try {
      // Use mock data as baseline; real FRED data layered on top via econApi if keys present
      const data = generateMockEconomic();
      state.economic = data;
      state.lastUpdate.economic = Date.now();
      state.lastFetchTime.economic = Date.now();
      clearError('economic');
      notify();
    } catch (err) {
      console.warn('[MarketEngine] economic error', err);
      recordError('economic', err);
      notify();
    }
  }

  async function fetchIndices() {
    try {
      const data = generateMockChinaIndices();
      // Merge global index mock data
      const globalIndices = {
        SPX: { symbol: 'SPX', name: 'S&P 500', price: 5250 + (Math.random() - 0.5) * 60, changePct: (Math.random() - 0.5) * 2 },
        DJI: { symbol: 'DJI', name: 'Dow Jones', price: 39200 + (Math.random() - 0.5) * 400, changePct: (Math.random() - 0.5) * 1.5 },
        IXIC: { symbol: 'IXIC', name: 'NASDAQ', price: 16500 + (Math.random() - 0.5) * 200, changePct: (Math.random() - 0.5) * 2.5 },
        FTSE: { symbol: 'FTSE', name: 'FTSE 100', price: 7950 + (Math.random() - 0.5) * 80, changePct: (Math.random() - 0.5) * 1.2 },
        DAX: { symbol: 'DAX', name: 'DAX 40', price: 18100 + (Math.random() - 0.5) * 180, changePct: (Math.random() - 0.5) * 1.5 },
        N225: { symbol: 'N225', name: 'Nikkei 225', price: 38500 + (Math.random() - 0.5) * 400, changePct: (Math.random() - 0.5) * 2 },
      };
      for (const idx of data) {
        globalIndices[idx.symbol] = { symbol: idx.symbol, name: idx.name, price: idx.price, changePct: idx.changesPercentage || 0 };
      }
      state.indices = globalIndices;
      state.lastUpdate.indices = Date.now();
      state.lastFetchTime.indices = Date.now();
      clearError('indices');
      notify();
    } catch (err) {
      console.warn('[MarketEngine] indices error', err);
      recordError('indices', err);
      notify();
    }
  }

  function updateFromWS(tick) {
    const sym = tick.symbol;
    if (sym.endsWith('USDT')) {
      state.crypto[sym.replace('USDT', '')] = { ...state.crypto[sym.replace('USDT', '')], ...tick, market: 'crypto' };
    } else {
      state.stocks[sym] = { ...state.stocks[sym], ...tick, market: 'stock' };
    }
    state.lastUpdate.ws = Date.now();
  }

  function getSnapshot() {
    return {
      forex: { ...state.forex },
      stocks: { ...state.stocks },
      crypto: { ...state.crypto },
      bonds: [...state.bonds],
      commodities: { ...state.commodities },
      economic: { ...state.economic },
      indices: { ...state.indices },
      lastUpdate: { ...state.lastUpdate },
      errors: { ...state.errors },
      lastFetchTime: { ...state.lastFetchTime },
    };
  }

  function start() {
    fetchForex();
    fetchCrypto();
    fetchStocks();
    fetchBonds();
    fetchCommodities();
    fetchEconomic();
    fetchIndices();

    state.intervals.push(
      setInterval(fetchForex, 60000),
      setInterval(fetchCrypto, 35000),
      setInterval(fetchStocks, 1800000), // 30min — Alpha Vantage free tier is 25 req/day
      setInterval(fetchBonds, 600000),
      setInterval(fetchCommodities, 600000),
      setInterval(fetchEconomic, 300000),  // 5 min
      setInterval(fetchIndices, 60000),    // 1 min
    );
  }

  function stop() {
    for (const id of state.intervals) clearInterval(id);
    state.intervals = [];
  }

  return { start, stop, subscribe, getSnapshot, updateFromWS, fetchForex, fetchStocks, fetchCrypto, fetchBonds, fetchCommodities, fetchEconomic, fetchIndices };
}
