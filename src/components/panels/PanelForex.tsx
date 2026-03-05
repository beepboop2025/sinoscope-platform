import { memo, useState, useMemo, useCallback, type ReactElement } from 'react';
import { DollarSign, Download, FileSpreadsheet } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import MiniSparkline from '../shared/MiniSparkline';
import SearchInput from '../shared/SearchInput';
import { priceChangeColor } from '../../constants/colors';
import { exportCsvFile } from '../../utils/export';
import { exportToXlsx } from '../../utils/excelExport';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import type { MarketTick } from '../../types/market';

interface PanelForexProps {
  data?: Record<string, MarketTick>;
}

// Module-level price history accumulator
const forexHistory = new Map<string, number[]>();

function accumulateForexHistory(data: Record<string, MarketTick>): Map<string, number[]> {
  for (const [pair, d] of Object.entries(data)) {
    const price = Number(d.price);
    if (!price) continue;
    const arr = forexHistory.get(pair) || [];
    if (arr.length === 0 || arr[arr.length - 1] !== price) {
      arr.push(price);
      if (arr.length > 20) arr.shift();
      forexHistory.set(pair, arr);
    }
  }
  return forexHistory;
}

const PanelForex = memo(({ data }: PanelForexProps): ReactElement => {
  const [filter, setFilter] = useState('');
  const [showExport, setShowExport] = useState(false);

  const history = useMemo(() => data ? new Map(accumulateForexHistory(data)) : new Map<string, number[]>(), [data]);

  const handleExportCsv = useCallback(() => {
    if (!data) return;
    const headers = ['Pair', 'Rate', 'Change%'];
    const rows = Object.entries(data).map(([pair, d]) => [
      pair, (Number(d.price) || 0).toFixed(4), (Number(d.changePct) || 0).toFixed(2),
    ]);
    exportCsvFile('forex.csv', headers, rows);
    setShowExport(false);
  }, [data]);

  const handleExportXlsx = useCallback(() => {
    if (!data) return;
    const headers = ['Pair', 'Rate', 'Change%'];
    const rows = Object.entries(data).map(([pair, d]) => ({
      Pair: pair, Rate: (Number(d.price) || 0).toFixed(4), 'Change%': (Number(d.changePct) || 0).toFixed(2),
    }));
    exportToXlsx('Forex', headers, rows, 'forex.xlsx');
    setShowExport(false);
  }, [data]);

  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Forex Rates" icon={DollarSign} iconColor="var(--cyan)"><PanelSkeleton /></PanelChrome>;
  }

  const pairs = Object.entries(data)
    .filter(([pair]) => !filter || pair.toLowerCase().includes(filter.toLowerCase()))
    .slice(0, 15);

  return (
    <PanelChrome title="Forex Rates" icon={DollarSign} iconColor="var(--cyan)">
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <SearchInput placeholder="Filter pairs..." onSearch={setFilter} debounceMs={150} />
        </div>
        <div style={{ position: 'relative' }}>
          <button className="btn-ghost" onClick={() => setShowExport(e => !e)} title="Export data" style={{ padding: '4px 8px' }}>
            <Download size={12} />
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
        <span style={{ fontSize: 9, color: 'var(--text-4)', whiteSpace: 'nowrap' }}>{pairs.length} pairs</span>
      </div>

      <table className="dense-table">
        <thead>
          <tr>
            <th>Pair</th>
            <th style={{ textAlign: 'center' }}>Trend</th>
            <th style={{ textAlign: 'right' }}>Rate</th>
            <th style={{ textAlign: 'right' }}>Change</th>
          </tr>
        </thead>
        <tbody>
          {pairs.map(([pair, d]) => {
            const sparkData = history.get(pair) || [];
            const isUp = (Number(d.changePct) || 0) >= 0;
            return (
              <tr key={pair}>
                <td style={{ color: 'var(--text-1)', fontWeight: 500, fontFamily: 'Outfit' }}>{pair}</td>
                <td style={{ textAlign: 'center' }}>
                  {sparkData.length > 1 && (
                    <MiniSparkline data={sparkData} color={isUp ? 'var(--green)' : 'var(--red)'} width={40} height={18} />
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>{(Number(d.price) || 0).toFixed(4)}</td>
                <td style={{ textAlign: 'right', color: priceChangeColor(d.changePct) }}>
                  {isUp ? '+' : ''}{(Number(d.changePct) || 0).toFixed(2)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </PanelChrome>
  );
});
PanelForex.displayName = "PanelForex";
export default PanelForex;
