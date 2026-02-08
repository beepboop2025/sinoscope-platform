import { memo } from 'react';
import { LineChart as RLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Brush } from 'recharts';
import { CHART_COLORS } from '../../constants/colors';

const LineChartComponent = memo(({ data = [], series = [], height = 250, showGrid = true, showLegend = false, xKey = 'time', yDomain, formatY, showBrush = false }) => {
  if (!data.length) return null;

  const tooltipFormatter = (value, name) => {
    if (typeof value !== 'number') return [value, name];
    if (formatY) return [formatY(value), name];
    return [value.toLocaleString(undefined, { maximumFractionDigits: 4 }), name];
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RLineChart data={data} margin={{ top: 4, right: 8, bottom: showBrush ? 2 : 4, left: 0 }}>
        {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />}
        <XAxis dataKey={xKey} tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={{ stroke: 'var(--border-1)' }} />
        <YAxis domain={yDomain || ['auto', 'auto']} tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={false} tickFormatter={formatY} width={50} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 11, color: 'var(--text-1)' }}
          labelStyle={{ color: 'var(--text-3)', fontSize: 10 }}
          cursor={{ stroke: 'var(--text-3)', strokeDasharray: '3 3' }}
          formatter={tooltipFormatter}
        />
        {showLegend && <Legend wrapperStyle={{ fontSize: 10, color: 'var(--text-3)' }} />}
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name || s.key}
            stroke={s.color || CHART_COLORS[i % CHART_COLORS.length]}
            strokeWidth={s.width || 1.5}
            dot={false}
            activeDot={{ r: 3 }}
          />
        ))}
        {showBrush && data.length > 10 && (
          <Brush
            dataKey={xKey}
            height={18}
            stroke="var(--border-2)"
            fill="var(--bg-2)"
            travellerWidth={8}
            tickFormatter={() => ''}
          />
        )}
      </RLineChart>
    </ResponsiveContainer>
  );
});
LineChartComponent.displayName = 'LineChartComponent';
export default LineChartComponent;
