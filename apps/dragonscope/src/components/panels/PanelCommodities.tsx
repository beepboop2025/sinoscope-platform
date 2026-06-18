import { memo, useState, useCallback, type ReactElement } from 'react';
import { Gem, Download, FileSpreadsheet } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import MiniSparkline from '../shared/MiniSparkline';
import { exportCsvFile } from '../../utils/export';
import { exportToXlsx } from '../../utils/excelExport';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

interface CommodityLabel {
  name: string;
  unit: string;
  color: string;
}

const LABELS: Record<string, CommodityLabel> = {
  GASOLINE: { name: 'Gasoline', unit: '$/gal', color: '#f59e0b' },
  OIL_WTI: { name: 'WTI Crude', unit: '$/bbl', color: '#3b82f6' },
  OIL_BRENT: { name: 'Brent Crude', unit: '$/bbl', color: '#2563eb' },
  NATGAS: { name: 'Natural Gas', unit: '$/mmBtu', color: '#06d6e0' },
  COPPER: { name: 'Copper', unit: '$/lb', color: '#fb923c' },
};

interface CommodityData {
  price?: number;
  history?: Array<{ value: number }>;
}

interface PanelCommoditiesProps {
  data?: Record<string, CommodityData>;
}

const PanelCommodities = memo(({ data }: PanelCommoditiesProps): ReactElement => {
  const [showExport, setShowExport] = useState(false);

  const handleExportCsv = useCallback(() => {
    if (!data) return;
    const headers = ['Commodity', 'Unit', 'Price'];
    const rows = Object.entries(data).map(([key, d]) => {
      const label = LABELS[key] || { name: key, unit: '', color: '' };
      return [label.name, label.unit, (Number(d.price) || 0).toFixed(2)];
    });
    exportCsvFile('commodities.csv', headers, rows);
    setShowExport(false);
  }, [data]);

  const handleExportXlsx = useCallback(() => {
    if (!data) return;
    const headers = ['Commodity', 'Unit', 'Price'];
    const rows = Object.entries(data).map(([key, d]) => {
      const label = LABELS[key] || { name: key, unit: '', color: '' };
      return { Commodity: label.name, Unit: label.unit, Price: (Number(d.price) || 0).toFixed(2) };
    });
    exportToXlsx('Commodities', headers, rows, 'commodities.xlsx');
    setShowExport(false);
  }, [data]);

  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Commodities" icon={Gem} iconColor="var(--amber)"><PanelSkeleton /></PanelChrome>;
  }

  return (
    <PanelChrome title="Commodities" icon={Gem} iconColor="var(--amber)">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6, position: 'relative' }}>
        <button className="btn-ghost" onClick={() => setShowExport(e => !e)} title="Export data" style={{ padding: '3px 6px' }}>
          <Download size={11} />
        </button>
        {showExport && (
          <div style={{
            position: 'absolute', top: '100%', right: 0, marginTop: 4, background: 'var(--glass-bg-heavy)',
            border: '1px solid var(--border-2)', borderRadius: 'var(--radius-md)', padding: 4, zIndex: 10,
            display: 'flex', flexDirection: 'column', gap: 2, minWidth: 100,
          }}>
            <button className="btn-ghost" onClick={handleExportCsv} style={{ padding: '4px 8px', fontSize: 10, width: '100%', justifyContent: 'flex-start' }}>
              <Download size={10} /> CSV
            </button>
            <button className="btn-ghost" onClick={handleExportXlsx} style={{ padding: '4px 8px', fontSize: 10, width: '100%', justifyContent: 'flex-start' }}>
              <FileSpreadsheet size={10} /> Excel
            </button>
          </div>
        )}
      </div>
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
