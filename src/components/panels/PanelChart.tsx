import { memo, useState, useEffect, useCallback, useRef, type ReactElement, type ChangeEvent } from 'react';
import { LineChart as LineChartIcon, RefreshCw, AlertTriangle } from 'lucide-react';
import { createChart, AreaSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import { cacheGet, cacheSet } from '../../services/CacheManager';
import { api } from '../../services/apiClient';

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

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

async function fetchChartData(symbol: string, days: number): Promise<PricePoint[] | null> {
  const cacheKey = `chart_${symbol}_${days}`;
  const cached = cacheGet(cacheKey) as PricePoint[] | undefined;
  if (cached) return cached;

  // Try backend candles first (persistent TimescaleDB data)
  try {
    const interval = days <= 1 ? '1h' : '1d';
    const limit = days <= 1 ? 24 : Math.min(days, 500);
    const result = await api.getHistoryCandles(symbol, { interval, limit }) as { data?: { bucket: string; close: number }[] };
    if (result?.data && result.data.length > 0) {
      const prices: PricePoint[] = result.data
        .sort((a, b) => new Date(a.bucket).getTime() - new Date(b.bucket).getTime())
        .map((c) => {
          const ts = new Date(c.bucket).getTime();
          return {
            time: days <= 1
              ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' }),
            close: c.close,
            timestamp: ts,
          };
        });
      cacheSet(cacheKey, prices, days <= 1 ? 60000 : 300000);
      return prices;
    }
  } catch {
    // Backend unavailable, fall through to CoinGecko
  }

  // Fall through to CoinGecko
  const cgId = COINGECKO_IDS[symbol];
  if (!cgId) return null;

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
  const [chartData, setChartData] = useState<PricePoint[]>(externalData || []);
  const [loading, setLoading] = useState<boolean>(true);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const areaSeriesRef = useRef<ISeriesApi<'Area'> | null>(null);

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

  // Create LW chart
  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    const bg = getCSSVar('--bg-1') || '#0a0f1a';
    const text = getCSSVar('--text-3') || '#64748b';
    const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';
    const crosshair = getCSSVar('--cyan') || '#06d6e0';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: { background: { color: bg }, textColor: text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
      grid: { vertLines: { color: border }, horzLines: { color: border } },
      crosshair: { mode: 0, vertLine: { color: crosshair, width: 1, style: 2 }, horzLine: { color: crosshair, width: 1, style: 2 } },
      rightPriceScale: { borderColor: border, scaleMargins: { top: 0.1, bottom: 0.05 } },
      timeScale: { borderColor: border },
    });

    const areaSeries = chart.addSeries(AreaSeries, { lineWidth: 2 });

    chartRef.current = chart;
    areaSeriesRef.current = areaSeries;

    const ro = new ResizeObserver(() => {
      if (container.clientWidth > 0 && container.clientHeight > 0) {
        chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      areaSeriesRef.current = null;
    };
  }, []);

  // Update series data and colors
  useEffect(() => {
    const series = areaSeriesRef.current;
    const chart = chartRef.current;
    if (!series || !chartData.length) return;

    const isPositive = (priceChange || 0) >= 0;
    const green = getCSSVar('--green') || '#00DC82';
    const red = getCSSVar('--red') || '#FF4458';
    const lineColor = isPositive ? green : red;

    series.applyOptions({
      lineColor,
      topColor: lineColor + '40',
      bottomColor: lineColor + '05',
    });

    const lwData = chartData.map((d, i) => ({
      time: i as UTCTimestamp,
      value: d.close,
    }));
    series.setData(lwData);
    chart?.timeScale().fitContent();
  }, [chartData, priceChange]);

  const isPositive = (priceChange || 0) >= 0;
  const strokeColor = isPositive ? 'var(--green)' : 'var(--red)';

  return (
    <PanelChrome title={`${symbol} Price Chart`} icon={LineChartIcon} iconColor="var(--cyan)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={symbol}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => setSymbol(e.target.value)}
            aria-label="Select cryptocurrency symbol"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border-1)', borderRadius: 4, color: 'var(--text-1)', fontSize: 10, padding: '2px 4px', fontFamily: 'var(--font-mono)' }}
          >
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {RANGES.map(r => (
            <button key={r.label} className="btn-ghost" onClick={() => setRange(r)}
              style={{ fontSize: 9, padding: '1px 5px', color: range.label === r.label ? 'var(--cyan)' : 'var(--text-3)', borderBottom: range.label === r.label ? '1px solid var(--cyan)' : 'none' }}>
              {r.label}
            </button>
          ))}

          <button className="btn-ghost" onClick={loadData} aria-label="Refresh chart data" style={{ fontSize: 9, padding: '1px 4px', marginLeft: 'auto' }}>
            <RefreshCw size={10} aria-hidden="true" />
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

        <div ref={chartContainerRef} role="img" aria-label={`${symbol} price chart for the last ${range.label}`} style={{ flex: 1, minHeight: 120 }}>
          {error && chartData.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8, color: 'var(--text-3)' }}>
              <AlertTriangle size={20} color="var(--amber)" />
              <span style={{ fontSize: 11, textAlign: 'center', maxWidth: 200 }}>{error}</span>
              <button className="btn-ghost" onClick={loadData} style={{ fontSize: 10, padding: '3px 10px', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <RefreshCw size={10} /> Retry
              </button>
            </div>
          ) : loading && chartData.length === 0 ? <PanelSkeleton /> : null}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelChart.displayName = "PanelChart";
export default PanelChart;
