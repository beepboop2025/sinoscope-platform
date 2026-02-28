import { memo, useState, useEffect, useMemo, type ReactElement } from 'react';
import { Filter, ArrowUpDown, TrendingUp, TrendingDown } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScreenerRow {
  symbol: string;
  name: string;
  type: 'stock' | 'crypto' | 'forex';
  price: number;
  change24h: number;
  volume: number;
  marketCap: number;
  pe?: number;
}

type SortField = 'symbol' | 'price' | 'change24h' | 'volume' | 'marketCap';
type SortDir = 'asc' | 'desc';

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const ASSETS: Array<{ symbol: string; name: string; type: 'stock' | 'crypto' | 'forex' }> = [
  { symbol: 'AAPL', name: 'Apple', type: 'stock' },
  { symbol: 'MSFT', name: 'Microsoft', type: 'stock' },
  { symbol: 'GOOGL', name: 'Alphabet', type: 'stock' },
  { symbol: 'AMZN', name: 'Amazon', type: 'stock' },
  { symbol: 'NVDA', name: 'NVIDIA', type: 'stock' },
  { symbol: 'TSLA', name: 'Tesla', type: 'stock' },
  { symbol: 'META', name: 'Meta', type: 'stock' },
  { symbol: 'JPM', name: 'JPMorgan', type: 'stock' },
  { symbol: 'BTC', name: 'Bitcoin', type: 'crypto' },
  { symbol: 'ETH', name: 'Ethereum', type: 'crypto' },
  { symbol: 'SOL', name: 'Solana', type: 'crypto' },
  { symbol: 'ADA', name: 'Cardano', type: 'crypto' },
  { symbol: 'DOGE', name: 'Dogecoin', type: 'crypto' },
  { symbol: 'XRP', name: 'Ripple', type: 'crypto' },
  { symbol: 'EUR/USD', name: 'Euro/Dollar', type: 'forex' },
  { symbol: 'GBP/USD', name: 'Pound/Dollar', type: 'forex' },
  { symbol: 'USD/JPY', name: 'Dollar/Yen', type: 'forex' },
  { symbol: 'USD/CNY', name: 'Dollar/Yuan', type: 'forex' },
  { symbol: 'AUD/USD', name: 'Aussie/Dollar', type: 'forex' },
  { symbol: 'USD/INR', name: 'Dollar/Rupee', type: 'forex' },
];

function generateMockRows(): ScreenerRow[] {
  return ASSETS.map(a => {
    const isForex = a.type === 'forex';
    const isCrypto = a.type === 'crypto';
    const basePrice = isForex ? 0.5 + Math.random() * 150 : isCrypto ? Math.random() * 70000 + 0.1 : 50 + Math.random() * 500;
    return {
      symbol: a.symbol,
      name: a.name,
      type: a.type,
      price: +basePrice.toFixed(isForex ? 4 : 2),
      change24h: +(Math.random() * 10 - 5).toFixed(2),
      volume: Math.round(Math.random() * 1e9 + 1e6),
      marketCap: isForex ? 0 : Math.round(Math.random() * 3e12 + 1e8),
      pe: a.type === 'stock' ? +(Math.random() * 50 + 5).toFixed(1) : undefined,
    };
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtNum(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function PanelScreener(): ReactElement {
  const [rows, setRows] = useState<ScreenerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<'all' | 'stock' | 'crypto' | 'forex'>('all');
  const [sortField, setSortField] = useState<SortField>('marketCap');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setRows(generateMockRows());
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const filtered = useMemo(() => {
    let result = rows;
    if (typeFilter !== 'all') result = result.filter(r => r.type === typeFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(r => r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q));
    }
    result = [...result].sort((a, b) => {
      const av = a[sortField] ?? 0;
      const bv = b[sortField] ?? 0;
      if (typeof av === 'string' && typeof bv === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === 'asc' ? (Number(av) || 0) - (Number(bv) || 0) : (Number(bv) || 0) - (Number(av) || 0);
    });
    return result;
  }, [rows, typeFilter, sortField, sortDir, search]);

  if (loading) {
    return (
      <PanelChrome title="Screener" icon={<Filter size={14} />}>
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  const TYPE_COLORS: Record<string, string> = { stock: 'var(--accent-blue)', crypto: 'var(--accent-purple)', forex: 'var(--yellow)' };

  const ColHeader = ({ field, label, align = 'right' }: { field: SortField; label: string; align?: string }) => (
    <th
      onClick={() => handleSort(field)}
      style={{
        padding: '4px 6px', fontSize: 9, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase',
        letterSpacing: '0.5px', cursor: 'pointer', userSelect: 'none', textAlign: align as 'left' | 'right',
        borderBottom: '1px solid rgba(255,255,255,0.08)', whiteSpace: 'nowrap',
      }}
    >
      {label} {sortField === field && (sortDir === 'asc' ? '\u2191' : '\u2193')}
    </th>
  );

  return (
    <PanelChrome title="Screener" icon={<Filter size={14} />} subtitle={`${filtered.length} assets`}>
      <div style={{ padding: '8px 12px', overflowY: 'auto', height: '100%' }}>
        {/* Controls */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {(['all', 'stock', 'crypto', 'forex'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              style={{
                padding: '2px 8px', fontSize: 10, borderRadius: 4, cursor: 'pointer', border: 'none',
                background: typeFilter === t ? 'var(--accent-blue)' : 'rgba(255,255,255,0.06)',
                color: typeFilter === t ? '#fff' : 'var(--text-3)', textTransform: 'capitalize',
              }}
            >
              {t}
            </button>
          ))}
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search..."
            style={{
              marginLeft: 'auto', padding: '3px 8px', fontSize: 10, borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.04)', color: 'var(--text-1)', outline: 'none', width: 100,
            }}
          />
        </div>

        {/* Table */}
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <ColHeader field="symbol" label="Symbol" align="left" />
              <ColHeader field="price" label="Price" />
              <ColHeader field="change24h" label="24h %" />
              <ColHeader field="volume" label="Volume" />
              <ColHeader field="marketCap" label="Mkt Cap" />
            </tr>
          </thead>
          <tbody>
            {filtered.map(row => (
              <tr key={row.symbol} style={{ cursor: 'pointer' }}>
                <td style={{ padding: '4px 6px', textAlign: 'left' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 4, height: 4, borderRadius: '50%', background: TYPE_COLORS[row.type], display: 'inline-block' }} />
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-1)' }}>{row.symbol}</span>
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-3)', marginLeft: 8 }}>{row.name}</div>
                </td>
                <td style={{ padding: '4px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-1)' }}>
                  {row.type === 'forex' ? row.price.toFixed(4) : row.price < 1 ? row.price.toFixed(4) : row.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
                <td style={{
                  padding: '4px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11,
                  color: row.change24h > 0 ? 'var(--green)' : row.change24h < 0 ? 'var(--red)' : 'var(--text-3)',
                }}>
                  {row.change24h > 0 ? '+' : ''}{row.change24h}%
                </td>
                <td style={{ padding: '4px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)' }}>
                  {fmtNum(row.volume)}
                </td>
                <td style={{ padding: '4px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)' }}>
                  {row.marketCap > 0 ? fmtNum(row.marketCap) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PanelChrome>
  );
}

export default memo(PanelScreener);
