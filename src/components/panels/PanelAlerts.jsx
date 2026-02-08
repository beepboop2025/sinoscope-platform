import { memo, useState } from 'react';
import { Bell, AlertTriangle, TrendingUp, Volume2 } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';

const SEVERITY_COLORS = { critical: 'var(--red)', high: 'var(--orange)', medium: 'var(--amber)', low: 'var(--text-3)' };
const TYPE_ICONS = { price_spike: TrendingUp, volume_spike: Volume2, anomaly: AlertTriangle, default: Bell };

const PanelAlerts = memo(({ alerts = [] }) => {
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all' ? alerts : alerts.filter(a => a.severity === filter);

  return (
    <PanelChrome title="Alerts" icon={Bell} iconColor="var(--amber)">
      <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
        {['all', 'critical', 'high', 'medium'].map(f => (
          <button key={f} className={`tab-btn ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)} style={{ padding: '2px 8px', fontSize: 10, textTransform: 'capitalize' }}>
            {f}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {filtered.length === 0 && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
            No alerts. Market patterns will generate alerts automatically.
          </div>
        )}
        {filtered.map((a, i) => {
          const Icon = TYPE_ICONS[a.type] || TYPE_ICONS.default;
          const color = SEVERITY_COLORS[a.severity] || 'var(--text-3)';
          return (
            <div key={i} style={{ display: 'flex', gap: 8, padding: '6px 8px', background: 'var(--bg-1)', borderRadius: 6, border: '1px solid var(--border-1)', borderLeft: `3px solid ${color}` }}>
              <Icon size={14} color={color} style={{ flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: 'var(--text-1)' }}>{a.message}</div>
                <div style={{ fontSize: 9, color: 'var(--text-4)', marginTop: 2 }}>
                  {a.symbol} {new Date(a.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </PanelChrome>
  );
});
PanelAlerts.displayName = "PanelAlerts";
export default PanelAlerts;
