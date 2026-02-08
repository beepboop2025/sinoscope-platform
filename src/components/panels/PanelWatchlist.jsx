import { memo, useState, useCallback, useEffect, useRef } from 'react';
import { Eye, Plus, X, TrendingUp, TrendingDown } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { debounce } from '../../utils/helpers';

const STORAGE_KEY = 'dragonscope_watchlist';
const DEFAULT_WATCHLIST = ['AAPL', 'BTC', 'ETH', 'NVDA', 'MSFT', 'SOL', 'USD/JPY', 'GOLD'];

function loadWatchlist() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : DEFAULT_WATCHLIST;
  } catch {
    return DEFAULT_WATCHLIST;
  }
}

function saveWatchlist(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch (e) {
    if (e?.name === 'QuotaExceededError') {
      localStorage.removeItem(STORAGE_KEY);
    }
  }
}

const PanelWatchlist = memo(({ data }) => {
  const [watchlist, setWatchlist] = useState(loadWatchlist);
  const [showAdd, setShowAdd] = useState(false);
  const [addInput, setAddInput] = useState('');

  // Debounced localStorage save (300ms)
  const debouncedSaveRef = useRef(debounce(saveWatchlist, 300));
  useEffect(() => { debouncedSaveRef.current(watchlist); }, [watchlist]);

  const addSymbol = useCallback((sym) => {
    const s = sym.trim().toUpperCase();
    if (s && !watchlist.includes(s)) {
      setWatchlist(prev => [...prev, s]);
    }
    setAddInput('');
    setShowAdd(false);
  }, [watchlist]);

  const removeSymbol = useCallback((sym) => {
    setWatchlist(prev => prev.filter(s => s !== sym));
  }, []);

  // Look up price data for each symbol across all data categories
  const getSymbolData = useCallback((sym) => {
    if (!data) return null;

    // Check stocks
    if (data.stocks?.[sym]) {
      const d = data.stocks[sym];
      return { price: d.price, changePct: d.changePct, type: 'stock' };
    }
    // Check crypto
    if (data.crypto?.[sym]) {
      const d = data.crypto[sym];
      return { price: d.price, changePct: d.changePct, type: 'crypto' };
    }
    // Check forex
    if (data.forex?.[sym]) {
      const d = data.forex[sym];
      const price = typeof d === 'number' ? d : d.rate || d.price || 0;
      const chg = typeof d === 'number' ? 0 : d.changePct || 0;
      return { price, changePct: chg, type: 'forex' };
    }
    // Check indices
    if (data.indices?.[sym]) {
      const d = data.indices[sym];
      return { price: d.price, changePct: d.changePct, type: 'index' };
    }
    // Check commodities
    if (data.commodities?.[sym]) {
      const d = data.commodities[sym];
      const price = typeof d === 'number' ? d : d.price || 0;
      const chg = typeof d === 'number' ? 0 : d.changePct || 0;
      return { price, changePct: chg, type: 'commodity' };
    }
    return null;
  }, [data]);

  const TYPE_COLORS = {
    stock: 'var(--blue)',
    crypto: 'var(--orange)',
    forex: 'var(--cyan)',
    index: 'var(--green)',
    commodity: 'var(--amber)',
  };

  return (
    <PanelChrome title="Watchlist" icon={Eye} iconColor="var(--cyan)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, height: '100%', minHeight: 0 }}>
        {/* Header with add button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 9, color: 'var(--text-4)' }}>{watchlist.length} symbols</span>
          <button
            className="btn-ghost"
            onClick={() => setShowAdd(!showAdd)}
            style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 2 }}
          >
            <Plus size={9} /> Add
          </button>
        </div>

        {/* Add symbol input */}
        {showAdd && (
          <div style={{ display: 'flex', gap: 3 }}>
            <input
              autoFocus
              value={addInput}
              onChange={e => setAddInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') addSymbol(addInput); if (e.key === 'Escape') setShowAdd(false); }}
              placeholder="Symbol (e.g. AAPL, BTC)"
              style={{
                flex: 1, fontSize: 10, padding: '3px 6px', background: 'var(--bg-0)',
                color: 'var(--text-1)', border: '1px solid var(--border-2)', borderRadius: 3,
                fontFamily: 'JetBrains Mono, monospace', outline: 'none',
              }}
            />
            <button className="btn-primary" onClick={() => addSymbol(addInput)} style={{ padding: '2px 8px', fontSize: 9 }}>Add</button>
          </div>
        )}

        {/* Watchlist items */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {watchlist.map(sym => {
            const d = getSymbolData(sym);
            const price = d ? Number(d.price) || 0 : 0;
            const chg = d ? Number(d.changePct) || 0 : 0;
            const isUp = chg > 0;

            return (
              <div key={sym} style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '5px 4px',
                borderBottom: '1px solid var(--border-1)',
              }}>
                {d ? (
                  isUp ? <TrendingUp size={11} style={{ color: 'var(--green)', flexShrink: 0 }} />
                       : <TrendingDown size={11} style={{ color: 'var(--red)', flexShrink: 0 }} />
                ) : (
                  <span style={{ width: 11, height: 11, flexShrink: 0 }} />
                )}

                <span style={{ fontSize: 11, fontWeight: 600, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-1)', minWidth: 50 }}>
                  {sym}
                </span>

                {d && (
                  <span className="badge" style={{ background: 'var(--bg-3)', color: TYPE_COLORS[d.type] || 'var(--text-3)', fontSize: 8, padding: '1px 4px' }}>
                    {d.type}
                  </span>
                )}

                <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-1)' }}>
                  {d ? (price >= 1 ? price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : price.toFixed(4)) : '\u2014'}
                </span>

                <span style={{
                  fontSize: 10, fontFamily: 'JetBrains Mono, monospace', minWidth: 55, textAlign: 'right',
                  color: chg > 0 ? 'var(--green)' : chg < 0 ? 'var(--red)' : 'var(--text-4)',
                }}>
                  {d ? `${chg > 0 ? '+' : ''}${chg.toFixed(2)}%` : ''}
                </span>

                <button
                  onClick={() => removeSymbol(sym)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-4)', cursor: 'pointer', padding: 2, flexShrink: 0 }}
                  title="Remove"
                >
                  <X size={10} />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelWatchlist.displayName = 'PanelWatchlist';
export default PanelWatchlist;
