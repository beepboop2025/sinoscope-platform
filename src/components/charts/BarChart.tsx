import { memo, type ReactElement } from 'react';
import { BarChart as RBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell, Brush } from 'recharts';
import { CHART_COLORS } from '../../constants/colors';

interface BarConfig {
  key: string;
  name?: string;
  color?: string;
}

interface BarChartProps {
  data?: Record<string, unknown>[];
  bars?: BarConfig[];
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  xKey?: string;
  colorByValue?: boolean;
  formatY?: (value: number) => string;
  showBrush?: boolean;
}

const BarChartComponent = memo(({ data = [], bars = [], height = 250, showGrid = true, showLegend = false, xKey = 'name', colorByValue = false, formatY, showBrush = false }: BarChartProps): ReactElement | null => {
  if (!data.length) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart data={data} margin={{ top: 4, right: 8, bottom: showBrush ? 2 : 4, left: 0 }}>
        {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />}
        <XAxis dataKey={xKey} tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={{ stroke: 'var(--border-1)' }} />
        <YAxis tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={false} tickFormatter={formatY} width={50} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 11, color: 'var(--text-1)' }}
          labelStyle={{ color: 'var(--text-3)', fontSize: 10 }}
          cursor={{ fill: 'var(--bg-3)', opacity: 0.3 }}
        />
        {showLegend && <Legend wrapperStyle={{ fontSize: 10, color: 'var(--text-3)' }} />}
        {bars.map((b, i) => (
          <Bar key={b.key} dataKey={b.key} name={b.name || b.key} fill={b.color || CHART_COLORS[i % CHART_COLORS.length]} radius={[2, 2, 0, 0]}>
            {colorByValue && data.map((entry, idx) => (
              <Cell key={idx} fill={(entry[b.key] as number) >= 0 ? 'var(--green)' : 'var(--red)'} />
            ))}
          </Bar>
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
      </RBarChart>
    </ResponsiveContainer>
  );
});
BarChartComponent.displayName = 'BarChartComponent';
export default BarChartComponent;
