/**
 * PanelChinaCalendar - China Economic Data Release Calendar
 * Shows upcoming and recent economic indicators from NBS China
 */
import { useState, useMemo } from 'react';
import { Calendar, Clock, AlertCircle, TrendingUp, TrendingDown, Minus, Bell } from 'lucide-react';
import { CHINA_CALENDAR } from '../../../constants/china';

// Generate mock calendar events for the next 30 days
const generateCalendarEvents = () => {
  const events = [];
  const today = new Date();
  
  // Add some past and future events
  const eventTemplates = [
    { indicator: 'PMI Manufacturing', type: 'pmi', importance: 'High', forecast: 49.8, previous: 49.0 },
    { indicator: 'Trade Balance', type: 'trade', importance: 'High', forecast: 75.2, previous: 70.8 },
    { indicator: 'CPI', type: 'inflation', importance: 'High', forecast: 0.3, previous: 0.2 },
    { indicator: 'PPI', type: 'inflation', importance: 'Medium', forecast: -2.5, previous: -2.7 },
    { indicator: 'New Yuan Loans', type: 'credit', importance: 'High', forecast: 1200, previous: 1100 },
    { indicator: 'FX Reserves', type: 'reserves', importance: 'Medium', forecast: 32300, previous: 32258 },
    { indicator: 'Industrial Production', type: 'production', importance: 'High', forecast: 5.2, previous: 5.0 },
    { indicator: 'Retail Sales', type: 'consumption', importance: 'Medium', forecast: 7.5, previous: 7.2 },
    { indicator: 'GDP', type: 'growth', importance: 'High', forecast: 5.2, previous: 5.3 },
    { indicator: 'LPR', type: 'rates', importance: 'High', forecast: 3.45, previous: 3.45 },
  ];

  // Distribute events across dates
  eventTemplates.forEach((template, idx) => {
    const date = new Date(today);
    date.setDate(today.getDate() + (idx * 3) - 10); // Mix of past and future
    
    // Determine status
    let status = 'upcoming';
    let actual = null;
    if (date < today) {
      status = 'released';
      // Generate actual value near forecast
      actual = template.forecast + (Math.random() - 0.5) * 0.5;
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
    <div className="panel-content" style={{ padding: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Calendar size={18} color="var(--magenta)" />
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>China Calendar</h3>
        </div>
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
        Source: National Bureau of Statistics of China (NBS) • All times Beijing (CST)
      </div>
    </div>
  );
}
