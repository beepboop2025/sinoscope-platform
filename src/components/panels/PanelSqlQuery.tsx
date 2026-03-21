import { memo, useState, useCallback, useRef, useMemo, useDeferredValue, type ReactElement, type KeyboardEvent, type ChangeEvent } from 'react';
import { Database, Play, Trash2, ChevronDown, ChevronUp, Clock, Download, Copy, Star, BookOpen, ArrowUpDown, ArrowUp, ArrowDown, Check, X, Save, FileSpreadsheet } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import VirtualTable, { type VirtualTableColumn } from '../shared/VirtualTable';
import { useSqlEngine } from '../../hooks/useSqlEngine';
import { exportToXlsx } from '../../utils/excelExport';

/** Threshold: use VirtualTable when result set exceeds this row count */
const VIRTUAL_TABLE_THRESHOLD = 100;

interface QueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  elapsed: string | undefined;
  error?: string;
}

interface HistoryEntry {
  sql: string;
  rowCount: number;
  elapsed: string;
  error?: string;
}

interface SavedQuery {
  label: string;
  sql: string;
}

interface SchemaTable {
  columns: string[];
}

interface SortIconProps {
  col: string;
  sortCol: string | null;
  sortDir: string;
}

interface SchemaDrawerProps {
  schema: Record<string, SchemaTable>;
  onInsert: (sql: string) => void;
}

interface SaveQueryDialogProps {
  sql: string;
  onSave: (label: string, sql: string) => void;
  onCancel: () => void;
}

const PRESETS = [
  { label: 'Top Gainers', sql: 'SELECT symbol, asset_type, price, changePct FROM all_assets WHERE changePct > 0 ORDER BY changePct DESC LIMIT 10' },
  { label: 'Top Losers', sql: 'SELECT symbol, asset_type, price, changePct FROM all_assets WHERE changePct < 0 ORDER BY changePct ASC LIMIT 10' },
  { label: 'Market Summary', sql: 'SELECT asset_type, COUNT(*) as count, ROUND(AVG(changePct),2) as avgChg, ROUND(SUM(volume),0) as totalVol FROM all_assets GROUP BY asset_type' },
  { label: 'Global Indices', sql: 'SELECT symbol, name, price, changePct FROM indices ORDER BY price DESC' },
  { label: 'Economic Data', sql: 'SELECT indicator, value, unit, date FROM economic ORDER BY indicator' },
  { label: 'Crypto > $1K', sql: 'SELECT symbol, price, changePct, volume FROM crypto WHERE price > 1000 ORDER BY price DESC' },
  { label: 'Yield Curve', sql: 'SELECT maturity, yield, change FROM bonds ORDER BY yield ASC' },
  { label: 'Forex Spreads', sql: 'SELECT pair, rate, bid, ask, ROUND(ask - bid, 4) as spread FROM forex ORDER BY spread DESC' },
  { label: 'All Stocks', sql: 'SELECT symbol, price, changePct, volume, high, low FROM stocks ORDER BY symbol' },
  { label: 'High Volume', sql: 'SELECT symbol, asset_type, price, volume FROM all_assets WHERE volume > 0 ORDER BY volume DESC LIMIT 10' },
  { label: 'Volatile Assets', sql: 'SELECT symbol, asset_type, price, changePct FROM all_assets WHERE ABS(changePct) > 2 ORDER BY ABS(changePct) DESC' },
  { label: 'Crypto vs Stocks', sql: "SELECT asset_type, COUNT(*) as cnt, ROUND(AVG(price),2) as avgPrice, ROUND(AVG(changePct),2) as avgChg FROM all_assets WHERE asset_type IN ('stock','crypto') GROUP BY asset_type" },
  { label: 'GitHub Top Repos', sql: 'SELECT name, stars, forks, language FROM github_repos ORDER BY stars DESC LIMIT 15' },
  { label: 'HF Models', sql: 'SELECT name, pipeline, downloads, likes FROM hf_models ORDER BY downloads DESC LIMIT 15' },
  { label: 'Python Finance', sql: "SELECT name, stars, forks FROM github_repos WHERE language = 'Python' ORDER BY stars DESC LIMIT 10" },
  { label: 'DeFi Top TVL', sql: 'SELECT name, symbol, tvl, change1d, category FROM defi_protocols ORDER BY tvl DESC LIMIT 15' },
  { label: 'Reddit Hot', sql: 'SELECT title, subreddit, score, comments FROM reddit_posts ORDER BY score DESC LIMIT 15' },
  { label: 'DeFi by Category', sql: 'SELECT category, COUNT(*) as cnt, ROUND(SUM(tvl),0) as totalTvl FROM defi_protocols GROUP BY category ORDER BY totalTvl DESC' },
];

const SortIcon = ({ col, sortCol, sortDir }: SortIconProps): ReactElement => {
  if (sortCol !== col) return <ArrowUpDown size={9} style={{ opacity: 0.3 }} />;
  return sortDir === 'asc' ? <ArrowUp size={9} /> : <ArrowDown size={9} />;
};

const SchemaDrawer = ({ schema, onInsert }: SchemaDrawerProps): ReactElement => (
  <div style={{ fontSize: 10, maxHeight: 160, overflow: 'auto', padding: '4px 0' }}>
    {Object.entries(schema).map(([table, def]) => (
      <div key={table} style={{ marginBottom: 6 }}>
        <div
          style={{ color: 'var(--purple)', fontWeight: 600, cursor: 'pointer', fontFamily: 'JetBrains Mono, monospace' }}
          onClick={() => onInsert(`SELECT * FROM ${table} LIMIT 10`)}
          title={`Click to query ${table}`}
        >
          {table}
        </div>
        <div style={{ paddingLeft: 10, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
          {def.columns.map(c => {
            const [name, type] = c.split(' ');
            return (
              <div key={name} style={{ display: 'flex', gap: 6 }}>
                <span style={{ color: 'var(--text-2)' }}>{name}</span>
                <span style={{ color: 'var(--text-4)', fontSize: 9 }}>{type}</span>
              </div>
            );
          })}
        </div>
      </div>
    ))}
  </div>
);

const SaveQueryDialog = ({ sql, onSave, onCancel }: SaveQueryDialogProps): ReactElement => {
  const [label, setLabel] = useState<string>('');
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', padding: '4px 0' }}>
      <input
        autoFocus
        value={label}
        onChange={(e: ChangeEvent<HTMLInputElement>) => setLabel(e.target.value)}
        onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Enter' && label.trim()) onSave(label.trim(), sql); if (e.key === 'Escape') onCancel(); }}
        placeholder="Query name..."
        style={{
          flex: 1, fontSize: 10, padding: '2px 6px', background: 'var(--bg-0)',
          color: 'var(--text-1)', border: '1px solid var(--border-2)', borderRadius: 3,
          fontFamily: 'JetBrains Mono, monospace', outline: 'none',
        }}
      />
      <button className="btn-ghost" onClick={() => label.trim() && onSave(label.trim(), sql)} style={{ padding: '2px 6px', fontSize: 9 }}>
        <Check size={10} />
      </button>
      <button className="btn-ghost" onClick={onCancel} style={{ padding: '2px 6px', fontSize: 9 }}>
        <X size={10} />
      </button>
    </div>
  );
};

const PanelSqlQuery = memo(({ data }: { data?: unknown }): ReactElement => {
  const {
    executeQuery, isReady, tableInfo, history, clearHistory,
    getSchema, savedQueries, saveQuery, removeSavedQuery,
    exportCsv, copyResults,
  } = useSqlEngine(data as Record<string, unknown> | null);

  const [sql, setSql] = useState<string>('SELECT * FROM all_assets ORDER BY changePct DESC LIMIT 10');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [showHistory, setShowHistory] = useState<boolean>(false);
  const [showSchema, setShowSchema] = useState<boolean>(false);
  const [showSaved, setShowSaved] = useState<boolean>(false);
  const [showSaveDialog, setShowSaveDialog] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<string>('asc');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const schema = useMemo(() => getSchema() as Record<string, SchemaTable>, [getSchema]);

  const runQuery = useCallback((query?: string) => {
    const q = query || sql;
    if (!q.trim()) return;
    const res = executeQuery(q) as QueryResult;
    setResult(res);
    setSortCol(null);
    setSortDir('asc');
    if (query) setSql(query);
  }, [sql, executeQuery]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runQuery();
    }
  }, [runQuery]);

  const handleSort = useCallback((col: string) => {
    setSortCol(prev => {
      if (prev === col) {
        setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        return col;
      }
      setSortDir('asc');
      return col;
    });
  }, []);

  const sortedRows = useMemo(() => {
    if (!result?.rows?.length || !sortCol) return result?.rows || [];
    return [...result.rows].sort((a, b) => {
      const va = a[sortCol], vb = b[sortCol];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'number' && typeof vb === 'number') return sortDir === 'asc' ? va - vb : vb - va;
      return sortDir === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    });
  }, [result, sortCol, sortDir]);

  const handleCopy = useCallback(async () => {
    if (!result?.columns?.length) return;
    try {
      const ok = await copyResults(result.columns, sortedRows);
      if (ok) { setCopied(true); setTimeout(() => setCopied(false), 1500); }
    } catch (err) {
      console.warn('[PanelSqlQuery] copy failed:', (err as Error).message);
    }
  }, [result, sortedRows, copyResults]);

  const handleExport = useCallback(() => {
    if (!result?.columns?.length) return;
    exportCsv(result.columns, sortedRows);
  }, [result, sortedRows, exportCsv]);

  const handleSaveQuery = useCallback((label: string, querySql: string) => {
    saveQuery(label, querySql);
    setShowSaveDialog(false);
  }, [saveQuery]);

  const tableBadges = Object.entries(tableInfo as Record<string, number>);

  return (
    <PanelChrome title="SQL Query" icon={Database} iconColor="var(--purple)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Table info badges + schema toggle */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', padding: '2px 0', alignItems: 'center' }}>
          {tableBadges.map(([name, count]) => (
            <span key={name} className="badge" style={{ background: 'var(--bg-3)', color: 'var(--purple)', fontSize: 9, padding: '1px 6px' }}>
              {name}: {count}
            </span>
          ))}
          {!isReady && <span style={{ fontSize: 10, color: 'var(--text-4)' }}>Waiting for data...</span>}
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 2 }}>
            <button
              className="btn-ghost"
              onClick={() => { setShowSchema(v => !v); setShowSaved(false); }}
              style={{ padding: '1px 5px', fontSize: 9, color: showSchema ? 'var(--purple)' : undefined }}
              title="Schema browser"
            >
              <BookOpen size={10} />
            </button>
            <button
              className="btn-ghost"
              onClick={() => { setShowSaved(v => !v); setShowSchema(false); }}
              style={{ padding: '1px 5px', fontSize: 9, color: showSaved ? 'var(--yellow)' : undefined }}
              title="Saved queries"
            >
              <Star size={10} />
            </button>
          </span>
        </div>

        {/* Schema browser */}
        {showSchema && (
          <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 4, padding: '4px 8px' }}>
            <SchemaDrawer schema={schema} onInsert={(q) => { setSql(q); setShowSchema(false); }} />
          </div>
        )}

        {/* Saved queries */}
        {showSaved && (
          <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 4, padding: '4px 8px', maxHeight: 120, overflow: 'auto' }}>
            {(savedQueries as SavedQuery[]).length === 0 ? (
              <div style={{ fontSize: 10, color: 'var(--text-4)', padding: 4 }}>No saved queries yet</div>
            ) : (savedQueries as SavedQuery[]).map((q, i) => (
              <div key={i} style={{
                display: 'flex', gap: 6, alignItems: 'center', padding: '3px 2px',
                borderBottom: '1px solid var(--border-1)', fontSize: 10,
              }}>
                <Star size={9} style={{ color: 'var(--yellow)', flexShrink: 0 }} />
                <span
                  onClick={() => { runQuery(q.sql); setShowSaved(false); }}
                  style={{ cursor: 'pointer', color: 'var(--text-2)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  title={q.sql}
                >
                  {q.label}
                </span>
                <button
                  className="btn-ghost"
                  onClick={() => removeSavedQuery(q.sql)}
                  style={{ padding: '1px 3px', fontSize: 9, color: 'var(--text-4)' }}
                >
                  <X size={9} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* SQL textarea */}
        <textarea
          ref={textareaRef}
          value={sql}
          onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          placeholder="SELECT * FROM stocks ORDER BY changePct DESC"
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
            background: 'var(--bg-0)',
            color: 'var(--text-1)',
            border: '1px solid var(--border-2)',
            borderRadius: 4,
            padding: '6px 8px',
            resize: 'vertical',
            minHeight: 48,
            maxHeight: 120,
            outline: 'none',
            width: '100%',
            boxSizing: 'border-box',
          }}
        />

        {/* Save query dialog */}
        {showSaveDialog && (
          <SaveQueryDialog sql={sql} onSave={handleSaveQuery} onCancel={() => setShowSaveDialog(false)} />
        )}

        {/* Action row: Run + Presets + Tools */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            className="btn-primary"
            onClick={() => runQuery()}
            disabled={!isReady}
            style={{ padding: '3px 10px', fontSize: 10, display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <Play size={10} /> Run
          </button>
          <button
            className="btn-ghost"
            onClick={() => setShowSaveDialog(true)}
            style={{ padding: '2px 7px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}
            title="Save query"
          >
            <Save size={9} /> Save
          </button>
          {result && !result.error && result.rows.length > 0 && (
            <>
              <button
                className="btn-ghost"
                onClick={handleExport}
                style={{ padding: '2px 7px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}
                title="Export CSV"
              >
                <Download size={9} /> CSV
              </button>
              <button
                className="btn-ghost"
                onClick={() => exportToXlsx('Query Results', result.columns, sortedRows)}
                style={{ padding: '2px 7px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}
                title="Export XLSX"
              >
                <FileSpreadsheet size={9} /> XLSX
              </button>
              <button
                className="btn-ghost"
                onClick={handleCopy}
                style={{ padding: '2px 7px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}
                title="Copy to clipboard"
              >
                {copied ? <Check size={9} /> : <Copy size={9} />} {copied ? 'Copied!' : 'Copy'}
              </button>
            </>
          )}
          <div style={{ width: '100%', display: 'flex', gap: 3, flexWrap: 'wrap', marginTop: 1 }}>
            {PRESETS.map(p => (
              <button
                key={p.label}
                className="btn-ghost"
                onClick={() => runQuery(p.sql)}
                style={{ padding: '2px 7px', fontSize: 9 }}
              >
                {p.label}
              </button>
            ))}
          </div>
          <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--text-4)' }}>
            {navigator.platform?.includes('Mac') ? '\u2318' : 'Ctrl'}+Enter to run
          </span>
        </div>

        {/* Status bar */}
        {result && (
          <div style={{
            display: 'flex', gap: 8, alignItems: 'center', fontSize: 10, padding: '2px 4px',
            color: result.error ? 'var(--red)' : 'var(--green)',
          }}>
            {result.error ? (
              <span>Error: {result.error}</span>
            ) : (
              <>
                <span>{result.rowCount} row{result.rowCount !== 1 ? 's' : ''}</span>
                <span style={{ color: 'var(--text-4)' }}>in {result.elapsed}ms</span>
                {sortCol && <span style={{ color: 'var(--text-4)' }}>sorted by {sortCol} {sortDir}</span>}
              </>
            )}
          </div>
        )}

        {/* Results table — uses VirtualTable for large result sets */}
        {result && !result.error && result.rows.length > 0 && (() => {
          const useVirtual = sortedRows.length > VIRTUAL_TABLE_THRESHOLD;

          if (useVirtual) {
            const vtCols: VirtualTableColumn<Record<string, unknown>>[] = result.columns.map(col => ({
              key: col,
              label: col,
              style: { textAlign: typeof result.rows[0][col] === 'number' ? 'right' as const : 'left' as const },
              cellStyle: { textAlign: typeof result.rows[0][col] === 'number' ? 'right' as const : 'left' as const },
              render: (val: unknown) => {
                const isNum = typeof val === 'number';
                const isChangePct = col === 'changePct' || col === 'change' || col === 'avgChg';
                if (isNum) {
                  const styled = isChangePct
                    ? `${(Number(val) || 0).toFixed(2)}%`
                    : Number.isInteger(val as number) ? (val as number).toLocaleString() : (Number(val) || 0).toFixed(2);
                  return <span style={{ color: isChangePct ? ((val as number) > 0 ? 'var(--green)' : (val as number) < 0 ? 'var(--red)' : undefined) : undefined }}>{styled}</span>;
                }
                return String(val ?? '');
              },
            }));
            return (
              <div style={{ flex: 1, minHeight: 0 }}>
                <VirtualTable columns={vtCols} rows={sortedRows} rowHeight={26} containerHeight={300} />
              </div>
            );
          }

          return (
            <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              <table className="dense-table">
                <thead>
                  <tr>
                    {result.columns.map(col => (
                      <th
                        key={col}
                        onClick={() => handleSort(col)}
                        style={{
                          textAlign: typeof result.rows[0][col] === 'number' ? 'right' : 'left',
                          cursor: 'pointer',
                          userSelect: 'none',
                        }}
                        title={`Sort by ${col}`}
                      >
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                          {col}
                          <SortIcon col={col} sortCol={sortCol} sortDir={sortDir} />
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row, i) => (
                    <tr key={i}>
                      {result.columns.map(col => {
                        const val = row[col];
                        const isNum = typeof val === 'number';
                        const isChangePct = col === 'changePct' || col === 'change' || col === 'avgChg';
                        return (
                          <td
                            key={col}
                            style={{
                              textAlign: isNum ? 'right' : 'left',
                              color: isChangePct ? ((val as number) > 0 ? 'var(--green)' : (val as number) < 0 ? 'var(--red)' : undefined) : undefined,
                            }}
                          >
                            {isNum
                              ? (isChangePct ? `${(Number(val) || 0).toFixed(2)}%` : Number.isInteger(val as number) ? (val as number).toLocaleString() : (Number(val) || 0).toFixed(2))
                              : String(val ?? '')}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })()}

        {result && !result.error && result.rows.length === 0 && (
          <div style={{ padding: 12, color: 'var(--text-4)', fontSize: 11, textAlign: 'center' }}>
            No rows returned
          </div>
        )}

        {/* History drawer */}
        <div style={{ borderTop: '1px solid var(--border-1)', marginTop: 'auto' }}>
          <button
            onClick={() => setShowHistory(!showHistory)}
            style={{
              background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, padding: '4px 0', width: '100%',
            }}
          >
            <Clock size={10} />
            History ({(history as HistoryEntry[]).length})
            {showHistory ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            {(history as HistoryEntry[]).length > 0 && (
              <span
                onClick={(e: React.MouseEvent) => { e.stopPropagation(); clearHistory(); }}
                style={{ marginLeft: 'auto', color: 'var(--text-4)', display: 'flex', alignItems: 'center', gap: 2 }}
              >
                <Trash2 size={9} /> Clear
              </span>
            )}
          </button>
          {showHistory && (history as HistoryEntry[]).length > 0 && (
            <div style={{ maxHeight: 100, overflow: 'auto' }}>
              {(history as HistoryEntry[]).map((h, i) => (
                <div
                  key={i}
                  onClick={() => runQuery(h.sql)}
                  style={{
                    padding: '3px 6px', cursor: 'pointer', fontSize: 10,
                    fontFamily: 'JetBrains Mono, monospace',
                    borderBottom: '1px solid var(--border-1)',
                    color: h.error ? 'var(--red-dim)' : 'var(--text-2)',
                    display: 'flex', gap: 8, alignItems: 'center',
                  }}
                >
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.sql}</span>
                  <span style={{ color: 'var(--text-4)', flexShrink: 0 }}>
                    {h.rowCount}r · {h.elapsed}ms
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelSqlQuery.displayName = 'PanelSqlQuery';
export default PanelSqlQuery;
