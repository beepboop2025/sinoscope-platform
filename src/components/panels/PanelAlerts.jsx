import { memo, useState, useEffect, useRef } from 'react';
import { Bell, AlertTriangle, TrendingUp, TrendingDown, Volume2, Activity, Trash2, Zap, BarChart3 } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';

const SEVERITY_COLORS = { critical: 'var(--red)', high: 'var(--orange)', medium: 'var(--amber)', low: 'var(--text-3)' };
const TYPE_ICONS = { price_spike: TrendingUp, price_drop: TrendingDown, volume_spike: Volume2, anomaly: AlertTriangle, ml_signal: Activity, pattern: Zap, technical: BarChart3, breakout: TrendingUp, breakdown: TrendingDown, bearish_divergence: TrendingDown, bullish_divergence: TrendingUp, default: Bell };

const STORAGE_KEY = 'dragonscope_alerts';

function loadAlerts() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveAlerts(alerts) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(alerts.slice(0, 100)));
  } catch { /* quota */ }
}

function timeAgo(ts) {
  const mins = Math.round((Date.now() - ts) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

const PanelAlerts = memo(({ alerts: externalAlerts = [], marketData, mlState, patternEvents = [], technicalSignals = {} }) => {
  const [alerts, setAlerts] = useState(loadAlerts);
  const [filter, setFilter] = useState('all');
  const prevRef = useRef({});

  // Generate alerts from market data
  useEffect(() => {
    if (!marketData) return;
    const prev = prevRef.current;
    const newAlerts = [];

    // Stock alerts — significant moves (>3%)
    for (const [sym, d] of Object.entries(marketData.stocks || {})) {
      const pct = Number(d?.changePct) || 0;
      const absPct = Math.abs(pct);
      if (absPct < 3) continue;
      const key = `stock_${sym}_${Math.floor(Date.now() / 300000)}`; // dedup per 5 min
      if (prev[key]) continue;
      prev[key] = true;

      const severity = absPct >= 8 ? 'critical' : absPct >= 5 ? 'high' : 'medium';
      newAlerts.push({
        id: key,
        type: pct > 0 ? 'price_spike' : 'price_drop',
        severity,
        symbol: sym,
        message: `${sym} ${pct > 0 ? 'surged' : 'dropped'} ${absPct.toFixed(1)}% to $${(Number(d.price) || 0).toFixed(2)}`,
        timestamp: Date.now(),
      });
    }

    // Crypto alerts — significant moves (>5%)
    for (const [sym, d] of Object.entries(marketData.crypto || {})) {
      const pct = Number(d?.changePct) || 0;
      const absPct = Math.abs(pct);
      if (absPct < 5) continue;
      const key = `crypto_${sym}_${Math.floor(Date.now() / 300000)}`;
      if (prev[key]) continue;
      prev[key] = true;

      const severity = absPct >= 15 ? 'critical' : absPct >= 10 ? 'high' : 'medium';
      newAlerts.push({
        id: key,
        type: pct > 0 ? 'price_spike' : 'price_drop',
        severity,
        symbol: sym.replace('USDT', ''),
        message: `${sym.replace('USDT', '')} ${pct > 0 ? 'rallied' : 'fell'} ${absPct.toFixed(1)}% to $${(Number(d.price) || 0).toLocaleString()}`,
        timestamp: Date.now(),
      });
    }

    if (newAlerts.length > 0) {
      setAlerts(prev2 => {
        const next = [...newAlerts, ...prev2].slice(0, 100);
        saveAlerts(next);
        return next;
      });
    }
    prevRef.current = prev;
  }, [marketData]);

  // Generate alerts from ML anomalies
  useEffect(() => {
    if (!mlState?.anomalies) return;
    const prev = prevRef.current;

    const newAlerts = [];
    for (const a of mlState.anomalies.slice(0, 5)) {
      const key = `ml_${a.symbol}_${Math.floor(a.timestamp / 300000)}`;
      if (prev[key]) continue;
      prev[key] = true;

      newAlerts.push({
        id: key,
        type: 'anomaly',
        severity: a.severity,
        symbol: a.symbol,
        message: `ML anomaly: ${a.symbol} ${a.direction} (z-score: ${(Number(a.zScore) || 0).toFixed(1)})`,
        timestamp: a.timestamp,
      });
    }

    // Strong ML signals
    const strongBuys = mlState.signalSummary?.strongBuys || [];
    const strongSells = mlState.signalSummary?.strongSells || [];
    for (const sym of strongBuys) {
      const key = `signal_buy_${sym}_${Math.floor(Date.now() / 600000)}`;
      if (prev[key]) continue;
      prev[key] = true;
      newAlerts.push({
        id: key, type: 'ml_signal', severity: 'medium', symbol: sym,
        message: `Strong BUY signal for ${sym}`, timestamp: Date.now(),
      });
    }
    for (const sym of strongSells) {
      const key = `signal_sell_${sym}_${Math.floor(Date.now() / 600000)}`;
      if (prev[key]) continue;
      prev[key] = true;
      newAlerts.push({
        id: key, type: 'ml_signal', severity: 'high', symbol: sym,
        message: `Strong SELL signal for ${sym}`, timestamp: Date.now(),
      });
    }

    if (newAlerts.length > 0) {
      setAlerts(prev2 => {
        const next = [...newAlerts, ...prev2].slice(0, 100);
        saveAlerts(next);
        return next;
      });
    }
  }, [mlState?.anomalies, mlState?.signalSummary]);

  // Generate alerts from PatternEngine events
  useEffect(() => {
    if (!patternEvents || patternEvents.length === 0) return;
    const prev = prevRef.current;
    const newAlerts = [];

    for (const pe of patternEvents.slice(0, 10)) {
      const key = `pattern_${pe.type}_${pe.symbol}_${Math.floor(pe.timestamp / 300000)}`;
      if (prev[key]) continue;
      prev[key] = true;

      newAlerts.push({
        id: key,
        type: pe.type,
        severity: pe.severity || 'medium',
        symbol: pe.symbol,
        message: pe.message,
        timestamp: pe.timestamp,
      });
    }

    if (newAlerts.length > 0) {
      setAlerts(prev2 => {
        const next = [...newAlerts, ...prev2].slice(0, 100);
        saveAlerts(next);
        return next;
      });
    }
  }, [patternEvents]);

  // Generate alerts from TechnicalEngine signals
  useEffect(() => {
    if (!technicalSignals || Object.keys(technicalSignals).length === 0) return;
    const prev = prevRef.current;
    const newAlerts = [];

    for (const [sym, sigList] of Object.entries(technicalSignals)) {
      for (const sig of sigList) {
        const key = `tech_${sym}_${sig.type}_${Math.floor(Date.now() / 600000)}`;
        if (prev[key]) continue;
        prev[key] = true;

        const severity = sig.strength === 'high' ? 'high' : sig.strength === 'medium' ? 'medium' : 'low';
        newAlerts.push({
          id: key,
          type: 'technical',
          severity,
          symbol: sym,
          message: `${sym} ${sig.indicator}: ${sig.type.replace(/_/g, ' ')}`,
          timestamp: Date.now(),
        });
      }
    }

    if (newAlerts.length > 0) {
      setAlerts(prev2 => {
        const next = [...newAlerts, ...prev2].slice(0, 100);
        saveAlerts(next);
        return next;
      });
    }
  }, [technicalSignals]);

  // Merge external alerts
  useEffect(() => {
    if (externalAlerts.length > 0) {
      setAlerts(prev => {
        const existingIds = new Set(prev.map(a => a.id));
        const newOnes = externalAlerts.filter(a => !existingIds.has(a.id));
        if (newOnes.length === 0) return prev;
        const next = [...newOnes, ...prev].slice(0, 100);
        saveAlerts(next);
        return next;
      });
    }
  }, [externalAlerts]);

  const clearAlerts = () => {
    setAlerts([]);
    saveAlerts([]);
    prevRef.current = {};
  };

  const filtered = filter === 'all' ? alerts : alerts.filter(a => a.severity === filter);

  return (
    <PanelChrome title="Alerts" icon={Bell} iconColor="var(--amber)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {['all', 'critical', 'high', 'medium'].map(f => (
            <button key={f} className="btn-ghost" onClick={() => setFilter(f)}
              style={{ padding: '2px 6px', fontSize: 9, textTransform: 'capitalize',
                color: filter === f ? (f === 'all' ? 'var(--cyan)' : SEVERITY_COLORS[f]) : 'var(--text-3)' }}>
              {f} {f !== 'all' ? `(${alerts.filter(a => a.severity === f).length})` : `(${alerts.length})`}
            </button>
          ))}
          {alerts.length > 0 && (
            <button className="btn-ghost" onClick={clearAlerts} style={{ marginLeft: 'auto', fontSize: 9, padding: '2px 4px', color: 'var(--text-3)' }}>
              <Trash2 size={10} />
            </button>
          )}
        </div>

        <div style={{ flex: 1, overflow: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {filtered.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-3)', fontSize: 11 }}>
              {alerts.length === 0 ? 'Monitoring markets for alerts...' : 'No alerts match this filter.'}
            </div>
          )}
          {filtered.map((a) => {
            const Icon = TYPE_ICONS[a.type] || TYPE_ICONS.default;
            const color = SEVERITY_COLORS[a.severity] || 'var(--text-3)';
            return (
              <div key={a.id} style={{ display: 'flex', gap: 8, padding: '5px 8px', background: 'var(--bg-1)', borderRadius: 5, border: '1px solid var(--border-1)', borderLeft: `3px solid ${color}` }}>
                <Icon size={13} color={color} style={{ flexShrink: 0, marginTop: 1 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-1)', lineHeight: 1.3 }}>{a.message}</div>
                  <div style={{ fontSize: 8, color: 'var(--text-4)', marginTop: 2, display: 'flex', gap: 6 }}>
                    {a.symbol && <span style={{ fontFamily: 'var(--font-mono)' }}>{a.symbol}</span>}
                    <span>{timeAgo(a.timestamp)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelAlerts.displayName = "PanelAlerts";
export default PanelAlerts;
