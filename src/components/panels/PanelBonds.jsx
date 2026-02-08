import { memo } from 'react';
import { Landmark } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

const PanelBonds = memo(({ data }) => {
  if (!data || data.length === 0) {
    return <PanelChrome title="US Treasury Yields" icon={Landmark} iconColor="var(--purple)"><PanelSkeleton /></PanelChrome>;
  }

  return (
    <PanelChrome title="US Treasury Yields" icon={Landmark} iconColor="var(--purple)">
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {data.map(d => (
          <div key={d.maturity} style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '6px 10px', border: '1px solid var(--border-1)', minWidth: 60, textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase' }}>{d.maturity}</div>
            <div className="mono" style={{ fontSize: 14, fontWeight: 600, color: 'var(--purple)' }}>
              {(Number(d.yield) || 0).toFixed(2)}%
            </div>
          </div>
        ))}
      </div>
      <div style={{ height: 160 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="maturity" tick={{ fontSize: 10, fill: '#64748b' }} />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ background: '#0f1628', border: '1px solid #243356', borderRadius: 6, fontSize: 11 }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Line type="monotone" dataKey="yield" stroke="#a78bfa" strokeWidth={2} dot={{ r: 3, fill: '#a78bfa' }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </PanelChrome>
  );
});
PanelBonds.displayName = "PanelBonds";
export default PanelBonds;
