import { memo, useState, useEffect, useCallback } from 'react';
import { CalendarCheck, RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchEarningsCalendar } from '../../services/api/stockApi';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

function getDateRange(offsetWeeks = 0) {
  const now = new Date();
  const start = new Date(now);
  start.setDate(start.getDate() + offsetWeeks * 7);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return {
    from: start.toISOString().split('T')[0],
    to: end.toISOString().split('T')[0],
  };
}

function generateMockEarnings() {
  const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX', 'AMD', 'CRM', 'ORCL', 'INTC', 'PYPL', 'ADBE', 'CSCO'];
  const now = new Date();
  return symbols.slice(0, 10).map((sym, i) => {
    const date = new Date(now);
    date.setDate(date.getDate() + Math.floor(i / 2));
    const eps = +(Math.random() * 5 + 0.5).toFixed(2);
    const hasActual = i < 4;
    return {
      symbol: sym,
      date: date.toISOString().split('T')[0],
      hour: i % 2 === 0 ? 'bmo' : 'amc',
      epsEstimate: eps,
      epsActual: hasActual ? +(eps + (Math.random() - 0.4) * 0.5).toFixed(2) : null,
      revenueEstimate: +(Math.random() * 50 + 10).toFixed(1) * 1e9,
      revenueActual: hasActual ? +(Math.random() * 55 + 10).toFixed(1) * 1e9 : null,
      quarter: Math.ceil((now.getMonth() + 1) / 3),
      year: now.getFullYear(),
    };
  });
}

const PanelEarningsCalendar = memo(() => {
  const [earnings, setEarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [weekOffset, setWeekOffset] = useState(0);

  const loadData = useCallback(async () => {
    setLoading(true);
    const { from, to } = getDateRange(weekOffset);
    try {
      const data = await fetchEarningsCalendar(from, to);
      if (data && data.length > 0) {
        setEarnings(data);
      } else {
        setEarnings(generateMockEarnings());
      }
    } catch {
      setEarnings(generateMockEarnings());
    }
    setLoading(false);
  }, [weekOffset]);

  useEffect(() => { loadData(); }, [loadData]);

  const { from, to } = getDateRange(weekOffset);

  // Group by date
  const grouped = {};
  for (const e of earnings) {
    if (!grouped[e.date]) grouped[e.date] = [];
    grouped[e.date].push(e);
  }

  return (
    <PanelChrome title="Earnings Calendar" icon={CalendarCheck} iconColor="var(--purple)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Controls */}
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <button className="btn-ghost" onClick={() => setWeekOffset(w => w - 1)} style={{ padding: '2px 6px', fontSize: 9 }}>
            &larr; Prev
          </button>
          <span style={{ fontSize: 10, color: 'var(--text-2)', flex: 1, textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
            {from} — {to}
          </span>
          <button className="btn-ghost" onClick={() => setWeekOffset(w => w + 1)} style={{ padding: '2px 6px', fontSize: 9 }}>
            Next &rarr;
          </button>
          <button className="btn-ghost" onClick={() => setWeekOffset(0)} style={{ padding: '2px 6px', fontSize: 9, color: weekOffset === 0 ? 'var(--cyan)' : undefined }}>
            This Week
          </button>
          <button className="btn-ghost" onClick={loadData} style={{ padding: '2px 4px', fontSize: 9 }}>
            <RefreshCw size={10} />
          </button>
        </div>

        {/* Earnings list */}
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {loading ? <PanelSkeleton /> : Object.entries(grouped).map(([date, items]) => (
            <div key={date} style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', padding: '3px 0', borderBottom: '1px solid var(--border-1)' }}>
                {new Date(date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
              </div>
              {items.map((e, i) => {
                const beat = e.epsActual != null && e.epsEstimate != null ? e.epsActual > e.epsEstimate : null;
                return (
                  <div key={`${e.symbol}-${i}`} style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '4px 6px',
                    borderBottom: '1px solid var(--border-1)', fontSize: 10,
                  }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-1)', width: 45 }}>
                      {e.symbol}
                    </span>
                    <span style={{ fontSize: 8, color: 'var(--text-4)', width: 28 }}>
                      {e.hour === 'bmo' ? 'Pre' : e.hour === 'amc' ? 'Post' : '-'}
                    </span>
                    <span style={{ color: 'var(--text-3)', flex: 1 }}>
                      EPS Est: ${e.epsEstimate?.toFixed(2) || '-'}
                    </span>
                    {e.epsActual != null ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: beat ? 'var(--green)' : 'var(--red)' }}>
                        {beat ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                        ${e.epsActual.toFixed(2)}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-4)', display: 'flex', alignItems: 'center', gap: 3 }}>
                        <Minus size={10} /> Pending
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
          {!loading && earnings.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-3)', fontSize: 11 }}>
              No earnings reports this week
            </div>
          )}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelEarningsCalendar.displayName = 'PanelEarningsCalendar';
export default PanelEarningsCalendar;
