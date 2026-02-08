import { memo } from 'react';
import { Gem } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import MiniSparkline from '../shared/MiniSparkline';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

const LABELS = {
  GASOLINE: { name: 'Gasoline', unit: '$/gal', color: '#f59e0b' },
  OIL_WTI: { name: 'WTI Crude', unit: '$/bbl', color: '#3b82f6' },
  OIL_BRENT: { name: 'Brent Crude', unit: '$/bbl', color: '#2563eb' },
  NATGAS: { name: 'Natural Gas', unit: '$/mmBtu', color: '#06d6e0' },
  COPPER: { name: 'Copper', unit: '$/lb', color: '#fb923c' },
};

const PanelCommodities = memo(({ data }) => {
  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Commodities" icon={Gem} iconColor="var(--amber)"><PanelSkeleton /></PanelChrome>;
  }

  return (
    <PanelChrome title="Commodities" icon={Gem} iconColor="var(--amber)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Object.entries(data).map(([key, d]) => {
          const label = LABELS[key] || { name: key, unit: '', color: 'var(--text-2)' };
          const history = d.history?.map(h => h.value) || [];
          return (
            <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: 'var(--bg-1)', borderRadius: 6, border: '1px solid var(--border-1)' }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-1)' }}>{label.name}</div>
                <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{label.unit}</div>
              </div>
              {history.length > 1 && <MiniSparkline data={history} color={label.color} width={60} height={24} />}
              <div className="mono" style={{ fontSize: 14, fontWeight: 600, color: label.color }}>
                {(Number(d.price) || 0).toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>
    </PanelChrome>
  );
});
PanelCommodities.displayName = "PanelCommodities";
export default PanelCommodities;
