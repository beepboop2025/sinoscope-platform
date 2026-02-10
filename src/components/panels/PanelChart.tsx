import { memo, useState, useEffect, useCallback, type ReactElement, type ChangeEvent } from 'react';
import { LineChart as LineChartIcon, RefreshCw, AlertTriangle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, Area, AreaChart } from 'recharts';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import { cacheGet, cacheSet } from '../../services/CacheManager';

interface PricePoint {
  time: string;
  close: number;
  timestamp: number;
}

interface Range {
  label: string;
  days: number;
}

const COINGECKO_IDS: Record<string, string> = {
  BTC: 'bitcoin', ETH: 'ethereum', SOL: 'solana', BNB: 'binancecoin',
  ADA: 'cardano', DOGE: 'dogecoin', XRP: 'ripple', DOT: 'polkadot',
  AVAX: 'avalanche-2', MATIC: 'matic-network',
};

const SYMBOLS = Object.keys(COINGECKO_IDS);
const RANGES: Range[] = [
  { label: '1D', days: 1 },
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '1Y', days: 365 },
];

async function fetchChartData(symbol: string, days: number): Promise<PricePoint[] | null> {
  const cgId = COINGECKO_IDS[symbol];
  if (!cgId) return null;

  const cacheKey = `chart_${cgId}_${days}`;
  const cached = cacheGet(cacheKey) as PricePoint[] | undefined;
  if (cached) return cached;

  try {
    const url = `https://api.coingecko.com/api/v3/coins/${cgId}/market_chart?vs_currency=usd&days=${days}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();

    const prices: PricePoint[] = ((data.prices || []) as [number, number][]).map(([ts, price]) => ({
      time: days <= 1
        ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' }),
      close: price,
      timestamp: ts,
    }));

    const maxPoints = 120;
    const step = Math.max(1, Math.floor(prices.length / maxPoints));
    const sampled = prices.filter((_, i) => i % step === 0);

    cacheSet(cacheKey, sampled, days <= 1 ? 60000 : 300000);
    return sampled;
  } catch (err: unknown) {
    console.warn('[PanelChart]', (err as Error).message);
    return null;
  }
}

interface PanelChartProps {
  symbol?: string;
  data?: PricePoint[];
}

const PanelChart = memo(({ symbol: initialSymbol = 'BTC', data: externalData }: PanelChartProps): ReactElement => {
  const [symbol, setSymbol] = useState<string>(initialSymbol);
  const [range, setRange] = useState<Range>(RANGES[2]);
  const [chartType, setChartType] = useState<'area' | 'line'>('area');
  const [chartData, setChartData] = useState<PricePoint[]>(externalData || []);
  const [loading, setLoading] = useState<boolean>(true);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchChartData(symbol, range.days);
      if (data && data.length > 0) {
        setChartData(data);
        const first = data[0].close;
        const last = data[data.length - 1].close;
        setCurrentPrice(last);
        setPriceChange(first > 0 ? ((last - first) / first) * 100 : 0);
      }
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to load chart data');
    }
    setLoading(false);
  }, [symbol, range]);

  useEffect(() => { loadData(); }, [loadData]);

  const isPositive = (priceChange || 0) >= 0;
  const strokeColor = isPositive ? 'var(--green)' : 'var(--red)';

  return (
    <PanelChrome title={`${symbol} Price Chart`} icon={LineChartIcon} iconColor="var(--cyan)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={symbol}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => setSymbol(e.target.value)}
            style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 4, color: 'var(--text-1)', fontSize: 10, padding: '2px 4px', fontFamily: 'var(--font-mono)' }}
          >
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {RANGES.map(r => (
            <button key={r.label} className="btn-ghost" onClick={() => setRange(r)}
              style={{ fontSize: 9, padding: '1px 5px', color: range.label === r.label ? 'var(--cyan)' : 'var(--text-3)', borderBottom: range.label === r.label ? '1px solid var(--cyan)' : 'none' }}>
              {r.label}
            </button>
          ))}

          {(['area', 'line'] as const).map(t => (
            <button key={t} className="btn-ghost" onClick={() => setChartType(t)}
              style={{ fontSize: 9, padding: '1px 5px', marginLeft: t === 'area' ? 'auto' : 0, color: chartType === t ? 'var(--text-1)' : 'var(--text-3)' }}>
              {t.toUpperCase()}
            </button>
          ))}

          <button className="btn-ghost" onClick={loadData} style={{ fontSize: 9, padding: '1px 4px' }}>
            <RefreshCw size={10} />
          </button>
        </div>

        {currentPrice != null && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>
              ${currentPrice >= 1 ? currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : currentPrice.toFixed(6)}
            </span>
            {priceChange != null && (
              <span style={{ fontSize: 11, color: strokeColor, fontWeight: 600 }}>
                {isPositive ? '+' : ''}{priceChange.toFixed(2)}%
              </span>
            )}
            <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{range.label}</span>
          </div>
        )}

        <div style={{ flex: 1, minHeight: 120 }}>
          {error && chartData.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8, color: 'var(--text-3)' }}>
              <AlertTriangle size={20} color="var(--amber)" />
              <span style={{ fontSize: 11, textAlign: 'center', maxWidth: 200 }}>{error}</span>
              <button className="btn-ghost" onClick={loadData} style={{ fontSize: 10, padding: '3px 10px', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <RefreshCw size={10} /> Retry
              </button>
            </div>
          ) : loading && chartData.length === 0 ? <PanelSkeleton /> : (
            <ResponsiveContainer width="100%" height="100%">
              {chartType === 'area' ? (
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={strokeColor} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={strokeColor} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" tick={{ fontSize: 8, fill: 'var(--text-3)' }} tickCount={6} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 8, fill: 'var(--text-3)' }} domain={['auto', 'auto']} width={55}
                    tickFormatter={(v: number) => v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(2)}`} />
                  <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 10 }}
                    formatter={(v: number) => [`$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, 'Price']} />
                  <Area type="monotone" dataKey="close" stroke={strokeColor} fill="url(#chartGrad)" strokeWidth={1.5} dot={false} />
                </AreaChart>
              ) : (
                <LineChart data={chartData}>
                  <XAxis dataKey="time" tick={{ fontSize: 8, fill: 'var(--text-3)' }} tickCount={6} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 8, fill: 'var(--text-3)' }} domain={['auto', 'auto']} width={55}
                    tickFormatter={(v: number) => v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(2)}`} />
                  <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 10 }}
                    formatter={(v: number) => [`$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, 'Price']} />
                  <Line type="monotone" dataKey="close" stroke={strokeColor} strokeWidth={1.5} dot={false} />
                </LineChart>
              )}
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelChart.displayName = "PanelChart";
export default PanelChart;
