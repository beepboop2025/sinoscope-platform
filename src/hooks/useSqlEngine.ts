import { useState, useRef, useCallback, useEffect } from 'react';
import alasql from 'alasql';
import { fetchGithubFinanceRepos } from '../services/api/githubApi';
import { fetchFinanceModels } from '../services/api/huggingfaceApi';
import { fetchDefiProtocols } from '../services/api/defiLlamaApi';
import { fetchAllFinanceSubs } from '../services/api/redditApi';

const MAX_HISTORY = 50;
const THROTTLE_MS = 2000;
const STORAGE_KEY = 'dragonscope_saved_queries';

const BLOCKED_KEYWORDS = /^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE)\b/i;

interface TableInfo {
  stocks?: number;
  crypto?: number;
  forex?: number;
  bonds?: number;
  commodities?: number;
  indices?: number;
  economic?: number;
}

interface HistoryEntry {
  sql: string;
  rowCount: number;
  elapsed: string;
  timestamp: number;
  error: string | null;
}

interface SavedQuery {
  label: string;
  sql: string;
  timestamp: number;
}

interface QueryResult {
  rows?: Record<string, unknown>[];
  columns?: string[];
  rowCount?: number;
  elapsed?: string;
  error: string | null;
}

interface MarketDataRecord {
  price?: number;
  changePct?: number;
  volume?: number;
  high?: number;
  low?: number;
  marketCap?: number;
  market_cap?: number;
  rate?: number;
  bid?: number;
  ask?: number;
  maturity?: string;
  term?: string;
  yield?: number;
  change?: number;
  unit?: string;
  symbol?: string;
  name?: string;
  value?: number;
  date?: string;
}

interface MarketData {
  stocks?: Record<string, MarketDataRecord>;
  crypto?: Record<string, MarketDataRecord>;
  forex?: Record<string, number | MarketDataRecord>;
  bonds?: MarketDataRecord[] | Record<string, MarketDataRecord | number>;
  commodities?: Record<string, number | MarketDataRecord>;
  indices?: Record<string, MarketDataRecord>;
  economic?: Record<string, MarketDataRecord>;
}

interface SchemaTable {
  columns: string[];
}

function safeNum(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

const SCHEMA: Record<string, SchemaTable> = {
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

function loadSavedQueries(): SavedQuery[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistSavedQueries(queries: SavedQuery[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queries));
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === 'QuotaExceededError') {
      console.warn('localStorage quota exceeded, clearing saved queries');
      localStorage.removeItem(STORAGE_KEY);
    }
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AlaSQLDB = any;

export function useSqlEngine(marketData: MarketData | null) {
  const dbRef = useRef<AlaSQLDB>(null);
  const lastSyncRef = useRef<number>(0);
  const [isReady, setIsReady] = useState(false);
  const [tableInfo, setTableInfo] = useState<TableInfo>({});
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>(loadSavedQueries);

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
      if (!db) return;

      // GitHub repos
      try {
        const repos = await fetchGithubFinanceRepos() || [];
        db.exec('DELETE FROM github_repos');
        for (const r of repos as unknown as Array<Record<string, unknown>>) {
          db.exec('INSERT INTO github_repos VALUES (?,?,?,?,?,?)', [
            r.name, r.stars || 0, r.forks || 0, r.language || '', (String(r.description || '')).slice(0, 200), r.license || ''
          ]);
        }
      } catch { /* use mock on failure */ }

      // HuggingFace models
      try {
        const models = await fetchFinanceModels() || [];
        db.exec('DELETE FROM hf_models');
        for (const m of models as unknown as Array<Record<string, unknown>>) {
          db.exec('INSERT INTO hf_models VALUES (?,?,?,?,?)', [
            m.name, m.pipeline || '', m.downloads || 0, m.likes || 0, m.library || ''
          ]);
        }
      } catch { /* use mock on failure */ }

      // DeFi protocols
      try {
        const protos = await fetchDefiProtocols() || [];
        db.exec('DELETE FROM defi_protocols');
        for (const p of protos as unknown as Array<Record<string, unknown>>) {
          db.exec('INSERT INTO defi_protocols VALUES (?,?,?,?,?)', [
            p.name, p.symbol || '', p.tvl || 0, p.change1d || 0, p.category || ''
          ]);
        }
      } catch { /* use mock on failure */ }

      // Reddit posts
      try {
        const posts = await fetchAllFinanceSubs() || [];
        db.exec('DELETE FROM reddit_posts');
        for (const p of posts as unknown as Array<Record<string, unknown>>) {
          db.exec('INSERT INTO reddit_posts VALUES (?,?,?,?,?)', [
            (String(p.title || '')).slice(0, 200), p.subreddit || '', p.score || 0, p.numComments || 0, p.flair || ''
          ]);
        }
      } catch { /* use mock on failure */ }
    }

    loadResearchData().catch(err => {
      console.warn('[useSqlEngine] loadResearchData failed:', (err as Error).message);
    });
  }, []);

  // Helper: upsert rows by key
  const upsertTable = useCallback((db: AlaSQLDB, table: string, keyCol: string, rows: unknown[][]) => {
    for (const row of rows) {
      db.exec(`DELETE FROM ${table} WHERE ${keyCol} = ?`, [row[0]]);
      db.exec(`INSERT INTO ${table} VALUES (${row.map(() => '?').join(',')})`, row);
    }
  }, []);

  // Sync market data into SQL tables (throttled, incremental upserts)
  useEffect(() => {
    if (!marketData) return;
    const now = Date.now();
    if (now - lastSyncRef.current < THROTTLE_MS) return;
    lastSyncRef.current = now;

    const db = dbRef.current;
    if (!db) return;
    const info: TableInfo = {};

    const stocks = marketData.stocks || {};
    const stockRows = Object.entries(stocks).map(([sym, d]) => [
      sym, safeNum(d.price), safeNum(d.changePct), safeNum(d.volume),
      safeNum(d.high), safeNum(d.low), 'stock'
    ]);
    upsertTable(db, 'stocks', 'symbol', stockRows);
    info.stocks = stockRows.length;

    const crypto = marketData.crypto || {};
    const cryptoRows = Object.entries(crypto).map(([sym, d]) => [
      sym, safeNum(d.price), safeNum(d.changePct), safeNum(d.volume),
      safeNum(d.marketCap || d.market_cap), 'crypto'
    ]);
    upsertTable(db, 'crypto', 'symbol', cryptoRows);
    info.crypto = cryptoRows.length;

    const forex = marketData.forex || {};
    const forexRows = Object.entries(forex).map(([pair, d]) => {
      const rec = d as number | MarketDataRecord;
      const rate = typeof rec === 'number' ? rec : safeNum(rec.rate || rec.price);
      const chg = typeof rec === 'number' ? 0 : safeNum(rec.changePct);
      const bid = typeof rec === 'number' ? rec : safeNum(rec.bid || rec.rate || rec.price);
      const ask = typeof rec === 'number' ? rec : safeNum(rec.ask || rec.rate || rec.price);
      return [pair, rate, chg, bid, ask, 'forex'];
    });
    upsertTable(db, 'forex', 'pair', forexRows);
    info.forex = forexRows.length;

    const bonds = marketData.bonds || [];
    const bondArr = Array.isArray(bonds) ? bonds : Object.entries(bonds).map(([k, v]) => ({ maturity: k, ...(typeof v === 'number' ? { yield: v } : v as MarketDataRecord) }));
    const bondRows = bondArr.map((b: MarketDataRecord) => [
      b.maturity || b.term || '', safeNum(b.yield || b.rate), safeNum(b.change)
    ]);
    upsertTable(db, 'bonds', 'maturity', bondRows);
    info.bonds = bondRows.length;

    const commodities = marketData.commodities || {};
    const commodityRows = Object.entries(commodities).map(([name, d]) => {
      const rec = d as number | MarketDataRecord;
      const price = typeof rec === 'number' ? rec : safeNum(rec.price);
      const chg = typeof rec === 'number' ? 0 : safeNum(rec.changePct);
      const unit = typeof rec === 'object' && rec !== null ? ((rec as MarketDataRecord).unit || '') : '';
      return [name, price, chg, unit, 'commodity'];
    });
    upsertTable(db, 'commodities', 'name', commodityRows);
    info.commodities = commodityRows.length;

    const indices = marketData.indices || {};
    const indexRows = Object.entries(indices).map(([sym, d]) => [
      d.symbol || sym, d.name || sym, safeNum(d.price), safeNum(d.changePct)
    ]);
    upsertTable(db, 'indices', 'symbol', indexRows);
    info.indices = indexRows.length;

    const economic = marketData.economic || {};
    const econRows = Object.entries(economic)
      .filter(([, d]) => d && typeof d === 'object')
      .map(([key, d]) => [key, safeNum(d.value), d.unit || '', d.date || '']);
    upsertTable(db, 'economic', 'indicator', econRows);
    info.economic = econRows.length;

    db.exec('DELETE FROM all_assets');
    for (const [sym, d] of Object.entries(stocks)) {
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [
        sym, 'stock', safeNum(d.price), safeNum(d.changePct), safeNum(d.volume)
      ]);
    }
    for (const [sym, d] of Object.entries(crypto)) {
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [
        sym, 'crypto', safeNum(d.price), safeNum(d.changePct), safeNum(d.volume)
      ]);
    }
    for (const [pair, d] of Object.entries(forex)) {
      const rec = d as number | MarketDataRecord;
      const rate = typeof rec === 'number' ? rec : safeNum(rec.rate || rec.price);
      const chg = typeof rec === 'number' ? 0 : safeNum(rec.changePct);
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [pair, 'forex', rate, chg, 0]);
    }
    for (const [name, d] of Object.entries(commodities)) {
      const rec = d as number | MarketDataRecord;
      const price = typeof rec === 'number' ? rec : safeNum(rec.price);
      const chg = typeof rec === 'number' ? 0 : safeNum(rec.changePct);
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [name, 'commodity', price, chg, 0]);
    }
    for (const [sym, d] of Object.entries(indices)) {
      db.exec('INSERT INTO all_assets VALUES (?,?,?,?,?)', [
        d.symbol || sym, 'index', safeNum(d.price), safeNum(d.changePct), 0
      ]);
    }

    setTableInfo(info);
    setIsReady(true);
  }, [marketData, upsertTable]);

  const executeQuery = useCallback((sql: string): QueryResult => {
    const trimmed = sql.trim();
    if (!trimmed) return { error: 'Empty query' };

    if (BLOCKED_KEYWORDS.test(trimmed)) {
      return { error: 'Only SELECT queries are allowed' };
    }

    const start = performance.now();
    try {
      const result = dbRef.current!.exec(trimmed);
      const elapsed = performance.now() - start;
      const rows = Array.isArray(result) ? result as Record<string, unknown>[] : [];
      const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

      const entry: HistoryEntry = {
        sql: trimmed,
        rowCount: rows.length,
        elapsed: elapsed.toFixed(1),
        timestamp: Date.now(),
        error: null,
      };
      setHistory(prev => [entry, ...prev].slice(0, MAX_HISTORY));

      return { rows, columns, rowCount: rows.length, elapsed: elapsed.toFixed(1), error: null };
    } catch (err: unknown) {
      const elapsed = performance.now() - start;
      const message = err instanceof Error ? err.message : String(err);
      const entry: HistoryEntry = {
        sql: trimmed,
        rowCount: 0,
        elapsed: elapsed.toFixed(1),
        timestamp: Date.now(),
        error: message,
      };
      setHistory(prev => [entry, ...prev].slice(0, MAX_HISTORY));

      return { rows: [], columns: [], rowCount: 0, elapsed: elapsed.toFixed(1), error: message };
    }
  }, []);

  const clearHistory = useCallback(() => setHistory([]), []);
  const getSchema = useCallback(() => SCHEMA, []);

  const saveQuery = useCallback((label: string, sql: string) => {
    setSavedQueries(prev => {
      const next = [{ label, sql, timestamp: Date.now() }, ...prev.filter((q: SavedQuery) => q.sql !== sql)].slice(0, 20);
      persistSavedQueries(next);
      return next;
    });
  }, []);

  const removeSavedQuery = useCallback((sql: string) => {
    setSavedQueries(prev => {
      const next = prev.filter((q: SavedQuery) => q.sql !== sql);
      persistSavedQueries(next);
      return next;
    });
  }, []);

  const exportCsv = useCallback((columns: string[], rows: Record<string, unknown>[], filename = 'query_results.csv') => {
    if (!columns.length || !rows.length) return;
    const header = columns.join(',');
    const body = rows.map(row =>
      columns.map((col: string) => {
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

  const copyResults = useCallback((columns: string[], rows: Record<string, unknown>[]) => {
    if (!columns.length || !rows.length) return Promise.resolve(false);
    const header = columns.join('\t');
    const body = rows.map(row => columns.map((col: string) => String(row[col] ?? '')).join('\t')).join('\n');
    return navigator.clipboard.writeText(header + '\n' + body).then(() => true).catch(() => false);
  }, []);

  return {
    executeQuery, isReady, tableInfo, history, clearHistory,
    getSchema, savedQueries, saveQuery, removeSavedQuery,
    exportCsv, copyResults,
  };
}
