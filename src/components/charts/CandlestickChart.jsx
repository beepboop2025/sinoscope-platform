import { memo } from 'react';
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const CandlestickChart = memo(({ data = [], height = 300, overlays = [] }) => {
  if (!data.length) return null;

  const processedData = data.map(d => ({
    ...d,
    bodyLow: Math.min(d.open, d.close),
    bodyHeight: Math.abs(d.close - d.open) || 0.01,
    isUp: d.close >= d.open,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={processedData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />
        <XAxis dataKey="time" tick={{ fontSize: 8, fill: 'var(--text-4)' }} tickLine={false} axisLine={{ stroke: 'var(--border-1)' }} />
        <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={false} width={55} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 11, color: 'var(--text-1)' }}
          labelStyle={{ color: 'var(--text-3)', fontSize: 10 }}
          formatter={(v, name) => [typeof v === 'number' ? v.toFixed(4) : v, name]}
        />
        {/* Wicks as thin bars */}
        <Bar dataKey="high" stackId="wick" fill="none" barSize={1}>
          {processedData.map((d, i) => (
            <Cell key={i} fill={d.isUp ? 'var(--green)' : 'var(--red)'} />
          ))}
        </Bar>
        {/* Candle bodies */}
        <Bar dataKey="bodyHeight" stackId="body" barSize={6}>
          {processedData.map((d, i) => (
            <Cell key={i} fill={d.isUp ? 'var(--green)' : 'var(--red)'} />
          ))}
        </Bar>
        {/* Overlay lines (SMA, EMA, Bollinger) */}
        {overlays.map(o => (
          <Line key={o.key} type="monotone" dataKey={o.key} stroke={o.color} strokeWidth={1} dot={false} name={o.name || o.key} />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
});
CandlestickChart.displayName = 'CandlestickChart';
export default CandlestickChart;
