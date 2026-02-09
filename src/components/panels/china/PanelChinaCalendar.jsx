/**
 * PanelChinaCalendar - China Economic Data Release Calendar
 * Shows upcoming and recent economic indicators from NBS China
 * NOTE: Calendar events are illustrative sample data, not live feeds.
 */
import { useState, useMemo } from 'react';
import { Calendar, Clock, AlertCircle, TrendingUp, TrendingDown, Minus, Bell, Info } from 'lucide-react';
import { CHINA_CALENDAR } from '../../../constants/china';
import PanelChrome from '../../shared/PanelChrome';

// Generate illustrative calendar events using fixed offsets from today
// These use realistic indicator names and typical values but are NOT sourced from a live feed.
const generateCalendarEvents = () => {
  const events = [];
  const today = new Date();

  // Fixed day-of-month offsets for deterministic scheduling (no Math.random for dates)
  const eventTemplates = [
    { indicator: 'PMI Manufacturing', type: 'pmi', importance: 'High', forecast: 49.8, previous: 49.0, dayOffset: -10 },
    { indicator: 'Trade Balance', type: 'trade', importance: 'High', forecast: 75.2, previous: 70.8, dayOffset: -7 },
    { indicator: 'CPI', type: 'inflation', importance: 'High', forecast: 0.3, previous: 0.2, dayOffset: -4 },
    { indicator: 'PPI', type: 'inflation', importance: 'Medium', forecast: -2.5, previous: -2.7, dayOffset: -1 },
    { indicator: 'New Yuan Loans', type: 'credit', importance: 'High', forecast: 1200, previous: 1100, dayOffset: 2 },
    { indicator: 'FX Reserves', type: 'reserves', importance: 'Medium', forecast: 32300, previous: 32258, dayOffset: 5 },
    { indicator: 'Industrial Production', type: 'production', importance: 'High', forecast: 5.2, previous: 5.0, dayOffset: 8 },
    { indicator: 'Retail Sales', type: 'consumption', importance: 'Medium', forecast: 7.5, previous: 7.2, dayOffset: 11 },
    { indicator: 'GDP', type: 'growth', importance: 'High', forecast: 5.2, previous: 5.3, dayOffset: 17 },
    { indicator: 'LPR', type: 'rates', importance: 'High', forecast: 3.45, previous: 3.45, dayOffset: 20 },
  ];

  // Distribute events across dates using fixed offsets
  eventTemplates.forEach((template) => {
    const date = new Date(today);
    date.setDate(today.getDate() + template.dayOffset);

    // Determine status
    let status = 'upcoming';
    let actual = null;
    if (date < today) {
      status = 'released';
      // Use a deterministic "actual" near forecast (based on previous value direction)
      actual = template.forecast + (template.forecast - template.previous) * 0.3;
    } else if (date.toDateString() === today.toDateString()) {
      status = 'today';
    }

    events.push({
      ...template,
      date: date.toISOString().split('T')[0],
      displayDate: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      status,
      actual,
      surprise: actual ? actual - template.forecast : null,
    });
  });

  return events.sort((a, b) => new Date(a.date) - new Date(b.date));
};

const CALENDAR_EVENTS = generateCalendarEvents();

export default function PanelChinaCalendar() {
  const [filter, setFilter] = useState('all'); // 'all' | 'upcoming' | 'high'
  const [alerts, setAlerts] = useState(new Set());

  const filteredEvents = useMemo(() => {
    let events = CALENDAR_EVENTS;
    if (filter === 'upcoming') {
      events = events.filter(e => e.status === 'upcoming' || e.status === 'today');
    } else if (filter === 'high') {
      events = events.filter(e => e.importance === 'High');
    }
    return events;
  }, [filter]);

  const toggleAlert = (indicator) => {
    const newAlerts = new Set(alerts);
    if (newAlerts.has(indicator)) {
      newAlerts.delete(indicator);
    } else {
      newAlerts.add(indicator);
    }
    setAlerts(newAlerts);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'released': return 'var(--text-3)';
      case 'today': return 'var(--amber)';
      case 'upcoming': return 'var(--cyan)';
      default: return 'var(--text-3)';
    }
  };

  const getSurpriseIcon = (surprise) => {
    if (!surprise) return <Minus size={12} />;
    if (surprise > 0) return <TrendingUp size={12} color="var(--green)" />;
    return <TrendingDown size={12} color="var(--red)" />;
  };

  return (
    <PanelChrome title="China Calendar" icon={Calendar} iconColor="var(--magenta)">
      <div style={{ padding: 4 }}>
      {/* Filter */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {['all', 'upcoming', 'high'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '3px 8px',
                fontSize: 10,
                borderRadius: 4,
                border: 'none',
                background: filter === f ? 'var(--primary)' : 'var(--surface-2)',
                color: filter === f ? 'white' : 'var(--text-2)',
                cursor: 'pointer',
                textTransform: 'capitalize',
              }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}

      <div style={{ display: 'flex', gap: 12, marginBottom: 12, fontSize: 9 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 6, height: 6, background: 'var(--amber)', borderRadius: '50%' }} />
          <span>Today</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 6, height: 6, background: 'var(--cyan)', borderRadius: '50%' }} />
          <span>Upcoming</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 6, height: 6, background: 'var(--text-3)', borderRadius: '50%' }} />
          <span>Released</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <AlertCircle size={10} color="var(--red)" />
          <span>High Impact</span>
        </div>
      </div>

      {/* Events List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {filteredEvents.map((event, idx) => (
          <div
            key={idx}
            style={{
              padding: '10px 12px',
              background: event.status === 'today' ? 'var(--amber-alpha)' : 'var(--surface-1)',
              borderRadius: 8,
              border: `1px solid ${event.status === 'today' ? 'var(--amber)' : 'var(--divider)'}`,
              opacity: event.status === 'released' ? 0.7 : 1,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: getStatusColor(event.status),
                  }}
                />
                <span style={{ fontSize: 12, fontWeight: 500 }}>{event.indicator}</span>
                {event.importance === 'High' && (
                  <AlertCircle size={12} color="var(--red)" />
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{event.displayDate}</span>
                <button
                  onClick={() => toggleAlert(event.indicator)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 2,
                    cursor: 'pointer',
                    opacity: alerts.has(event.indicator) ? 1 : 0.3,
                  }}
                >
                  <Bell size={12} color={alerts.has(event.indicator) ? 'var(--amber)' : 'var(--text-3)'} />
                </button>
              </div>
            </div>

            {/* Forecast / Actual */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginLeft: 16, marginTop: 4 }}>
              <div style={{ fontSize: 10 }}>
                <span style={{ color: 'var(--text-3)' }}>Forecast: </span>
                <span style={{ fontWeight: 500 }}>{event.forecast}</span>
              </div>

              {event.status === 'released' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10 }}>
                    <span style={{ color: 'var(--text-3)' }}>Actual: </span>
                    <span style={{ fontWeight: 600, color: event.surprise > 0 ? 'var(--green)' : event.surprise < 0 ? 'var(--red)' : 'var(--text-1)' }}>
                      {event.actual?.toFixed(1)}
                    </span>
                  </span>
                  {getSurpriseIcon(event.surprise)}
                </div>
              )}

              {event.status === 'today' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--amber)' }}>
                  <Clock size={10} />
                  <span>Due today</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Quick Reference */}
      <div
        style={{
          marginTop: 16,
          padding: 12,
          background: 'var(--surface-2)',
          borderRadius: 8,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 8, color: 'var(--text-2)' }}>
          Release Schedule Reference
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px' }}>
          {CHINA_CALENDAR.slice(0, 6).map((item, idx) => (
            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9 }}>
              <span style={{ color: 'var(--text-3)' }}>{item.indicator}</span>
              <span>{item.releaseDay}</span>
            </div>
          ))}
        </div>
      </div>

      {/* NBS Source */}
      <div style={{ marginTop: 12, fontSize: 9, color: 'var(--text-3)', textAlign: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
          <Info size={9} />
          <span>Illustrative schedule — dates and values are sample data, not a live feed</span>
        </div>
        <div style={{ marginTop: 4 }}>
          Source: National Bureau of Statistics of China (NBS) release calendar reference
        </div>
      </div>
    </div>
    </PanelChrome>
  );
}
