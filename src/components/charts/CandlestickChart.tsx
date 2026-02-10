import { memo, type ReactElement } from 'react';
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts';

interface OverlayDefault {
  color: string;
  width: number;
  dash: string;
}

const OVERLAY_DEFAULTS: OverlayDefault[] = [
  { color: '#f59e0b', width: 1.2, dash: '0' },
  { color: '#a78bfa', width: 1.2, dash: '0' },
  { color: '#3b82f6', width: 1, dash: '4 2' },
  { color: '#ec4899', width: 1, dash: '4 2' },
  { color: '#14b8a6', width: 1, dash: '6 3' },
];

interface CandlestickDataPoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  [key: string]: unknown;
}

interface OverlayConfig {
  key: string;
  name?: string;
  color?: string;
  width?: number;
  dash?: string;
}

interface CandlestickChartProps {
  data?: CandlestickDataPoint[];
  height?: number;
  overlays?: OverlayConfig[];
}

const CandlestickChart = memo(({ data = [], height = 300, overlays = [] }: CandlestickChartProps): ReactElement | null => {
  if (!data.length) return null;

  const processedData = data.map(d => ({
    ...d,
    bodyLow: Math.min(d.open, d.close),
    bodyHeight: Math.abs(d.close - d.open) || 0.01,
    isUp: d.close >= d.open,
  }));

  const hasOverlays = overlays.length > 0;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={processedData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />
        <XAxis dataKey="time" tick={{ fontSize: 8, fill: 'var(--text-4)' }} tickLine={false} axisLine={{ stroke: 'var(--border-1)' }} />
        <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={false} width={55} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 11, color: 'var(--text-1)' }}
          labelStyle={{ color: 'var(--text-3)', fontSize: 10 }}
          formatter={(v: number | string, name: string) => {
            if (name === 'bodyHeight' || name === 'bodyLow') return null;
            return [typeof v === 'number' ? v.toFixed(4) : v, name];
          }}
        />
        {hasOverlays && <Legend wrapperStyle={{ fontSize: 10, color: 'var(--text-3)' }} />}
        {/* Wicks as thin bars */}
        <Bar dataKey="high" stackId="wick" fill="none" barSize={1} legendType="none">
          {processedData.map((d, i) => (
            <Cell key={i} fill={d.isUp ? 'var(--green)' : 'var(--red)'} />
          ))}
        </Bar>
        {/* Candle bodies */}
        <Bar dataKey="bodyHeight" stackId="body" barSize={6} legendType="none">
          {processedData.map((d, i) => (
            <Cell key={i} fill={d.isUp ? 'var(--green)' : 'var(--red)'} />
          ))}
        </Bar>
        {/* Overlay lines (SMA, EMA, Bollinger, etc.) */}
        {overlays.map((o, i) => {
          const defaults = OVERLAY_DEFAULTS[i % OVERLAY_DEFAULTS.length];
          return (
            <Line
              key={o.key}
              type="monotone"
              dataKey={o.key}
              stroke={o.color || defaults.color}
              strokeWidth={o.width || defaults.width}
              strokeDasharray={o.dash || defaults.dash}
              dot={false}
              name={o.name || o.key}
              connectNulls
              isAnimationActive={false}
            />
          );
        })}
      </ComposedChart>
    </ResponsiveContainer>
  );
});
CandlestickChart.displayName = 'CandlestickChart';
export default CandlestickChart;
