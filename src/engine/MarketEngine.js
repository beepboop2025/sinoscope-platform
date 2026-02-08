import { fetchForexRates } from '../services/api/forexApi';
import { fetchCryptoMarkets } from '../services/api/cryptoApi';
import { fetchStockQuotes } from '../services/api/stockApi';
import { fetchYieldCurve } from '../services/api/bondApi';
import { fetchAllCommodities } from '../services/api/commodityApi';
import { normalizeTick, normalizeForex, normalizeCrypto } from '../services/DataNormalizer';

export function createMarketEngine() {
  const state = {
    forex: {},
    stocks: {},
    crypto: {},
    bonds: [],
    commodities: {},
    economic: {},
    lastUpdate: {},
    listeners: new Set(),
    intervals: [],
  };

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
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] forex error', err);
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
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] stocks error', err);
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
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] crypto error', err);
    }
  }

  async function fetchBonds() {
    try {
      const data = await fetchYieldCurve();
      if (data) {
        state.bonds = data;
        state.lastUpdate.bonds = Date.now();
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] bonds error', err);
    }
  }

  async function fetchCommodities() {
    try {
      const data = await fetchAllCommodities();
      if (data) {
        state.commodities = data;
        state.lastUpdate.commodities = Date.now();
        notify();
      }
    } catch (err) {
      console.warn('[MarketEngine] commodities error', err);
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
      lastUpdate: { ...state.lastUpdate },
    };
  }

  function start() {
    fetchForex();
    fetchCrypto();
    fetchStocks();
    fetchBonds();
    fetchCommodities();

    state.intervals.push(
      setInterval(fetchForex, 60000),
      setInterval(fetchCrypto, 35000),
      setInterval(fetchStocks, 1800000), // 30min — Alpha Vantage free tier is 25 req/day
      setInterval(fetchBonds, 600000),
      setInterval(fetchCommodities, 600000),
    );
  }

  function stop() {
    for (const id of state.intervals) clearInterval(id);
    state.intervals = [];
  }

  return { start, stop, subscribe, getSnapshot, updateFromWS, fetchForex, fetchStocks, fetchCrypto, fetchBonds, fetchCommodities };
}
