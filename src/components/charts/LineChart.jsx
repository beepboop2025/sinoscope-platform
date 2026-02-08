import { memo } from 'react';
import { LineChart as RLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { CHART_COLORS } from '../../constants/colors';

const LineChartComponent = memo(({ data = [], series = [], height = 250, showGrid = true, showLegend = false, xKey = 'time', yDomain, formatY }) => {
  if (!data.length) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RLineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />}
        <XAxis dataKey={xKey} tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={{ stroke: 'var(--border-1)' }} />
        <YAxis domain={yDomain || ['auto', 'auto']} tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={false} tickFormatter={formatY} width={50} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 11, color: 'var(--text-1)' }}
          labelStyle={{ color: 'var(--text-3)', fontSize: 10 }}
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
      </RLineChart>
    </ResponsiveContainer>
  );
});
LineChartComponent.displayName = 'LineChartComponent';
export default LineChartComponent;
