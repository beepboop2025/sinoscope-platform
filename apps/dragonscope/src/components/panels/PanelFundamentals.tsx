import { memo, useState, useEffect, type ReactElement } from 'react';
import { FileBarChart, TrendingUp, TrendingDown } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FundamentalsData {
  symbol: string;
  name: string;
  sector: string;
  marketCap: number;
  pe: number;
  forwardPe: number;
  eps: number;
  dividendYield: number;
  beta: number;
  high52w: number;
  low52w: number;
  avgVolume: number;
  revenue: number;
  revenueGrowth: number;
  profitMargin: number;
  debtToEquity: number;
  roe: number;
  currentRatio: number;
}

// ---------------------------------------------------------------------------
// Mock data generator
// ---------------------------------------------------------------------------

const STOCK_PROFILES: Record<string, { name: string; sector: string }> = {
  AAPL: { name: 'Apple Inc.', sector: 'Technology' },
  MSFT: { name: 'Microsoft Corp.', sector: 'Technology' },
  GOOGL: { name: 'Alphabet Inc.', sector: 'Technology' },
  AMZN: { name: 'Amazon.com Inc.', sector: 'Consumer Cyclical' },
  NVDA: { name: 'NVIDIA Corp.', sector: 'Technology' },
  TSLA: { name: 'Tesla Inc.', sector: 'Consumer Cyclical' },
  META: { name: 'Meta Platforms', sector: 'Technology' },
  JPM: { name: 'JPMorgan Chase', sector: 'Financial Services' },
  V: { name: 'Visa Inc.', sector: 'Financial Services' },
  JNJ: { name: 'Johnson & Johnson', sector: 'Healthcare' },
};

function generateMockFundamentals(symbol: string): FundamentalsData {
  const profile = STOCK_PROFILES[symbol] || { name: symbol, sector: 'Unknown' };
  const basePrice = 100 + Math.random() * 400;
  return {
    symbol,
    name: profile.name,
    sector: profile.sector,
    marketCap: +(Math.random() * 3000 + 100).toFixed(1) * 1e9,
    pe: +(Math.random() * 40 + 8).toFixed(2),
    forwardPe: +(Math.random() * 35 + 6).toFixed(2),
    eps: +(Math.random() * 15 + 1).toFixed(2),
    dividendYield: +(Math.random() * 4).toFixed(2),
    beta: +(Math.random() * 1.5 + 0.3).toFixed(2),
    high52w: +(basePrice * (1 + Math.random() * 0.3)).toFixed(2),
    low52w: +(basePrice * (1 - Math.random() * 0.3)).toFixed(2),
    avgVolume: Math.round(Math.random() * 50_000_000 + 1_000_000),
    revenue: +(Math.random() * 400 + 10).toFixed(1) * 1e9,
    revenueGrowth: +(Math.random() * 40 - 10).toFixed(1),
    profitMargin: +(Math.random() * 35 + 2).toFixed(1),
    debtToEquity: +(Math.random() * 200).toFixed(1),
    roe: +(Math.random() * 40 + 5).toFixed(1),
    currentRatio: +(Math.random() * 3 + 0.5).toFixed(2),
  };
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function fmtMcap(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toFixed(0)}`;
}

function fmtVol(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return String(n);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SYMBOLS = Object.keys(STOCK_PROFILES);

function PanelFundamentals(): ReactElement {
  const [data, setData] = useState<FundamentalsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [symbolIdx, setSymbolIdx] = useState(0);

  const currentSymbol = SYMBOLS[symbolIdx] || 'AAPL';

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      setData(generateMockFundamentals(currentSymbol));
      setLoading(false);
    }, 600);
    return () => clearTimeout(timer);
  }, [currentSymbol]);

  if (loading || !data) {
    return (
      <PanelChrome title="Fundamentals" icon={FileBarChart}>
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  const MetricRow = ({ label, value, suffix = '', highlight }: { label: string; value: string | number; suffix?: string; highlight?: 'up' | 'down' | null }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ color: 'var(--text-3)', fontSize: 11 }}>{label}</span>
      <span style={{
        fontSize: 12, fontFamily: 'var(--font-mono)',
        color: highlight === 'up' ? 'var(--green)' : highlight === 'down' ? 'var(--red)' : 'var(--text-1)',
      }}>
        {value}{suffix}
      </span>
    </div>
  );

  return (
    <PanelChrome title="Fundamentals" icon={FileBarChart} subtitle={data.symbol}>
      <div style={{ padding: '8px 12px', overflowY: 'auto', height: '100%' }}>
        {/* Symbol Selector */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 10 }}>
          {SYMBOLS.map((s, i) => (
            <button
              key={s}
              onClick={() => setSymbolIdx(i)}
              style={{
                padding: '2px 6px', fontSize: 10, borderRadius: 4, cursor: 'pointer',
                background: i === symbolIdx ? 'var(--accent-blue)' : 'rgba(255,255,255,0.06)',
                color: i === symbolIdx ? '#fff' : 'var(--text-3)',
                border: 'none',
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Company header */}
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>{data.name}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>{data.sector}</div>
        </div>

        {/* Valuation */}
        <div style={{ fontSize: 10, color: 'var(--accent-blue)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Valuation</div>
        <MetricRow label="Market Cap" value={fmtMcap(data.marketCap)} />
        <MetricRow label="P/E Ratio" value={data.pe} />
        <MetricRow label="Forward P/E" value={data.forwardPe} />
        <MetricRow label="EPS" value={`$${data.eps}`} />
        <MetricRow label="Dividend Yield" value={data.dividendYield} suffix="%" />
        <MetricRow label="Beta" value={data.beta} />

        {/* Trading */}
        <div style={{ fontSize: 10, color: 'var(--accent-blue)', fontWeight: 600, marginTop: 10, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Trading</div>
        <MetricRow label="52W High" value={`$${data.high52w}`} />
        <MetricRow label="52W Low" value={`$${data.low52w}`} />
        <MetricRow label="Avg Volume" value={fmtVol(data.avgVolume)} />

        {/* Financial Health */}
        <div style={{ fontSize: 10, color: 'var(--accent-blue)', fontWeight: 600, marginTop: 10, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Financial Health</div>
        <MetricRow label="Revenue" value={fmtMcap(data.revenue)} />
        <MetricRow label="Revenue Growth" value={data.revenueGrowth} suffix="%" highlight={data.revenueGrowth > 0 ? 'up' : data.revenueGrowth < 0 ? 'down' : null} />
        <MetricRow label="Profit Margin" value={data.profitMargin} suffix="%" highlight={data.profitMargin > 15 ? 'up' : data.profitMargin < 5 ? 'down' : null} />
        <MetricRow label="Debt/Equity" value={data.debtToEquity} />
        <MetricRow label="ROE" value={data.roe} suffix="%" highlight={data.roe > 20 ? 'up' : data.roe < 8 ? 'down' : null} />
        <MetricRow label="Current Ratio" value={data.currentRatio} />
      </div>
    </PanelChrome>
  );
}

export default memo(PanelFundamentals);
