import { memo } from 'react';
import { BarChart3 } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import StatBox from '../shared/StatBox';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

const ECON_LABELS = {
  GDP: { label: 'GDP Growth', color: 'var(--green)', icon: BarChart3 },
  CPI: { label: 'CPI Inflation', color: 'var(--red)' },
  UNEMPLOYMENT: { label: 'Unemployment', color: 'var(--amber)' },
  FED_RATE: { label: 'Fed Rate', color: 'var(--blue)' },
  PMI: { label: 'Mfg PMI', color: 'var(--teal)' },
  RETAIL_SALES: { label: 'Retail Sales', color: 'var(--purple)' },
  TRADE_BALANCE: { label: 'Trade Balance', color: 'var(--orange)' },
};

const PanelEconomic = memo(({ data }) => {
  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Economic Indicators" icon={BarChart3} iconColor="var(--teal)"><PanelSkeleton /></PanelChrome>;
  }

  return (
    <PanelChrome title="Economic Indicators — US" icon={BarChart3} iconColor="var(--teal)">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 8 }}>
        {Object.entries(data).map(([key, d]) => {
          const label = ECON_LABELS[key] || { label: key, color: 'var(--text-2)' };
          return (
            <StatBox
              key={key}
              label={label.label}
              value={`${(Number(d.value) || 0).toFixed(1)}${d.unit || ''}`}
              sub={d.date}
              color={label.color}
              small
            />
          );
        })}
      </div>
    </PanelChrome>
  );
});
PanelEconomic.displayName = "PanelEconomic";
export default PanelEconomic;
