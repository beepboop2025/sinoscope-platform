import { memo, type ReactElement } from 'react';
import { Calendar, AlertCircle, TrendingUp, Globe } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';

interface TypeConfig {
  icon: LucideIcon;
  color: string;
}

const TYPE_CONFIG: Record<string, TypeConfig> = {
  price_alert: { icon: TrendingUp, color: 'var(--amber)' },
  anomaly: { icon: AlertCircle, color: 'var(--red)' },
  earnings: { icon: Calendar, color: 'var(--blue)' },
  economic: { icon: Globe, color: 'var(--teal)' },
  geopolitical: { icon: Globe, color: 'var(--orange)' },
};

interface TimelineEvent {
  id?: string;
  type: string;
  message?: string;
  title?: string;
  symbol?: string;
  timestamp: number;
}

interface PanelTimelineProps {
  events?: TimelineEvent[];
}

const PanelTimeline = memo(({ events = [] }: PanelTimelineProps): ReactElement => {
  if (events.length === 0) {
    return (
      <PanelChrome title="Event Timeline" icon={Calendar} iconColor="var(--teal)">
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
          No events recorded yet. Events will appear as market data flows.
        </div>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="Event Timeline" icon={Calendar} iconColor="var(--teal)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {events.slice(0, 20).map((evt, i) => {
          const cfg = TYPE_CONFIG[evt.type] || TYPE_CONFIG.economic;
          const Icon = cfg.icon;
          return (
            <div key={evt.id || i} style={{ display: 'flex', gap: 8, padding: '6px 8px', background: 'var(--bg-1)', borderRadius: 6, border: '1px solid var(--border-1)', alignItems: 'flex-start' }}>
              <Icon size={14} color={cfg.color} style={{ flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: 'var(--text-1)' }}>{evt.message || evt.title}</div>
                <div style={{ fontSize: 9, color: 'var(--text-4)', marginTop: 2 }}>
                  {evt.symbol && <span style={{ marginRight: 8 }}>{evt.symbol}</span>}
                  {new Date(evt.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </PanelChrome>
  );
});
PanelTimeline.displayName = "PanelTimeline";
export default PanelTimeline;
