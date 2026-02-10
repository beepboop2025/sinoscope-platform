import { memo, type ReactElement } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface YieldDataPoint {
  maturity: string;
  yield: number;
  [key: string]: unknown;
}

interface YieldCurveProps {
  data?: YieldDataPoint[];
  height?: number;
  prevData?: YieldDataPoint[];
}

const YieldCurve = memo(({ data = [], height = 200, prevData }: YieldCurveProps): ReactElement | null => {
  if (!data.length) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />
        <XAxis dataKey="maturity" tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={{ stroke: 'var(--border-1)' }} />
        <YAxis tick={{ fontSize: 9, fill: 'var(--text-4)' }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}%`} width={40} domain={['auto', 'auto']} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontSize: 11, color: 'var(--text-1)' }}
          formatter={(v: number | string) => [`${Number(v).toFixed(3)}%`, 'Yield']}
          labelStyle={{ color: 'var(--text-3)', fontSize: 10 }}
        />
        <ReferenceLine y={0} stroke="var(--border-2)" />
        {prevData && (
          <Line type="monotone" dataKey="yield" data={prevData} stroke="var(--text-4)" strokeWidth={1} strokeDasharray="4 4" dot={false} name="Previous" />
        )}
        <Line type="monotone" dataKey="yield" stroke="var(--cyan)" strokeWidth={2} dot={{ fill: 'var(--cyan)', r: 3 }} activeDot={{ r: 5 }} name="Current" />
      </LineChart>
    </ResponsiveContainer>
  );
});
YieldCurve.displayName = 'YieldCurve';
export default YieldCurve;
