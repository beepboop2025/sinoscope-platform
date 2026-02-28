import { memo, useState, useEffect, useCallback, type ReactElement } from 'react';
import { LayoutGrid } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchSectorPerformance, getSectorPerformance } from '../../services/api/sentimentApi';

interface SectorData { symbol: string; name: string; changePct: number; weekPct: number; monthPct: number; }

function getHeatColor(val: number): string {
  if (val >= 3) return '#10b981'; if (val >= 1.5) return '#34d399'; if (val >= 0.5) return '#6ee7b7';
  if (val > -0.5) return 'var(--bg-3)'; if (val > -1.5) return '#fca5a5'; if (val > -3) return '#f87171';
  return '#ef4444';
}

function getTextColor(val: number): string {
  if (Math.abs(val) < 0.5) return 'var(--text-2)';
  return '#fff';
}

const PanelSectors = memo((): ReactElement => {
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [view, setView] = useState<string>('day');

  const loadData = useCallback(async () => {
    try {
      const real = await fetchSectorPerformance();
      if (real && (real as SectorData[]).length > 0) { setSectors(real as SectorData[]); return; }
    } catch { /* fallback */ }
    setSectors(getSectorPerformance() as SectorData[]);
  }, []);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 120000); return () => clearInterval(interval); }, [loadData]);

  const getVal = (s: SectorData): number => {
    if (view === 'week') return s.weekPct; if (view === 'month') return s.monthPct; return s.changePct;
  };

  const sorted = [...sectors].sort((a, b) => getVal(b) - getVal(a));

  return (
    <PanelChrome title="Sector Performance" icon={LayoutGrid} iconColor="var(--teal)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'flex', gap: 3 }}>
          {['day', 'week', 'month'].map(v => (
            <button key={v} className={view === v ? 'btn-primary' : 'btn-ghost'} onClick={() => setView(v)} style={{ padding: '2px 8px', fontSize: 9, textTransform: 'capitalize' }}>{v}</button>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4, flex: 1, minHeight: 0, overflow: 'auto' }}>
          {sorted.map(s => {
            const val = getVal(s);
            return (
              <div key={s.symbol} style={{ background: getHeatColor(val), borderRadius: 4, padding: '8px 6px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, minHeight: 50 }}>
                <div style={{ fontSize: 9, fontWeight: 600, color: getTextColor(val), textAlign: 'center' }}>{s.name}</div>
                <div style={{ fontSize: 8, color: getTextColor(val), opacity: 0.7 }}>{s.symbol}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: getTextColor(val), fontFamily: 'JetBrains Mono, monospace' }}>{val > 0 ? '+' : ''}{val.toFixed(2)}%</div>
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, color: 'var(--text-4)', padding: '2px 4px' }}>
          <span style={{ color: 'var(--red)' }}>Bearish</span><span>Neutral</span><span style={{ color: 'var(--green)' }}>Bullish</span>
        </div>
      </div>
    </PanelChrome>
  );
});
PanelSectors.displayName = 'PanelSectors';
export default PanelSectors;
