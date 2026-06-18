#!/usr/bin/env node
/**
 * DragonScope 24/7 Data Collector
 * Continuously gathers market data from all APIs and saves to JSON files.
 * Run with: node collector.js
 * Or via pm2: pm2 start ecosystem.config.cjs
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import cron from 'node-cron';
import WebSocket from 'ws';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, 'data');
mkdirSync(DATA_DIR, { recursive: true });
mkdirSync(join(__dirname, 'logs'), { recursive: true });

// ─── Load env from parent .env ───
const envPath = join(__dirname, '..', '.env');
if (existsSync(envPath)) {
  const envContent = readFileSync(envPath, 'utf8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq > 0) {
      const key = trimmed.slice(0, eq).replace('VITE_', '');
      const val = trimmed.slice(eq + 1);
      process.env[key] = val;
    }
  }
}

const FRED_KEY = process.env.FRED_API_KEY || '';
const AV_KEY = process.env.ALPHA_VANTAGE_API_KEY || '';
const FINNHUB_KEY = process.env.FINNHUB_API_KEY || '';
const FMP_KEY = process.env.FMP_API_KEY || '';
const GNEWS_KEY = process.env.GNEWS_API_KEY || '';
const NEWSDATA_KEY = process.env.NEWSDATA_API_KEY || '';
const NEWSAPI_KEY = process.env.NEWSAPI_API_KEY || '';
const WORLD_NEWS_KEY = process.env.WORLD_NEWS_API_KEY || '';

// ─── Rate Limiter ───
const rateLimits = {};
function createLimiter(name, max, windowMs) {
  rateLimits[name] = { max, windowMs, tokens: max, lastRefill: Date.now() };
}
function canRequest(name) {
  const l = rateLimits[name];
  if (!l) return true;
  const now = Date.now();
  const elapsed = now - l.lastRefill;
  if (elapsed >= l.windowMs) {
    l.tokens = l.max;
    l.lastRefill = now;
  }
  return l.tokens > 0;
}
function consumeToken(name) {
  if (rateLimits[name]) rateLimits[name].tokens--;
}

// Configure rate limits
createLimiter('frankfurter', 25, 60000);
createLimiter('coingecko', 20, 60000);
createLimiter('fred', 80, 60000);
createLimiter('alphavantage', 20, 86400000);
createLimiter('fmp', 200, 86400000);
createLimiter('finnhub', 50, 60000);
createLimiter('github', 25, 3600000);
createLimiter('huggingface', 25, 60000);
createLimiter('defillama', 15, 60000);
createLimiter('reddit', 8, 60000);
createLimiter('sec', 8, 60000);
createLimiter('arxiv', 8, 60000);
createLimiter('gnews', 80, 86400000);
createLimiter('newsdata', 12, 86400000);
createLimiter('newsapiorg', 80, 86400000);
createLimiter('worldnews', 40, 86400000);

// ─── Helpers ───
function saveData(category, data) {
  const filePath = join(DATA_DIR, `${category}.json`);
  const payload = {
    _updated: new Date().toISOString(),
    _source: category,
    data,
  };
  try {
    writeFileSync(filePath, JSON.stringify(payload, null, 2));
  } catch (err) {
    log(`[SAVE ERROR] ${category}: ${err.message}`);
  }
}

function loadData(category) {
  const filePath = join(DATA_DIR, `${category}.json`);
  try {
    if (existsSync(filePath)) {
      return JSON.parse(readFileSync(filePath, 'utf8'));
    }
  } catch { /* ignore */ }
  return null;
}

function log(msg) {
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  console.log(`[${ts}] ${msg}`);
}

async function safeFetch(url, options = {}) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res;
  } catch (err) {
    throw err;
  }
}

// ─── Stats ───
const stats = { started: new Date().toISOString(), fetches: 0, errors: 0, lastRun: {} };

function recordRun(name, success) {
  stats.fetches++;
  if (!success) stats.errors++;
  stats.lastRun[name] = { time: new Date().toISOString(), success };
  // Save stats periodically
  if (stats.fetches % 10 === 0) {
    saveData('_stats', stats);
  }
}

// ═══════════════════════════════════════════════════════
// DATA FETCHERS
// ═══════════════════════════════════════════════════════

// ─── FOREX ───
async function fetchForex() {
  if (!canRequest('frankfurter')) return;
  consumeToken('frankfurter');
  try {
    const res = await safeFetch('https://api.frankfurter.dev/v1/latest?base=USD');
    const data = await res.json();
    saveData('forex', { base: data.base, date: data.date, rates: data.rates, timestamp: Date.now() });
    log('[FOREX] Rates updated');
    recordRun('forex', true);
  } catch (err) {
    log(`[FOREX] Error: ${err.message}`);
    recordRun('forex', false);
  }
}

async function fetchForexTimeseries() {
  if (!canRequest('frankfurter')) return;
  consumeToken('frankfurter');
  try {
    const to = new Date().toISOString().split('T')[0];
    const from = new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0];
    const res = await safeFetch(`https://api.frankfurter.dev/v1/${from}..${to}?base=USD&symbols=CNY,EUR,GBP,JPY,INR`);
    const data = await res.json();
    saveData('forex_timeseries', data);
    log('[FOREX] Timeseries updated');
    recordRun('forex_timeseries', true);
  } catch (err) {
    log(`[FOREX] Timeseries error: ${err.message}`);
    recordRun('forex_timeseries', false);
  }
}

// ─── CRYPTO (CoinGecko) ───
async function fetchCryptoMarkets() {
  if (!canRequest('coingecko')) return;
  consumeToken('coingecko');
  try {
    const res = await safeFetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1&sparkline=true&price_change_percentage=1h,24h,7d');
    const data = await res.json();
    saveData('crypto_markets', data);
    log(`[CRYPTO] Markets updated: ${data.length} coins`);
    recordRun('crypto_markets', true);
  } catch (err) {
    log(`[CRYPTO] Markets error: ${err.message}`);
    recordRun('crypto_markets', false);
  }
}

async function fetchCryptoGlobal() {
  if (!canRequest('coingecko')) return;
  consumeToken('coingecko');
  try {
    const res = await safeFetch('https://api.coingecko.com/api/v3/global');
    const data = await res.json();
    const d = data.data;
    saveData('crypto_global', {
      totalMarketCap: d.total_market_cap?.usd || 0,
      totalVolume: d.total_volume?.usd || 0,
      btcDominance: d.market_cap_percentage?.btc || 0,
      ethDominance: d.market_cap_percentage?.eth || 0,
      activeCryptos: d.active_cryptocurrencies || 0,
      markets: d.markets || 0,
      marketCapChange24h: d.market_cap_change_percentage_24h_usd || 0,
    });
    log('[CRYPTO] Global data updated');
    recordRun('crypto_global', true);
  } catch (err) {
    log(`[CRYPTO] Global error: ${err.message}`);
    recordRun('crypto_global', false);
  }
}

async function fetchTrendingCoins() {
  if (!canRequest('coingecko')) return;
  consumeToken('coingecko');
  try {
    const res = await safeFetch('https://api.coingecko.com/api/v3/search/trending');
    const data = await res.json();
    const coins = (data.coins || []).map(c => ({
      id: c.item.id, name: c.item.name, symbol: c.item.symbol,
      rank: c.item.market_cap_rank, priceBtc: c.item.price_btc, score: c.item.score,
    }));
    saveData('crypto_trending', coins);
    log(`[CRYPTO] Trending updated: ${coins.length} coins`);
    recordRun('crypto_trending', true);
  } catch (err) {
    log(`[CRYPTO] Trending error: ${err.message}`);
    recordRun('crypto_trending', false);
  }
}

// ─── Keyless real-data fallbacks (Yahoo Finance / treasury.gov) ───
// Used automatically when the corresponding API key is absent, so the app
// shows real market data out of the box instead of demo placeholders.
const YF_UA = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' };

async function yahooChart(symbol, range = '5d', interval = '1d') {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}`;
  const res = await safeFetch(url, { headers: YF_UA });
  const data = await res.json();
  return data?.chart?.result?.[0] || null;
}

async function fetchStocksYahoo() {
  const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'V', 'WMT'];
  const results = [];
  for (const sym of symbols) {
    try {
      const chart = await yahooChart(sym, '1d', '1d');
      const m = chart?.meta;
      if (!m?.regularMarketPrice) continue;
      const prev = m.chartPreviousClose ?? m.previousClose ?? m.regularMarketPrice;
      const q = chart.indicators?.quote?.[0] || {};
      results.push({
        symbol: m.symbol,
        price: m.regularMarketPrice,
        change: +(m.regularMarketPrice - prev).toFixed(4),
        changePct: +(((m.regularMarketPrice - prev) / prev) * 100).toFixed(4),
        volume: m.regularMarketVolume ?? q.volume?.[0] ?? 0,
        high: m.regularMarketDayHigh ?? q.high?.[0] ?? m.regularMarketPrice,
        low: m.regularMarketDayLow ?? q.low?.[0] ?? m.regularMarketPrice,
        open: q.open?.[0] ?? prev,
        prevClose: prev,
      });
    } catch (err) {
      log(`[STOCKS] Yahoo ${sym} error: ${err.message}`);
    }
    await sleep(300);
  }
  if (results.length > 0) {
    saveData('stocks', results);
    log(`[STOCKS] Updated ${results.length} quotes (Yahoo keyless)`);
    recordRun('stocks', true);
  } else {
    recordRun('stocks', false);
  }
}

async function fetchCommoditiesYahoo() {
  const futures = {
    GOLD: 'GC=F', SILVER: 'SI=F', OIL_WTI: 'CL=F', OIL_BRENT: 'BZ=F',
    NATGAS: 'NG=F', COPPER: 'HG=F',
  };
  const results = {};
  for (const [name, sym] of Object.entries(futures)) {
    try {
      const chart = await yahooChart(sym, '1mo', '1d');
      const m = chart?.meta;
      if (!m?.regularMarketPrice) continue;
      const ts = chart.timestamp || [];
      const closes = chart.indicators?.quote?.[0]?.close || [];
      const history = ts
        .map((t, i) => (closes[i] != null
          ? { date: new Date(t * 1000).toISOString().slice(0, 10), value: +closes[i].toFixed(4) }
          : null))
        .filter(Boolean)
        .reverse();
      results[name] = {
        price: m.regularMarketPrice,
        date: new Date((m.regularMarketTime || Date.now() / 1000) * 1000).toISOString().slice(0, 10),
        history: history.slice(0, 10),
      };
    } catch (err) {
      log(`[COMMODITIES] Yahoo ${name} error: ${err.message}`);
    }
    await sleep(300);
  }
  if (Object.keys(results).length > 0) {
    saveData('commodities', results);
    log(`[COMMODITIES] Updated ${Object.keys(results).length} commodities (Yahoo keyless)`);
    recordRun('commodities', true);
  } else {
    recordRun('commodities', false);
  }
}

async function fetchBondsTreasuryGov() {
  const month = new Date().toISOString().slice(0, 7).replace('-', '');
  const url = `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=${month}`;
  const fields = {
    '1M': 'BC_1MONTH', '3M': 'BC_3MONTH', '6M': 'BC_6MONTH', '1Y': 'BC_1YEAR',
    '2Y': 'BC_2YEAR', '3Y': 'BC_3YEAR', '5Y': 'BC_5YEAR', '7Y': 'BC_7YEAR',
    '10Y': 'BC_10YEAR', '20Y': 'BC_20YEAR', '30Y': 'BC_30YEAR',
  };
  try {
    const res = await safeFetch(url, { headers: YF_UA });
    const xml = await res.text();
    const entries = xml.split('<m:properties>').slice(1);
    const results = {};
    for (const entry of entries) {
      const dateMatch = entry.match(/<d:NEW_DATE[^>]*>([^<]+)/);
      if (!dateMatch) continue;
      const date = dateMatch[1].slice(0, 10);
      for (const [mat, field] of Object.entries(fields)) {
        const m = entry.match(new RegExp(`<d:${field}[^>]*>([0-9.]+)`));
        if (!m) continue;
        (results[mat] ||= []).push({ date, value: parseFloat(m[1]) });
      }
    }
    if (Object.keys(results).length === 0) throw new Error('no entries parsed');
    for (const mat of Object.keys(results)) results[mat].reverse(); // newest first, like FRED
    saveData('bonds', results);
    const curve = Object.entries(results)
      .map(([mat, obs]) => (obs.length > 0 ? { maturity: mat, yield: obs[0].value, date: obs[0].date } : null))
      .filter(Boolean);
    saveData('yield_curve', curve);
    log(`[BONDS] Updated ${curve.length} maturities (treasury.gov keyless)`);
    recordRun('bonds', true);
  } catch (err) {
    log(`[BONDS] treasury.gov error: ${err.message}`);
    recordRun('bonds', false);
  }
}

async function fetchNewsYahooRss() {
  try {
    const res = await safeFetch('https://finance.yahoo.com/news/rssindex', { headers: YF_UA });
    const xml = await res.text();
    const items = xml.split('<item>').slice(1, 21);
    const articles = items.map(item => {
      const pick = (tag) => {
        const m = item.match(new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?</${tag}>`));
        return m ? m[1].trim() : '';
      };
      const title = pick('title');
      const url = pick('link');
      if (!title || !url) return null;
      return {
        id: url,
        title,
        summary: pick('description').replace(/<[^>]+>/g, '').slice(0, 200),
        source: pick('source') || 'Yahoo Finance',
        url,
        image: '',
        time: pick('pubDate') ? new Date(pick('pubDate')).getTime() : Date.now(),
        category: 'business',
      };
    }).filter(Boolean);
    return articles.length > 0 ? articles : null;
  } catch {
    return null;
  }
}

// ─── STOCKS (Alpha Vantage) ───
async function fetchStocks() {
  if (!AV_KEY) { return fetchStocksYahoo(); }
  const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'V', 'WMT'];
  const results = [];
  for (const sym of symbols) {
    if (!canRequest('alphavantage')) break;
    consumeToken('alphavantage');
    try {
      const res = await safeFetch(`https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${sym}&apikey=${AV_KEY}`);
      const data = await res.json();
      if (data['Note'] || data['Information']) { log(`[STOCKS] AV rate limited at ${sym}`); break; }
      const gq = data['Global Quote'];
      if (gq && gq['05. price']) {
        results.push({
          symbol: gq['01. symbol'], price: parseFloat(gq['05. price']),
          change: parseFloat(gq['09. change']), changePct: parseFloat(gq['10. change percent']),
          volume: parseInt(gq['06. volume'], 10), high: parseFloat(gq['03. high']),
          low: parseFloat(gq['04. low']), open: parseFloat(gq['02. open']),
          prevClose: parseFloat(gq['08. previous close']),
        });
      }
    } catch (err) {
      log(`[STOCKS] ${sym} error: ${err.message}`);
    }
    await sleep(1500);
  }
  if (results.length > 0) {
    saveData('stocks', results);
    log(`[STOCKS] Updated ${results.length} quotes`);
    recordRun('stocks', true);
  } else {
    recordRun('stocks', false);
  }
}

// ─── BONDS (FRED Treasury Yields) ───
async function fetchBonds() {
  if (!FRED_KEY) { return fetchBondsTreasuryGov(); }
  const series = {
    '1M': 'DGS1MO', '3M': 'DGS3MO', '6M': 'DGS6MO', '1Y': 'DGS1',
    '2Y': 'DGS2', '3Y': 'DGS3', '5Y': 'DGS5', '7Y': 'DGS7',
    '10Y': 'DGS10', '20Y': 'DGS20', '30Y': 'DGS30',
  };
  const results = {};
  for (const [mat, seriesId] of Object.entries(series)) {
    if (!canRequest('fred')) break;
    consumeToken('fred');
    try {
      const res = await safeFetch(`https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&sort_order=desc&limit=30`);
      const data = await res.json();
      const obs = (data.observations || []).filter(o => o.value !== '.').map(o => ({
        date: o.date, value: parseFloat(o.value),
      }));
      results[mat] = obs;
    } catch (err) {
      log(`[BONDS] ${mat} error: ${err.message}`);
    }
    await sleep(200);
  }
  if (Object.keys(results).length > 0) {
    saveData('bonds', results);
    // Build yield curve
    const curve = Object.entries(results).map(([mat, obs]) =>
      obs.length > 0 ? { maturity: mat, yield: obs[0].value, date: obs[0].date } : null
    ).filter(Boolean);
    saveData('yield_curve', curve);
    log(`[BONDS] Updated ${Object.keys(results).length} maturities`);
    recordRun('bonds', true);
  } else {
    recordRun('bonds', false);
  }
}

// ─── COMMODITIES (FRED) ───
async function fetchCommodities() {
  if (!FRED_KEY) { return fetchCommoditiesYahoo(); }
  const indicators = {
    GASOLINE: 'GASREGW', OIL_WTI: 'DCOILWTICO', OIL_BRENT: 'DCOILBRENTEU',
    NATGAS: 'DHHNGSP', COPPER: 'PCOPPUSDM',
  };
  const results = {};
  for (const [name, seriesId] of Object.entries(indicators)) {
    if (!canRequest('fred')) break;
    consumeToken('fred');
    try {
      const res = await safeFetch(`https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&sort_order=desc&limit=30`);
      const data = await res.json();
      const obs = (data.observations || []).filter(o => o.value !== '.').map(o => ({
        date: o.date, value: parseFloat(o.value),
      }));
      if (obs.length > 0) {
        results[name] = { price: obs[0].value, date: obs[0].date, history: obs.slice(0, 10) };
      }
    } catch (err) {
      log(`[COMMODITIES] ${name} error: ${err.message}`);
    }
    await sleep(200);
  }
  if (Object.keys(results).length > 0) {
    saveData('commodities', results);
    log(`[COMMODITIES] Updated ${Object.keys(results).length} commodities`);
    recordRun('commodities', true);
  } else {
    recordRun('commodities', false);
  }
}

// ─── ECONOMIC INDICATORS (FRED) ───
async function fetchEconomic() {
  if (!FRED_KEY) return;
  const series = {
    GDP: 'GDP', CPI: 'CPIAUCSL', UNEMPLOYMENT: 'UNRATE', FED_RATE: 'FEDFUNDS',
    RETAIL_SALES: 'RSXFS', HOUSING_STARTS: 'HOUST', M2: 'M2SL', TRADE_BALANCE: 'BOPGSTB',
  };
  const results = {};
  for (const [name, seriesId] of Object.entries(series)) {
    if (!canRequest('fred')) break;
    consumeToken('fred');
    try {
      const res = await safeFetch(`https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&sort_order=desc&limit=24`);
      const data = await res.json();
      const obs = (data.observations || []).filter(o => o.value !== '.').map(o => ({
        date: o.date, value: parseFloat(o.value),
      }));
      results[name] = obs;
    } catch (err) {
      log(`[ECON] ${name} error: ${err.message}`);
    }
    await sleep(200);
  }
  if (Object.keys(results).length > 0) {
    saveData('economic', results);
    log(`[ECON] Updated ${Object.keys(results).length} indicators`);
    recordRun('economic', true);
  } else {
    recordRun('economic', false);
  }
}

// ─── FEAR & GREED INDEX ───
async function fetchFearGreed() {
  try {
    const res = await safeFetch('https://api.alternative.me/fng/?limit=30&format=json');
    const data = await res.json();
    const entries = (data.data || []).map(d => ({
      value: parseInt(d.value, 10), label: d.value_classification,
      timestamp: parseInt(d.timestamp, 10) * 1000,
    }));
    saveData('fear_greed', entries);
    log(`[SENTIMENT] Fear & Greed updated: ${entries[0]?.value} (${entries[0]?.label})`);
    recordRun('fear_greed', true);
  } catch (err) {
    log(`[SENTIMENT] Fear & Greed error: ${err.message}`);
    recordRun('fear_greed', false);
  }
}

// ─── DEFI LLAMA ───
async function fetchDefi() {
  // Protocols
  if (canRequest('defillama')) {
    consumeToken('defillama');
    try {
      const res = await safeFetch('https://api.llama.fi/protocols');
      const data = await res.json();
      const protocols = (data || []).slice(0, 50).map(p => ({
        name: p.name, symbol: p.symbol || '', tvl: p.tvl || 0,
        change1h: p.change_1h || 0, change1d: p.change_1d || 0, change7d: p.change_7d || 0,
        category: p.category || '', chains: (p.chains || []).slice(0, 5), url: p.url || '',
      }));
      saveData('defi_protocols', protocols);
      log(`[DEFI] Protocols updated: ${protocols.length}`);
      recordRun('defi_protocols', true);
    } catch (err) {
      log(`[DEFI] Protocols error: ${err.message}`);
      recordRun('defi_protocols', false);
    }
  }

  await sleep(500);

  // Chain TVL
  if (canRequest('defillama')) {
    consumeToken('defillama');
    try {
      const res = await safeFetch('https://api.llama.fi/v2/chains');
      const data = await res.json();
      const chains = (data || []).slice(0, 20).map(c => ({
        name: c.name, tvl: c.tvl || 0, tokenSymbol: c.tokenSymbol || '',
      }));
      saveData('defi_chains', chains);
      log(`[DEFI] Chains updated: ${chains.length}`);
      recordRun('defi_chains', true);
    } catch (err) {
      log(`[DEFI] Chains error: ${err.message}`);
      recordRun('defi_chains', false);
    }
  }

  await sleep(500);

  // Total TVL history
  if (canRequest('defillama')) {
    consumeToken('defillama');
    try {
      const res = await safeFetch('https://api.llama.fi/v2/historicalChainTvl');
      const data = await res.json();
      const recent = (data || []).slice(-30).map(d => ({
        date: new Date(d.date * 1000).toISOString().split('T')[0], tvl: d.tvl,
      }));
      saveData('defi_tvl_history', recent);
      log(`[DEFI] TVL history updated`);
      recordRun('defi_tvl', true);
    } catch (err) {
      log(`[DEFI] TVL error: ${err.message}`);
      recordRun('defi_tvl', false);
    }
  }

  await sleep(500);

  // Yields
  if (canRequest('defillama')) {
    consumeToken('defillama');
    try {
      const res = await safeFetch('https://yields.llama.fi/pools');
      const data = await res.json();
      const pools = (data.data || [])
        .filter(p => p.tvlUsd > 1000000 && p.apy > 0 && p.apy < 100)
        .sort((a, b) => b.tvlUsd - a.tvlUsd)
        .slice(0, 40)
        .map(p => ({
          pool: p.pool, project: p.project, symbol: p.symbol, chain: p.chain,
          tvl: p.tvlUsd, apy: p.apy, apyBase: p.apyBase || 0, apyReward: p.apyReward || 0,
          stablecoin: p.stablecoin || false,
        }));
      saveData('defi_yields', pools);
      log(`[DEFI] Yields updated: ${pools.length} pools`);
      recordRun('defi_yields', true);
    } catch (err) {
      log(`[DEFI] Yields error: ${err.message}`);
      recordRun('defi_yields', false);
    }
  }

  await sleep(500);

  // Stablecoins
  if (canRequest('defillama')) {
    consumeToken('defillama');
    try {
      const res = await safeFetch('https://stablecoins.llama.fi/stablecoins?includePrices=true');
      const data = await res.json();
      const stables = (data.peggedAssets || []).slice(0, 15).map(s => ({
        name: s.name, symbol: s.symbol, pegType: s.pegType,
        circulating: s.circulating?.peggedUSD || 0, price: s.price || 1,
      }));
      saveData('defi_stablecoins', stables);
      log(`[DEFI] Stablecoins updated: ${stables.length}`);
      recordRun('defi_stablecoins', true);
    } catch (err) {
      log(`[DEFI] Stablecoins error: ${err.message}`);
      recordRun('defi_stablecoins', false);
    }
  }
}

// ─── NEWS (Cascade fallback) ───
async function fetchNews() {
  let articles = null;

  // 1. Finnhub
  if (!articles && FINNHUB_KEY && canRequest('finnhub')) {
    consumeToken('finnhub');
    try {
      const res = await safeFetch(`https://finnhub.io/api/v1/news?category=general&token=${FINNHUB_KEY}`);
      const data = await res.json();
      articles = (data || []).slice(0, 20).map(a => ({
        id: a.id, title: a.headline, summary: a.summary, source: a.source,
        url: a.url, image: a.image, time: a.datetime * 1000, category: a.category,
      }));
      if (articles.length === 0) articles = null;
    } catch { articles = null; }
  }

  // 2. NewsData.io
  if (!articles && NEWSDATA_KEY && canRequest('newsdata')) {
    consumeToken('newsdata');
    try {
      const res = await safeFetch(`https://newsdata.io/api/1/latest?apikey=${NEWSDATA_KEY}&q=financial+markets&language=en&category=business`);
      const data = await res.json();
      if (data.status === 'success') {
        articles = (data.results || []).slice(0, 20).map(a => ({
          id: a.article_id || a.link, title: a.title,
          summary: a.description?.slice(0, 200) || '', source: a.source_name || 'NewsData',
          url: a.link, image: a.image_url || '',
          time: a.pubDate ? new Date(a.pubDate).getTime() : Date.now(), category: 'business',
        }));
        if (articles.length === 0) articles = null;
      }
    } catch { articles = null; }
  }

  // 3. NewsAPI.org
  if (!articles && NEWSAPI_KEY && canRequest('newsapiorg')) {
    consumeToken('newsapiorg');
    try {
      const res = await safeFetch(`https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=20&apiKey=${NEWSAPI_KEY}`);
      const data = await res.json();
      if (data.status === 'ok') {
        articles = (data.articles || []).slice(0, 20).map(a => ({
          id: a.url, title: a.title, summary: a.description || '',
          source: a.source?.name || 'NewsAPI', url: a.url, image: a.urlToImage || '',
          time: a.publishedAt ? new Date(a.publishedAt).getTime() : Date.now(), category: 'business',
        }));
        if (articles.length === 0) articles = null;
      }
    } catch { articles = null; }
  }

  // 4. WorldNewsAPI
  if (!articles && WORLD_NEWS_KEY && canRequest('worldnews')) {
    consumeToken('worldnews');
    try {
      const res = await safeFetch(`https://api.worldnewsapi.com/search-news?text=stock+market+finance&language=en&number=20&api-key=${WORLD_NEWS_KEY}`);
      const data = await res.json();
      articles = (data.news || []).slice(0, 20).map(a => ({
        id: String(a.id || a.url), title: a.title, summary: a.text?.slice(0, 200) || '',
        source: a.source_country || 'WorldNews', url: a.url, image: a.image || '',
        time: a.publish_date ? new Date(a.publish_date).getTime() : Date.now(), category: 'business',
      }));
      if (articles.length === 0) articles = null;
    } catch { articles = null; }
  }

  // 5. GNews
  if (!articles && GNEWS_KEY && canRequest('gnews')) {
    consumeToken('gnews');
    try {
      const q = encodeURIComponent('financial markets');
      const res = await safeFetch(`https://gnews.io/api/v4/search?q=${q}&token=${GNEWS_KEY}&lang=en&max=10`);
      const data = await res.json();
      articles = (data.articles || []).map(a => ({
        id: a.url, title: a.title, summary: a.description, source: a.source?.name,
        url: a.url, image: a.image, time: new Date(a.publishedAt).getTime(), category: 'general',
      }));
      if (articles.length === 0) articles = null;
    } catch { articles = null; }
  }

  // 6. Yahoo Finance RSS (keyless — real headlines with no API key)
  if (!articles) {
    articles = await fetchNewsYahooRss();
  }

  if (articles && articles.length > 0) {
    saveData('news', articles);
    log(`[NEWS] Updated: ${articles.length} articles`);
    recordRun('news', true);
  } else {
    log('[NEWS] No articles from any source');
    recordRun('news', false);
  }
}

// ─── GITHUB ───
async function fetchGithub() {
  const queries = [
    'finance trading stock market crypto',
    'topic:quantitative-finance',
    'topic:algorithmic-trading',
  ];
  const allRepos = [];
  const seen = new Set();

  for (const q of queries) {
    if (!canRequest('github')) break;
    consumeToken('github');
    try {
      const res = await safeFetch(
        `https://api.github.com/search/repositories?q=${encodeURIComponent(q)}&sort=stars&order=desc&per_page=30`,
        { headers: { Accept: 'application/vnd.github.v3+json', 'User-Agent': 'DragonScope/1.0' } }
      );
      const data = await res.json();
      for (const r of (data.items || [])) {
        if (!seen.has(r.id)) {
          seen.add(r.id);
          allRepos.push({
            id: r.id, name: r.full_name, description: r.description?.slice(0, 200) || '',
            stars: r.stargazers_count, forks: r.forks_count, language: r.language || 'Unknown',
            topics: (r.topics || []).slice(0, 5), url: r.html_url, updated: r.updated_at,
            openIssues: r.open_issues_count, license: r.license?.spdx_id || '',
          });
        }
      }
    } catch (err) {
      log(`[GITHUB] Error: ${err.message}`);
    }
    await sleep(1000);
  }

  allRepos.sort((a, b) => b.stars - a.stars);
  const top = allRepos.slice(0, 50);
  if (top.length > 0) {
    saveData('github_repos', top);
    log(`[GITHUB] Updated: ${top.length} repos`);
    recordRun('github', true);
  } else {
    recordRun('github', false);
  }
}

// ─── HUGGINGFACE ───
async function fetchHuggingFace() {
  const searches = ['financial-sentiment', 'stock-prediction', 'finance-text-classification', 'trading'];
  const allModels = [];
  const seen = new Set();

  for (const search of searches) {
    if (!canRequest('huggingface')) break;
    consumeToken('huggingface');
    try {
      const res = await safeFetch(
        `https://huggingface.co/api/models?search=${encodeURIComponent(search)}&sort=downloads&direction=-1&limit=20`
      );
      const data = await res.json();
      for (const m of (data || [])) {
        const id = m.modelId || m.id;
        if (!seen.has(id)) {
          seen.add(id);
          allModels.push({
            id, name: id, pipeline: m.pipeline_tag || 'unknown',
            downloads: m.downloads || 0, likes: m.likes || 0,
            tags: (m.tags || []).slice(0, 8), lastModified: m.lastModified, library: m.library_name || '',
          });
        }
      }
    } catch (err) {
      log(`[HUGGINGFACE] Error: ${err.message}`);
    }
    await sleep(500);
  }

  allModels.sort((a, b) => b.downloads - a.downloads);
  const top = allModels.slice(0, 40);
  if (top.length > 0) {
    saveData('huggingface_models', top);
    log(`[HUGGINGFACE] Updated: ${top.length} models`);
    recordRun('huggingface', true);
  } else {
    recordRun('huggingface', false);
  }
}

// ─── REDDIT ───
async function fetchReddit() {
  const subs = ['wallstreetbets', 'cryptocurrency', 'stocks', 'investing', 'CryptoMarkets'];
  const allPosts = [];

  for (const sub of subs) {
    if (!canRequest('reddit')) break;
    consumeToken('reddit');
    try {
      const res = await safeFetch(`https://www.reddit.com/r/${sub}/hot.json?limit=15&raw_json=1`, {
        headers: { 'User-Agent': 'DragonScope/1.0' },
      });
      const data = await res.json();
      const posts = (data.data?.children || []).filter(p => !p.data.stickied).map(p => ({
        id: p.data.id, title: p.data.title, author: p.data.author,
        score: p.data.score, upvoteRatio: p.data.upvote_ratio, numComments: p.data.num_comments,
        created: p.data.created_utc * 1000, subreddit: p.data.subreddit,
        flair: p.data.link_flair_text || '', url: `https://reddit.com${p.data.permalink}`,
        selftext: (p.data.selftext || '').slice(0, 150),
      }));
      allPosts.push(...posts);
    } catch (err) {
      log(`[REDDIT] ${sub} error: ${err.message}`);
    }
    await sleep(1500);
  }

  allPosts.sort((a, b) => b.score - a.score);
  const top = allPosts.slice(0, 50);
  if (top.length > 0) {
    // Also compute sentiment
    const bullish = ['moon', 'bull', 'calls', 'buy', 'long', 'pump', 'rocket', 'gain', 'green', 'breakout', 'ath', 'yolo', 'tendies'];
    const bearish = ['bear', 'puts', 'sell', 'short', 'dump', 'crash', 'red', 'loss', 'dip', 'down', 'fear', 'recession', 'bag'];
    let bullCount = 0, bearCount = 0, neutral = 0;
    for (const p of top) {
      const text = (p.title + ' ' + p.flair).toLowerCase();
      const isBull = bullish.some(w => text.includes(w));
      const isBear = bearish.some(w => text.includes(w));
      if (isBull && !isBear) bullCount++;
      else if (isBear && !isBull) bearCount++;
      else neutral++;
    }
    const total = top.length || 1;
    const sentiment = {
      bullish: Math.round((bullCount / total) * 100),
      bearish: Math.round((bearCount / total) * 100),
      neutral: Math.round((neutral / total) * 100),
      bullCount, bearCount, neutralCount: neutral, total: top.length,
    };
    saveData('reddit_posts', top);
    saveData('reddit_sentiment', sentiment);
    log(`[REDDIT] Updated: ${top.length} posts | Sentiment: ${sentiment.bullish}% bull / ${sentiment.bearish}% bear`);
    recordRun('reddit', true);
  } else {
    recordRun('reddit', false);
  }
}

// ─── SEC EDGAR ───
async function fetchSEC() {
  if (!canRequest('sec')) return;
  consumeToken('sec');
  try {
    const startdt = new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0];
    const enddt = new Date().toISOString().split('T')[0];
    const params = new URLSearchParams({
      q: 'quarterly earnings', dateRange: 'custom', startdt, enddt, forms: '10-K,10-Q,8-K',
    });
    const res = await safeFetch(`https://efts.sec.gov/LATEST/search?${params}`, {
      headers: { 'User-Agent': 'DragonScope research@example.com' },
    });
    const data = await res.json();
    const filings = (data.hits?.hits || []).slice(0, 20).map(h => {
      const s = h._source || {};
      return {
        id: h._id, company: s.display_names?.[0] || s.entity_name || 'Unknown',
        ticker: s.tickers?.[0] || '', form: s.form_type || '', filed: s.file_date || '',
        description: s.display_description || s.file_description || '',
        url: s.file_url ? `https://www.sec.gov/Archives/${s.file_url}` : '',
      };
    });
    saveData('sec_filings', filings);
    log(`[SEC] Updated: ${filings.length} filings`);
    recordRun('sec', true);
  } catch (err) {
    log(`[SEC] Error: ${err.message}`);
    recordRun('sec', false);
  }
}

// ─── ARXIV ───
async function fetchArxiv() {
  const queries = [
    'algorithmic trading machine learning',
    'portfolio optimization deep learning',
    'financial sentiment analysis NLP',
    'cryptocurrency market prediction',
  ];
  const allPapers = [];
  const seen = new Set();

  for (const q of queries) {
    if (!canRequest('arxiv')) break;
    consumeToken('arxiv');
    try {
      const params = new URLSearchParams({
        search_query: `cat:q-fin* OR all:${q}`, start: 0, max_results: 10,
        sortBy: 'submittedDate', sortOrder: 'descending',
      });
      const res = await safeFetch(`https://export.arxiv.org/api/query?${params}`);
      const text = await res.text();

      // Parse XML without DOMParser (Node.js compatible)
      const entries = text.split('<entry>').slice(1);
      for (const entry of entries) {
        const extract = (tag) => {
          const m = entry.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
          return m ? m[1].trim().replace(/\s+/g, ' ') : '';
        };
        const id = extract('id');
        if (seen.has(id)) continue;
        seen.add(id);

        const authors = [...entry.matchAll(/<name>([^<]+)<\/name>/g)].map(m => m[1]).slice(0, 3);
        const categories = [...entry.matchAll(/category[^>]*term="([^"]+)"/g)].map(m => m[1]).slice(0, 3);
        const pdfLink = (entry.match(/link[^>]*title="pdf"[^>]*href="([^"]+)"/) || [])[1] || '';

        allPapers.push({
          id, title: extract('title'), summary: extract('summary').slice(0, 300),
          authors, categories, published: extract('published').split('T')[0],
          pdfUrl: pdfLink, url: id,
        });
      }
    } catch (err) {
      log(`[ARXIV] Error: ${err.message}`);
    }
    await sleep(3500); // arXiv requires 3s between requests
  }

  allPapers.sort((a, b) => (b.published || '').localeCompare(a.published || ''));
  const top = allPapers.slice(0, 30);
  if (top.length > 0) {
    saveData('arxiv_papers', top);
    log(`[ARXIV] Updated: ${top.length} papers`);
    recordRun('arxiv', true);
  } else {
    recordRun('arxiv', false);
  }
}

// ─── WORLD BANK (China Economic) ───
async function fetchWorldBank() {
  const indicators = [
    { id: 'NY.GDP.MKTP.CD', label: 'GDP (USD)' },
    { id: 'NE.TRD.GNFS.ZS', label: 'Trade (% GDP)' },
    { id: 'FP.CPI.TOTL.ZG', label: 'CPI Inflation' },
    { id: 'BN.CAB.XOKA.CD', label: 'Current Account' },
  ];
  const results = [];
  for (const ind of indicators) {
    try {
      const res = await safeFetch(
        `https://api.worldbank.org/v2/country/CHN/indicator/${ind.id}?format=json&per_page=5&date=2020:2025`
      );
      const data = await res.json();
      const entries = data?.[1] || [];
      const latest = entries.find(e => e.value != null);
      if (latest) {
        results.push({ indicator: ind.label, value: latest.value, year: latest.date, id: ind.id });
      }
    } catch { /* skip */ }
    await sleep(500);
  }

  // Also fetch USA indicators
  const usaIndicators = [
    { id: 'NY.GDP.MKTP.KD.ZG', label: 'GDP Growth' },
    { id: 'FP.CPI.TOTL.ZG', label: 'CPI Inflation' },
    { id: 'SL.UEM.TOTL.ZS', label: 'Unemployment' },
  ];
  const usaResults = [];
  for (const ind of usaIndicators) {
    try {
      const res = await safeFetch(
        `https://api.worldbank.org/v2/country/USA/indicator/${ind.id}?format=json&per_page=5&date=2020:2025`
      );
      const data = await res.json();
      const entries = data?.[1] || [];
      const latest = entries.find(e => e.value != null);
      if (latest) {
        usaResults.push({ indicator: ind.label, value: latest.value, year: latest.date, id: ind.id });
      }
    } catch { /* skip */ }
    await sleep(500);
  }

  if (results.length > 0) {
    saveData('worldbank_china', results);
    log(`[WORLDBANK] China data updated: ${results.length} indicators`);
  }
  if (usaResults.length > 0) {
    saveData('worldbank_usa', usaResults);
    log(`[WORLDBANK] USA data updated: ${usaResults.length} indicators`);
  }
  recordRun('worldbank', results.length > 0 || usaResults.length > 0);
}

// ─── BINANCE WEBSOCKET (Real-time crypto) ───
let binanceWs = null;
let binanceReconnects = 0;
const MAX_RECONNECTS = 100;

function startBinanceWebSocket() {
  const pairs = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'adausdt', 'dotusdt', 'avaxusdt', 'maticusdt', 'linkusdt', 'xrpusdt'];
  const streams = pairs.map(p => `${p}@ticker`).join('/');
  const url = `wss://stream.binance.com:9443/stream?streams=${streams}`;

  try {
    binanceWs = new WebSocket(url);

    binanceWs.on('open', () => {
      log('[BINANCE WS] Connected');
      binanceReconnects = 0;
    });

    const tickerData = {};
    let lastSave = 0;

    binanceWs.on('message', (raw) => {
      try {
        const msg = JSON.parse(raw.toString());
        const d = msg.data;
        if (!d || !d.s) return;
        tickerData[d.s] = {
          symbol: d.s, price: parseFloat(d.c), change24h: parseFloat(d.P),
          high24h: parseFloat(d.h), low24h: parseFloat(d.l), volume: parseFloat(d.v),
          quoteVolume: parseFloat(d.q), timestamp: Date.now(),
        };
        // Save every 10 seconds
        if (Date.now() - lastSave > 10000) {
          saveData('binance_tickers', tickerData);
          lastSave = Date.now();
        }
      } catch { /* ignore parse errors */ }
    });

    binanceWs.on('close', () => {
      log('[BINANCE WS] Disconnected');
      reconnectBinance();
    });

    binanceWs.on('error', (err) => {
      log(`[BINANCE WS] Error: ${err.message}`);
    });
  } catch (err) {
    log(`[BINANCE WS] Connection error: ${err.message}`);
    reconnectBinance();
  }
}

function reconnectBinance() {
  if (binanceReconnects >= MAX_RECONNECTS) {
    log('[BINANCE WS] Max reconnects reached, stopping');
    return;
  }
  const delay = Math.min(1000 * Math.pow(2, binanceReconnects), 30000);
  binanceReconnects++;
  log(`[BINANCE WS] Reconnecting in ${delay}ms (attempt ${binanceReconnects})`);
  setTimeout(startBinanceWebSocket, delay);
}

// ─── CNY/CNH RATES ───
async function fetchCNYRates() {
  if (!canRequest('frankfurter')) return;
  consumeToken('frankfurter');
  try {
    const res = await safeFetch('https://api.frankfurter.dev/v1/latest?base=USD&symbols=CNY');
    const data = await res.json();
    const cny = data.rates?.CNY || 7.24;
    saveData('cny_rates', { cnyUsd: cny, timestamp: Date.now() });
    log(`[CNY] Rate updated: ${cny}`);
    recordRun('cny', true);
  } catch (err) {
    log(`[CNY] Error: ${err.message}`);
    recordRun('cny', false);
  }
}

// ─── Utility ───
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ═══════════════════════════════════════════════════════
// SCHEDULING
// ═══════════════════════════════════════════════════════

function setupSchedules() {
  // ── Every 60 seconds ──
  cron.schedule('* * * * *', async () => {
    await fetchForex();
    await sleep(2000);
    await fetchCryptoMarkets();
  });

  // ── Every 2 minutes ──
  cron.schedule('*/2 * * * *', async () => {
    await fetchCryptoGlobal();
  });

  // ── Every 5 minutes ──
  cron.schedule('*/5 * * * *', async () => {
    await fetchFearGreed();
    await sleep(1000);
    await fetchCNYRates();
  });

  // ── Every 10 minutes ──
  cron.schedule('*/10 * * * *', async () => {
    await fetchBonds();
    await sleep(2000);
    await fetchCommodities();
  });

  // ── Every 15 minutes ──
  cron.schedule('*/15 * * * *', async () => {
    await fetchDefi();
  });

  // ── Every 30 minutes ──
  cron.schedule('*/30 * * * *', async () => {
    await fetchNews();
    await sleep(3000);
    await fetchReddit();
  });

  // ── Every hour ──
  cron.schedule('0 * * * *', async () => {
    await fetchStocks();
    await sleep(5000);
    await fetchGithub();
    await sleep(3000);
    await fetchHuggingFace();
    await sleep(3000);
    await fetchSEC();
    await sleep(5000);
    await fetchArxiv();
  });

  // ── Every 5 minutes for economic (FRED) ──
  cron.schedule('*/5 * * * *', async () => {
    await fetchEconomic();
  });

  // ── Every 6 hours ──
  cron.schedule('0 */6 * * *', async () => {
    await fetchWorldBank();
    await sleep(3000);
    await fetchForexTimeseries();
    await sleep(2000);
    await fetchTrendingCoins();
  });

  log('[SCHEDULER] All cron jobs configured');
}

// ═══════════════════════════════════════════════════════
// STARTUP
// ═══════════════════════════════════════════════════════

async function initialFetch() {
  log('═══════════════════════════════════════════════');
  log('  DragonScope Data Collector - Starting');
  log('═══════════════════════════════════════════════');
  log(`  FRED key: ${FRED_KEY ? 'YES' : 'NO'}`);
  log(`  Alpha Vantage key: ${AV_KEY ? 'YES' : 'NO'}`);
  log(`  Finnhub key: ${FINNHUB_KEY ? 'YES' : 'NO'}`);
  log(`  FMP key: ${FMP_KEY ? 'YES' : 'NO'}`);
  log(`  GNews key: ${GNEWS_KEY ? 'YES' : 'NO'}`);
  log(`  NewsData key: ${NEWSDATA_KEY ? 'YES' : 'NO'}`);
  log(`  NewsAPI key: ${NEWSAPI_KEY ? 'YES' : 'NO'}`);
  log(`  WorldNews key: ${WORLD_NEWS_KEY ? 'YES' : 'NO'}`);
  log(`  Data dir: ${DATA_DIR}`);
  log('═══════════════════════════════════════════════');

  // Run all fetchers once on startup
  log('[STARTUP] Running initial data fetch...');

  await fetchForex();
  await sleep(1000);
  await fetchCryptoMarkets();
  await sleep(2000);
  await fetchCryptoGlobal();
  await sleep(2000);
  await fetchTrendingCoins();
  await sleep(1000);
  await fetchFearGreed();
  await sleep(1000);
  await fetchBonds();
  await sleep(1000);
  await fetchCommodities();
  await sleep(1000);
  await fetchEconomic();
  await sleep(1000);
  await fetchDefi();
  await sleep(2000);
  await fetchNews();
  await sleep(2000);
  await fetchReddit();
  await sleep(2000);
  await fetchStocks();
  await sleep(2000);
  await fetchGithub();
  await sleep(2000);
  await fetchHuggingFace();
  await sleep(2000);
  await fetchSEC();
  await sleep(4000);
  await fetchArxiv();
  await sleep(1000);
  await fetchWorldBank();
  await sleep(1000);
  await fetchForexTimeseries();
  await sleep(1000);
  await fetchCNYRates();

  log('[STARTUP] Initial fetch complete');
  saveData('_stats', stats);
}

// ─── Graceful shutdown ───
function shutdown(signal) {
  log(`\n[SHUTDOWN] Received ${signal}, cleaning up...`);
  if (binanceWs) {
    binanceWs.close();
    binanceWs = null;
  }
  saveData('_stats', stats);
  log('[SHUTDOWN] Goodbye!');
  process.exit(0);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('uncaughtException', (err) => {
  log(`[FATAL] Uncaught exception: ${err.message}`);
  log(err.stack);
  // Don't exit — let pm2 handle restart
});
process.on('unhandledRejection', (err) => {
  log(`[WARN] Unhandled rejection: ${err?.message || err}`);
});

// ─── Main ───
(async () => {
  await initialFetch();
  setupSchedules();
  startBinanceWebSocket();
  log('[RUNNING] Data collector is now running 24/7. Press Ctrl+C to stop.');
})();
