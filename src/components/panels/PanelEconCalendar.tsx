import { memo, useState, useEffect, type ReactElement } from 'react';
import { CalendarClock, AlertTriangle, Clock } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EconEvent {
  id: string;
  time: string;
  country: string;
  event: string;
  impact: 'high' | 'medium' | 'low';
  actual?: string;
  forecast?: string;
  previous?: string;
  isPast: boolean;
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const COUNTRIES = ['US', 'EU', 'GB', 'JP', 'CN', 'DE', 'AU', 'CA'];
const COUNTRY_FLAGS: Record<string, string> = {
  US: '\u{1F1FA}\u{1F1F8}', EU: '\u{1F1EA}\u{1F1FA}', GB: '\u{1F1EC}\u{1F1E7}',
  JP: '\u{1F1EF}\u{1F1F5}', CN: '\u{1F1E8}\u{1F1F3}', DE: '\u{1F1E9}\u{1F1EA}',
  AU: '\u{1F1E6}\u{1F1FA}', CA: '\u{1F1E8}\u{1F1E6}',
};

const EVENT_NAMES: Record<string, string[]> = {
  US: ['Non-Farm Payrolls', 'CPI YoY', 'FOMC Interest Rate Decision', 'GDP QoQ', 'Retail Sales MoM', 'ISM Manufacturing PMI', 'Initial Jobless Claims'],
  EU: ['ECB Interest Rate Decision', 'CPI YoY', 'GDP QoQ', 'PMI Manufacturing', 'Unemployment Rate'],
  GB: ['BoE Interest Rate Decision', 'CPI YoY', 'GDP MoM', 'Retail Sales MoM'],
  JP: ['BoJ Interest Rate Decision', 'CPI YoY', 'GDP QoQ', 'Tankan Index'],
  CN: ['PBoC Interest Rate', 'CPI YoY', 'GDP YoY', 'Manufacturing PMI', 'Trade Balance'],
  DE: ['Ifo Business Climate', 'ZEW Economic Sentiment', 'Industrial Production'],
  AU: ['RBA Interest Rate Decision', 'Employment Change', 'CPI QoQ'],
  CA: ['BoC Interest Rate Decision', 'CPI MoM', 'Employment Change'],
};

function generateMockEvents(): EconEvent[] {
  const events: EconEvent[] = [];
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  for (let dayOff = -1; dayOff <= 5; dayOff++) {
    const day = new Date(today.getTime() + dayOff * 86_400_000);
    const numEvents = 2 + Math.floor(Math.random() * 4);

    for (let j = 0; j < numEvents; j++) {
      const country = COUNTRIES[Math.floor(Math.random() * COUNTRIES.length)];
      const names = EVENT_NAMES[country] || EVENT_NAMES.US;
      const name = names[Math.floor(Math.random() * names.length)];
      const hour = 7 + Math.floor(Math.random() * 10);
      const minute = Math.random() > 0.5 ? 30 : 0;
      const eventTime = new Date(day);
      eventTime.setHours(hour, minute, 0);
      const isPast = eventTime.getTime() < now.getTime();

      const impacts: Array<'high' | 'medium' | 'low'> = ['high', 'medium', 'low'];
      const impact = impacts[Math.floor(Math.random() * impacts.length)];

      const base = +(Math.random() * 5 - 1).toFixed(1);
      events.push({
        id: `${dayOff}-${j}`,
        time: eventTime.toISOString(),
        country,
        event: name,
        impact,
        actual: isPast ? `${base}%` : undefined,
        forecast: `${(base + (Math.random() - 0.5) * 0.4).toFixed(1)}%`,
        previous: `${(base + (Math.random() - 0.5) * 0.6).toFixed(1)}%`,
        isPast,
      });
    }
  }

  events.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
  return events;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const IMPACT_COLORS: Record<string, string> = {
  high: 'var(--red)',
  medium: 'var(--yellow)',
  low: 'var(--text-3)',
};

function formatEventTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatEventDate(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
  return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

function getCountdown(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return '';
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  if (h > 24) return `${Math.floor(h / 24)}d`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function PanelEconCalendar(): ReactElement {
  const [events, setEvents] = useState<EconEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium'>('all');

  useEffect(() => {
    const timer = setTimeout(() => {
      setEvents(generateMockEvents());
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <PanelChrome title="Economic Calendar" icon={CalendarClock}>
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  const filtered = filter === 'all' ? events : events.filter(e => e.impact === filter || (filter === 'high' && e.impact === 'high'));

  // Group by date
  const grouped: Record<string, EconEvent[]> = {};
  for (const ev of filtered) {
    const dateKey = formatEventDate(ev.time);
    if (!grouped[dateKey]) grouped[dateKey] = [];
    grouped[dateKey].push(ev);
  }

  return (
    <PanelChrome title="Economic Calendar" icon={CalendarClock} subtitle={`${filtered.length} events`}>
      <div style={{ padding: '8px 12px', overflowY: 'auto', height: '100%' }}>
        {/* Filters */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
          {(['all', 'high', 'medium'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '2px 8px', fontSize: 10, borderRadius: 4, cursor: 'pointer', border: 'none',
                background: filter === f ? 'var(--accent-blue)' : 'rgba(255,255,255,0.06)',
                color: filter === f ? '#fff' : 'var(--text-3)',
                textTransform: 'capitalize',
              }}
            >
              {f === 'all' ? 'All' : `${f} impact`}
            </button>
          ))}
        </div>

        {/* Events grouped by date */}
        {Object.entries(grouped).map(([date, evts]) => (
          <div key={date} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: 'var(--accent-blue)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              {date}
            </div>
            {evts.map(ev => {
              const countdown = getCountdown(ev.time);
              return (
                <div
                  key={ev.id}
                  style={{
                    display: 'grid', gridTemplateColumns: '44px 20px 1fr auto',
                    gap: 6, alignItems: 'center', padding: '5px 0',
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    opacity: ev.isPast ? 0.5 : 1,
                  }}
                >
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                    {formatEventTime(ev.time)}
                  </span>
                  <span style={{ fontSize: 12 }}>{COUNTRY_FLAGS[ev.country] || ev.country}</span>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-1)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      {ev.event}
                      {ev.impact === 'high' && <AlertTriangle size={10} style={{ color: IMPACT_COLORS.high }} />}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', display: 'flex', gap: 8, marginTop: 1 }}>
                      {ev.actual && <span>A: <span style={{ color: 'var(--text-1)' }}>{ev.actual}</span></span>}
                      {ev.forecast && <span>F: {ev.forecast}</span>}
                      {ev.previous && <span>P: {ev.previous}</span>}
                    </div>
                  </div>
                  {countdown && (
                    <span style={{ fontSize: 9, color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Clock size={8} /> {countdown}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </PanelChrome>
  );
}

export default memo(PanelEconCalendar);
