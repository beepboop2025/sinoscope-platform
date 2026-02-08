import { memo, useState } from 'react';
import { LineChart as LineChartIcon } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, Area, AreaChart } from 'recharts';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

const PanelChart = memo(({ symbol = 'BTC', data = [] }) => {
  const [chartType, setChartType] = useState('area');

  if (data.length === 0) {
    return (
      <PanelChrome title={`${symbol} Chart`} icon={LineChartIcon} iconColor="var(--cyan)">
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title={`${symbol} Price Chart`} icon={LineChartIcon} iconColor="var(--cyan)">
      <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
        {['area', 'line'].map(t => (
          <button
            key={t}
            className={`tab-btn ${chartType === t ? 'active' : ''}`}
            onClick={() => setChartType(t)}
            style={{ padding: '2px 8px', fontSize: 10 }}
          >
            {t.toUpperCase()}
          </button>
        ))}
      </div>
      <div style={{ height: '100%', minHeight: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          {chartType === 'area' ? (
            <AreaChart data={data}>
              <defs>
                <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06d6e0" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06d6e0" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 9, fill: '#64748b' }} domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ background: '#0f1628', border: '1px solid #243356', borderRadius: 6, fontSize: 11 }} />
              <Area type="monotone" dataKey="close" stroke="#06d6e0" fill="url(#chartGradient)" strokeWidth={2} />
            </AreaChart>
          ) : (
            <LineChart data={data}>
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 9, fill: '#64748b' }} domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ background: '#0f1628', border: '1px solid #243356', borderRadius: 6, fontSize: 11 }} />
              <Line type="monotone" dataKey="close" stroke="#06d6e0" strokeWidth={2} dot={false} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </PanelChrome>
  );
});
PanelChart.displayName = "PanelChart";
export default PanelChart;
