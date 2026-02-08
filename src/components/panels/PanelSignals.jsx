import { memo, useState, useMemo } from 'react';
import { Radio, TrendingUp, TrendingDown, Minus, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';

const actionColors = {
  buy: 'var(--green)',
  sell: 'var(--red)',
  hold: 'var(--text-3)',
};

const actionIcons = {
  buy: TrendingUp,
  sell: TrendingDown,
  hold: Minus,
};

const strengthBadge = {
  strong: { bg: 'rgba(255,255,255,0.1)', fontWeight: 700 },
  moderate: { bg: 'transparent', fontWeight: 500 },
  neutral: { bg: 'transparent', fontWeight: 400 },
};

const PanelSignals = memo(function PanelSignals({ mlState }) {
  const { signals, signalSummary } = mlState || {};
  const [filter, setFilter] = useState('all'); // all, buy, sell, hold
  const [sortBy, setSortBy] = useState('score'); // score, symbol
  const [expanded, setExpanded] = useState(null);

  const filteredSignals = useMemo(() => {
    let list = signals || [];
    if (filter !== 'all') {
      list = list.filter(s => s.action === filter);
    }
    if (sortBy === 'symbol') {
      list = [...list].sort((a, b) => a.symbol.localeCompare(b.symbol));
    } else {
      // Default sort by absolute score (strongest signals first)
      list = [...list].sort((a, b) => Math.abs(b.score) - Math.abs(a.score));
    }
    return list;
  }, [signals, filter, sortBy]);

  return (
    <PanelChrome title="Trading Signals" icon={Radio} iconColor="var(--green)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>

        {/* Filter Row */}
        <div style={{ display: 'flex', gap: 3, fontSize: 9 }}>
          {['all', 'buy', 'sell', 'hold'].map(f => (
            <button
              key={f}
              className="btn-ghost"
              onClick={() => setFilter(f)}
              style={{
                fontSize: 9, padding: '1px 6px', textTransform: 'capitalize',
                color: filter === f ? (f === 'all' ? 'var(--cyan)' : actionColors[f] || 'var(--text-1)') : 'var(--text-3)',
                borderBottom: filter === f ? '1px solid currentColor' : 'none',
              }}
            >
              {f} {f !== 'all' && signalSummary ? `(${f === 'buy' ? signalSummary.buys : f === 'sell' ? signalSummary.sells : signalSummary.holds})` : ''}
            </button>
          ))}
          <button
            className="btn-ghost"
            onClick={() => setSortBy(s => s === 'score' ? 'symbol' : 'score')}
            style={{ fontSize: 9, padding: '1px 6px', marginLeft: 'auto', color: 'var(--text-3)' }}
          >
            {sortBy === 'score' ? 'By Strength' : 'A-Z'}
          </button>
        </div>

        {/* Signal List */}
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {filteredSignals.length === 0 ? (
            <div style={{ fontSize: 10, color: 'var(--text-3)', textAlign: 'center', padding: 20 }}>
              {(signals || []).length === 0 ? 'Waiting for ML predictions...' : 'No signals match filter'}
            </div>
          ) : (
            filteredSignals.map(signal => {
              const ActionIcon = actionIcons[signal.action] || Minus;
              const color = actionColors[signal.action];
              const isExpanded = expanded === signal.symbol;
              const badge = strengthBadge[signal.strength] || strengthBadge.neutral;

              return (
                <div key={signal.symbol} style={{ borderBottom: '1px solid var(--border)', padding: '4px 0' }}>
                  <div
                    onClick={() => setExpanded(isExpanded ? null : signal.symbol)}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 10 }}
                  >
                    <ActionIcon size={12} style={{ color, flexShrink: 0 }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-1)', minWidth: 55 }}>
                      {signal.symbol}
                    </span>
                    <span style={{
                      color,
                      fontSize: 9,
                      textTransform: 'uppercase',
                      fontWeight: badge.fontWeight,
                      background: badge.bg,
                      padding: '0 4px',
                      borderRadius: 3,
                    }}>
                      {signal.strength} {signal.action}
                    </span>
                    {signal.anomaly && (
                      <AlertTriangle size={10} style={{ color: 'var(--amber)', flexShrink: 0 }} />
                    )}
                    <ScoreBar score={signal.score} style={{ flex: 1, minWidth: 40 }} />
                    <span style={{ color: 'var(--text-3)', fontSize: 9, fontFamily: 'var(--font-mono)' }}>
                      {signal.score > 0 ? '+' : ''}{Math.round(signal.score)}
                    </span>
                    {isExpanded ? <ChevronUp size={10} style={{ color: 'var(--text-3)' }} /> : <ChevronDown size={10} style={{ color: 'var(--text-3)' }} />}
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div style={{ paddingLeft: 18, paddingTop: 4, fontSize: 9, color: 'var(--text-3)', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <div style={{ display: 'flex', gap: 10 }}>
                        <span>Regime: <span style={{
                          color: signal.regime === 'bull' ? 'var(--green)' : signal.regime === 'bear' ? 'var(--red)' : 'var(--text-2)',
                          fontWeight: 500,
                        }}>{signal.regime}</span> ({Math.round((Number(signal.regimeConfidence) || 0) * 100)}%)</span>
                        <span>Tech Score: <span style={{ color: 'var(--cyan)' }}>{Math.round(signal.techScore)}/100</span></span>
                      </div>
                      {signal.pricePrediction && (
                        <div>
                          Direction: <span style={{
                            color: signal.pricePrediction.direction === 'up' ? 'var(--green)' : signal.pricePrediction.direction === 'down' ? 'var(--red)' : 'var(--text-2)',
                          }}>
                            {signal.pricePrediction.direction}
                          </span> (confidence: {Math.round((Number(signal.pricePrediction.confidence) || 0) * 100)}%)
                        </div>
                      )}
                      {signal.anomaly && (
                        <div style={{ color: 'var(--amber)' }}>Anomaly detected: {signal.anomaly}</div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Overall Market Bar */}
        {signalSummary && signalSummary.total > 0 && (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 4 }}>
            <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', gap: 1 }}>
              {signalSummary.buys > 0 && (
                <div style={{ flex: signalSummary.buys, background: 'var(--green)', borderRadius: 2 }} />
              )}
              {signalSummary.holds > 0 && (
                <div style={{ flex: signalSummary.holds, background: 'var(--bg-3)', borderRadius: 2 }} />
              )}
              {signalSummary.sells > 0 && (
                <div style={{ flex: signalSummary.sells, background: 'var(--red)', borderRadius: 2 }} />
              )}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, color: 'var(--text-3)', marginTop: 2 }}>
              <span>{signalSummary.buys} Buy</span>
              <span>{signalSummary.total} Total</span>
              <span>{signalSummary.sells} Sell</span>
            </div>
          </div>
        )}
      </div>
    </PanelChrome>
  );
});

function ScoreBar({ score, style }) {
  const pct = Math.abs(score);
  const isPositive = score >= 0;
  return (
    <div style={{ ...style, height: 4, background: 'var(--bg-3)', borderRadius: 2, position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute',
        [isPositive ? 'left' : 'right']: '50%',
        width: `${Math.min(50, pct / 2)}%`,
        height: '100%',
        background: isPositive ? 'var(--green)' : 'var(--red)',
        borderRadius: 2,
      }} />
      <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--text-3)', opacity: 0.3 }} />
    </div>
  );
}

PanelSignals.displayName = 'PanelSignals';
export default PanelSignals;
