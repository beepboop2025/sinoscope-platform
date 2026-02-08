import { useState, useRef, useCallback, useEffect } from 'react';
import alasql from 'alasql';
import { fetchGithubFinanceRepos, getMockGithubRepos } from '../services/api/githubApi';
import { fetchFinanceModels, getMockHuggingFaceModels } from '../services/api/huggingfaceApi';
import { fetchDefiProtocols, getMockDefiData } from '../services/api/defiLlamaApi';
import { fetchAllFinanceSubs, getMockRedditPosts } from '../services/api/redditApi';

const MAX_HISTORY = 50;
const THROTTLE_MS = 2000;
const STORAGE_KEY = 'dragonscope_saved_queries';

const BLOCKED_KEYWORDS = /^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE)\b/i;

function safeNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

const SCHEMA = {
  stocks:      { columns: ['symbol STRING', 'price NUMBER', 'changePct NUMBER', 'volume NUMBER', 'high NUMBER', 'low NUMBER', 'market STRING'] },
  crypto:      { columns: ['symbol STRING', 'price NUMBER', 'changePct NUMBER', 'volume NUMBER', 'marketCap NUMBER', 'market STRING'] },
  forex:       { columns: ['pair STRING', 'rate NUMBER', 'changePct NUMBER', 'bid NUMBER', 'ask NUMBER', 'market STRING'] },
  bonds:       { columns: ['maturity STRING', 'yield NUMBER', 'change NUMBER'] },
  commodities: { columns: ['name STRING', 'price NUMBER', 'changePct NUMBER', 'unit STRING', 'market STRING'] },
  indices:     { columns: ['symbol STRING', 'name STRING', 'price NUMBER', 'changePct NUMBER'] },
  economic:    { columns: ['indicator STRING', 'value NUMBER', 'unit STRING', 'date STRING'] },
  github_repos: { columns: ['name STRING', 'stars NUMBER', 'forks NUMBER', 'language STRING', 'description STRING', 'license STRING'] },
  hf_models:   { columns: ['name STRING', 'pipeline STRING', 'downloads NUMBER', 'likes NUMBER', 'library STRING'] },
  defi_protocols: { columns: ['name STRING', 'symbol STRING', 'tvl NUMBER', 'change1d NUMBER', 'category STRING'] },
  reddit_posts:  { columns: ['title STRING', 'subreddit STRING', 'score NUMBER', 'comments NUMBER', 'flair STRING'] },
  all_assets:  { columns: ['symbol STRING', 'asset_type STRING', 'price NUMBER', 'changePct NUMBER', 'volume NUMBER'] },
};

function loadSavedQueries() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistSavedQueries(queries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queries));
  } catch (e) {
    if (e?.name === 'QuotaExceededError') {
      console.warn('localStorage quota exceeded, clearing saved queries');
      localStorage.removeItem(STORAGE_KEY);
    }
  }
}

export function useSqlEngine(marketData) {
  const dbRef = useRef(null);
  const lastSyncRef = useRef(0);
  const [isReady, setIsReady] = useState(false);
  const [tableInfo, setTableInfo] = useState({});
  const [history, setHistory] = useState([]);
  const [savedQueries, setSavedQueries] = useState(loadSavedQueries);

  // Initialize database once
  if (!dbRef.current) {
    dbRef.current = new alasql.Database('dragonscope');
    const db = dbRef.current;
    db.exec('CREATE TABLE IF NOT EXISTS stocks (symbol STRING, price NUMBER, changePct NUMBER, volume NUMBER, high NUMBER, low NUMBER, market STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS crypto (symbol STRING, price NUMBER, changePct NUMBER, volume NUMBER, marketCap NUMBER, market STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS forex (pair STRING, rate NUMBER, changePct NUMBER, bid NUMBER, ask NUMBER, market STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS bonds (maturity STRING, yield NUMBER, change NUMBER)');
    db.exec('CREATE TABLE IF NOT EXISTS commodities (name STRING, price NUMBER, changePct NUMBER, unit STRING, market STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS indices (symbol STRING, name STRING, price NUMBER, changePct NUMBER)');
    db.exec('CREATE TABLE IF NOT EXISTS economic (indicator STRING, value NUMBER, unit STRING, date STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS github_repos (name STRING, stars NUMBER, forks NUMBER, language STRING, description STRING, license STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS hf_models (name STRING, pipeline STRING, downloads NUMBER, likes NUMBER, library STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS defi_protocols (name STRING, symbol STRING, tvl NUMBER, change1d NUMBER, category STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS reddit_posts (title STRING, subreddit STRING, score NUMBER, comments NUMBER, flair STRING)');
    db.exec('CREATE TABLE IF NOT EXISTS all_assets (symbol STRING, asset_type STRING, price NUMBER, changePct NUMBER, volume NUMBER)');
  }

  // Load GitHub and HuggingFace data into SQL (once, then refresh every 10 min)
  const researchLoadedRef = useRef(false);
  useEffect(() => {
    if (researchLoadedRef.current) return;
    researchLoadedRef.current = true;

    async function loadResearchData() {
      const db = dbRef.current;

      // GitHub repos
      try {
        const repos = await fetchGithubFinanceRepos() || getMockGithubRepos();
        db.exec('DELETE FROM github_repos');
        for (const r of repos) {
          db.exec('INSERT INTO github_repos VALUES (?,?,?,?,?,?)', [
            r.name, r.stars || 0, r.forks || 0, r.language || '', (r.description || '').slice(0, 200), r.license || ''
          ]);
        }
      } catch { /* use mock on failure */ }

      // HuggingFace models
      try {
        const models = await fetchFinanceModels() || getMockHuggingFaceModels();
        db.exec('DELETE FROM hf_models');
        for (const m of models) {
          db.exec('INSERT INTO hf_models VALUES (?,?,?,?,?)', [
            m.name, m.pipeline || '', m.downloads || 0, m.likes || 0, m.library || ''
          ]);
        }
      } catch { /* use mock on failure */ }

      // DeFi protocols
      try {
        const protos = await fetchDefiProtocols() || getMockDefiData().protocols;
        db.exec('DELETE FROM defi_protocols');
        for (const p of protos) {
          db.exec('INSERT INTO defi_protocols VALUES (?,?,?,?,?)', [
            p.name, p.symbol || '', p.tvl || 0, p.change1d || 0, p.category || ''
          ]);
        }
      } catch { /* use mock on failure */ }

      // Reddit posts
      try {
        const posts = await fetchAllFinanceSubs() || getMockRedditPosts();
        db.exec('DELETE FROM reddit_posts');
        for (const p of posts) {
          db.exec('INSERT INTO reddit_posts VALUES (?,?,?,?,?)', [
            (p.title || '').slice(0, 200), p.subreddit || '', p.score || 0, p.numComments || 0, p.flair || ''
          ]);
        }
      } catch { /* use mock on failure */ }
    }

    loadResearchData();
  }, []);

  // Sync market data into SQL tables (throttled)
  useEffect(() => {
    if (!marketData) return;
    const now = Date.now();
    if (now - lastSyncRef.current < THROTTLE_MS) return;
    lastSyncRef.current = now;

    const db = dbRef.current;
    const info = {};

    // Clear tables
    db.exec('DELETE FROM stocks');
    db.exec('DELETE FROM crypto');
    db.exec('DELETE FROM forex');
    db.exec('DELETE FROM bonds');
    db.exec('DELETE FROM commodities');
    db.exec('DELETE FROM indices');
    db.exec('DELETE FROM economic');
    db.exec('DELETE FROM all_assets');

    // Stocks
    const stocks = marketData.stocks || {};
    for (const [sym, d] of Object.entries(stocks)) {
      db.exec('INSERT INTO stocks VALUES (?,?,?,?,?,?,?)', [
        sym, safeNum(d.price), safeNum(d.changePct), safeNum(d.volume),
        safeNum(d.high), safeNum(d.low), 'stock'
      ]);
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [
        sym, 'stock', safeNum(d.price), safeNum(d.changePct), safeNum(d.volume)
      ]);
    }
    info.stocks = Object.keys(stocks).length;

    // Crypto
    const crypto = marketData.crypto || {};
    for (const [sym, d] of Object.entries(crypto)) {
      db.exec('INSERT INTO crypto VALUES (?,?,?,?,?,?)', [
        sym, safeNum(d.price), safeNum(d.changePct), safeNum(d.volume),
        safeNum(d.marketCap || d.market_cap), 'crypto'
      ]);
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [
        sym, 'crypto', safeNum(d.price), safeNum(d.changePct), safeNum(d.volume)
      ]);
    }
    info.crypto = Object.keys(crypto).length;

    // Forex
    const forex = marketData.forex || {};
    for (const [pair, d] of Object.entries(forex)) {
      const rate = typeof d === 'number' ? d : safeNum(d.rate || d.price);
      const chg = typeof d === 'number' ? 0 : safeNum(d.changePct);
      const bid = typeof d === 'number' ? d : safeNum(d.bid || d.rate || d.price);
      const ask = typeof d === 'number' ? d : safeNum(d.ask || d.rate || d.price);
      db.exec('INSERT INTO forex VALUES (?,?,?,?,?,?)', [pair, rate, chg, bid, ask, 'forex']);
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [pair, 'forex', rate, chg, 0]);
    }
    info.forex = Object.keys(forex).length;

    // Bonds
    const bonds = marketData.bonds || [];
    const bondArr = Array.isArray(bonds) ? bonds : Object.entries(bonds).map(([k, v]) => ({ maturity: k, ...(typeof v === 'number' ? { yield: v } : v) }));
    for (const b of bondArr) {
      db.exec('INSERT INTO bonds VALUES (?,?,?)', [
        b.maturity || b.term || '', safeNum(b.yield || b.rate), safeNum(b.change)
      ]);
    }
    info.bonds = bondArr.length;

    // Commodities
    const commodities = marketData.commodities || {};
    for (const [name, d] of Object.entries(commodities)) {
      const price = typeof d === 'number' ? d : safeNum(d.price);
      const chg = typeof d === 'number' ? 0 : safeNum(d.changePct);
      const unit = typeof d === 'object' ? (d.unit || '') : '';
      db.exec('INSERT INTO commodities VALUES (?,?,?,?,?)', [name, price, chg, unit, 'commodity']);
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [name, 'commodity', price, chg, 0]);
    }
    info.commodities = Object.keys(commodities).length;

    // Indices
    const indices = marketData.indices || {};
    for (const [sym, d] of Object.entries(indices)) {
      db.exec('INSERT INTO indices VALUES (?,?,?,?)', [
        d.symbol || sym, d.name || sym, safeNum(d.price), safeNum(d.changePct)
      ]);
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [
        d.symbol || sym, 'index', safeNum(d.price), safeNum(d.changePct), 0
      ]);
    }
    info.indices = Object.keys(indices).length;

    // Economic indicators
    const economic = marketData.economic || {};
    for (const [key, d] of Object.entries(economic)) {
      if (d && typeof d === 'object') {
        db.exec('INSERT INTO economic VALUES (?,?,?,?)', [
          key, safeNum(d.value), d.unit || '', d.date || ''
        ]);
      }
    }
    info.economic = Object.keys(economic).length;

    setTableInfo(info);
    setIsReady(true);
  }, [marketData]);

  // Execute a SQL query
  const executeQuery = useCallback((sql) => {
    const trimmed = sql.trim();
    if (!trimmed) return { error: 'Empty query' };

    if (BLOCKED_KEYWORDS.test(trimmed)) {
      return { error: 'Only SELECT queries are allowed' };
    }

    const start = performance.now();
    try {
      const result = dbRef.current.exec(trimmed);
      const elapsed = performance.now() - start;
      const rows = Array.isArray(result) ? result : [];
      const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

      const entry = {
        sql: trimmed,
        rowCount: rows.length,
        elapsed: elapsed.toFixed(1),
        timestamp: Date.now(),
        error: null,
      };
      setHistory(prev => [entry, ...prev].slice(0, MAX_HISTORY));

      return { rows, columns, rowCount: rows.length, elapsed: elapsed.toFixed(1), error: null };
    } catch (err) {
      const elapsed = performance.now() - start;
      const entry = {
        sql: trimmed,
        rowCount: 0,
        elapsed: elapsed.toFixed(1),
        timestamp: Date.now(),
        error: err.message,
      };
      setHistory(prev => [entry, ...prev].slice(0, MAX_HISTORY));

      return { rows: [], columns: [], rowCount: 0, elapsed: elapsed.toFixed(1), error: err.message };
    }
  }, []);

  const clearHistory = useCallback(() => setHistory([]), []);

  // Schema inspection
  const getSchema = useCallback(() => SCHEMA, []);

  // Save a query
  const saveQuery = useCallback((label, sql) => {
    setSavedQueries(prev => {
      const next = [{ label, sql, timestamp: Date.now() }, ...prev.filter(q => q.sql !== sql)].slice(0, 20);
      persistSavedQueries(next);
      return next;
    });
  }, []);

  // Remove a saved query
  const removeSavedQuery = useCallback((sql) => {
    setSavedQueries(prev => {
      const next = prev.filter(q => q.sql !== sql);
      persistSavedQueries(next);
      return next;
    });
  }, []);

  // Export results to CSV
  const exportCsv = useCallback((columns, rows, filename = 'query_results.csv') => {
    if (!columns.length || !rows.length) return;
    const header = columns.join(',');
    const body = rows.map(row =>
      columns.map(col => {
        const val = row[col];
        if (val == null) return '';
        const str = String(val);
        return str.includes(',') || str.includes('"') || str.includes('\n')
          ? `"${str.replace(/"/g, '""')}"` : str;
      }).join(',')
    ).join('\n');
    const blob = new Blob([header + '\n' + body], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  // Copy results to clipboard
  const copyResults = useCallback((columns, rows) => {
    if (!columns.length || !rows.length) return Promise.resolve(false);
    const header = columns.join('\t');
    const body = rows.map(row => columns.map(col => String(row[col] ?? '')).join('\t')).join('\n');
    return navigator.clipboard.writeText(header + '\n' + body).then(() => true).catch(() => false);
  }, []);

  return {
    executeQuery, isReady, tableInfo, history, clearHistory,
    getSchema, savedQueries, saveQuery, removeSavedQuery,
    exportCsv, copyResults,
  };
}
