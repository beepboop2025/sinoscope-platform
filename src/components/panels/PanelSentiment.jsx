import { memo, useState, useEffect, useCallback } from 'react';
import { Gauge, RefreshCw } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchFearGreedIndex, getMockFearGreed } from '../../services/api/sentimentApi';

function getColor(val) {
  if (val <= 25) return 'var(--red)';
  if (val <= 45) return '#f97316';
  if (val <= 55) return 'var(--amber)';
  if (val <= 75) return '#84cc16';
  return 'var(--green)';
}

function GaugeArc({ value, size = 140 }) {
  const cx = size / 2, cy = size / 2 + 10;
  const r = size / 2 - 16;
  const startAngle = -180;
  const endAngle = 0;
  const range = endAngle - startAngle;
  const angle = startAngle + (value / 100) * range;

  const polarToCart = (a, radius) => ({
    x: cx + radius * Math.cos((a * Math.PI) / 180),
    y: cy + radius * Math.sin((a * Math.PI) / 180),
  });

  // Background arc
  const bgStart = polarToCart(startAngle, r);
  const bgEnd = polarToCart(endAngle, r);
  const bgPath = `M ${bgStart.x} ${bgStart.y} A ${r} ${r} 0 0 1 ${bgEnd.x} ${bgEnd.y}`;

  // Value arc
  const valEnd = polarToCart(angle, r);
  const largeArc = angle - startAngle > 180 ? 1 : 0;
  const valPath = `M ${bgStart.x} ${bgStart.y} A ${r} ${r} 0 ${largeArc} 1 ${valEnd.x} ${valEnd.y}`;

  // Needle
  const needleEnd = polarToCart(angle, r - 8);

  return (
    <svg width={size} height={size / 2 + 30} viewBox={`0 0 ${size} ${size / 2 + 30}`}>
      <path d={bgPath} fill="none" stroke="var(--bg-3)" strokeWidth={10} strokeLinecap="round" />
      <path d={valPath} fill="none" stroke={getColor(value)} strokeWidth={10} strokeLinecap="round" />
      <line x1={cx} y1={cy} x2={needleEnd.x} y2={needleEnd.y} stroke="var(--text-1)" strokeWidth={2} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={4} fill="var(--text-1)" />
      <text x={cx} y={cy - 14} textAnchor="middle" fontSize={28} fontWeight={700} fill={getColor(value)} fontFamily="JetBrains Mono, monospace">
        {value}
      </text>
    </svg>
  );
}

const PanelSentiment = memo(() => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchFearGreedIndex();
      setData(result || getMockFearGreed());
    } catch {
      setData(getMockFearGreed());
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const current = data?.[0];
  const history = data?.slice(1, 8) || [];

  return (
    <PanelChrome title="Fear & Greed Index" icon={Gauge} iconColor="var(--amber)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%', minHeight: 0, alignItems: 'center' }}>
        {loading && !current ? (
          <div style={{ padding: 20, color: 'var(--text-4)', fontSize: 11 }}>Loading...</div>
        ) : current ? (
          <>
            <GaugeArc value={current.value} />
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: getColor(current.value) }}>
                {current.label}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 2 }}>
                Crypto market sentiment
              </div>
            </div>

            {/* History sparkline */}
            <div style={{ width: '100%', marginTop: 'auto' }}>
              <div style={{ fontSize: 9, color: 'var(--text-4)', marginBottom: 4 }}>7-day history</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {history.map((h, i) => (
                  <div key={i} style={{ flex: 1, textAlign: 'center' }}>
                    <div style={{
                      height: 24, display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
                    }}>
                      <div style={{
                        width: '80%', height: `${(h.value / 100) * 24}px`,
                        background: getColor(h.value), borderRadius: 2, minHeight: 2,
                      }} />
                    </div>
                    <div style={{ fontSize: 8, color: 'var(--text-4)', marginTop: 2 }}>{h.value}</div>
                  </div>
                ))}
              </div>
            </div>

            <button
              className="btn-ghost"
              onClick={loadData}
              disabled={loading}
              style={{ padding: '2px 8px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3, alignSelf: 'flex-end' }}
            >
              <RefreshCw size={9} /> Refresh
            </button>
          </>
        ) : null}
      </div>
    </PanelChrome>
  );
});
PanelSentiment.displayName = 'PanelSentiment';
export default PanelSentiment;
