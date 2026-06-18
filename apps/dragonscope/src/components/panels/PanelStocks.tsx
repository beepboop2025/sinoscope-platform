import { memo, useState, useMemo, useCallback, type ReactElement } from 'react';
import { TrendingUp, Download, FileSpreadsheet } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import MiniSparkline from '../shared/MiniSparkline';
import SearchInput from '../shared/SearchInput';
import { priceChangeColor } from '../../constants/colors';
import { formatVolume } from '../../utils/formatters';
import { exportCsvFile } from '../../utils/export';
import { exportToXlsx } from '../../utils/excelExport';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import type { MarketTick } from '../../types/market';

const SIGNAL_COLORS: Record<string, string> = {
  oversold: 'var(--green)', overbought: 'var(--red)',
  bullish_crossover: 'var(--green)', bearish_crossover: 'var(--red)',
  below_lower_band: 'var(--green)', above_upper_band: 'var(--red)',
};

const SIGNAL_LABELS: Record<string, string> = {
  oversold: 'Oversold', overbought: 'Overbought',
  bullish_crossover: 'MACD Bull', bearish_crossover: 'MACD Bear',
  below_lower_band: 'BB Low', above_upper_band: 'BB High',
};

interface PanelStocksProps {
  data?: Record<string, MarketTick>;
  signals?: Record<string, Array<{ type: string }>>;
}

// Module-level price history accumulator (avoids ref/state lint issues)
const stocksHistory = new Map<string, number[]>();

function accumulateHistory(data: Record<string, MarketTick>): Map<string, number[]> {
  for (const [sym, d] of Object.entries(data)) {
    const price = Number(d.price);
    if (!price) continue;
    const arr = stocksHistory.get(sym) || [];
    if (arr.length === 0 || arr[arr.length - 1] !== price) {
      arr.push(price);
      if (arr.length > 20) arr.shift();
      stocksHistory.set(sym, arr);
    }
  }
  return stocksHistory;
}

const PanelStocks = memo(({ data, signals = {} }: PanelStocksProps): ReactElement => {
  const [filter, setFilter] = useState('');
  const [showExport, setShowExport] = useState(false);

  // Accumulate and snapshot price history for sparklines
  const history = useMemo(() => data ? new Map(accumulateHistory(data)) : new Map<string, number[]>(), [data]);

  const handleExportCsv = useCallback(() => {
    if (!data) return;
    const headers = ['Symbol', 'Price', 'Change%', 'Volume'];
    const rows = Object.entries(data).map(([sym, d]) => [
      sym, (Number(d.price) || 0).toFixed(2), (Number(d.changePct) || 0).toFixed(2), String(d.volume || 0),
    ]);
    exportCsvFile('stocks.csv', headers, rows);
    setShowExport(false);
  }, [data]);

  const handleExportXlsx = useCallback(() => {
    if (!data) return;
    const headers = ['Symbol', 'Price', 'Change%', 'Volume'];
    const rows = Object.entries(data).map(([sym, d]) => ({
      Symbol: sym, Price: (Number(d.price) || 0).toFixed(2),
      'Change%': (Number(d.changePct) || 0).toFixed(2), Volume: String(d.volume || 0),
    }));
    exportToXlsx('Stocks', headers, rows, 'stocks.xlsx');
    setShowExport(false);
  }, [data]);

  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Stock Watchlist" icon={TrendingUp} iconColor="var(--blue)"><PanelSkeleton /></PanelChrome>;
  }

  const stocks = Object.entries(data).filter(([sym]) =>
    !filter || sym.toLowerCase().includes(filter.toLowerCase())
  );
  const hasSignals = Object.keys(signals).length > 0;

  return (
    <PanelChrome title="Stock Watchlist" icon={TrendingUp} iconColor="var(--blue)">
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <SearchInput placeholder="Filter symbols..." onSearch={setFilter} debounceMs={150} />
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
        <span style={{ fontSize: 9, color: 'var(--text-4)', whiteSpace: 'nowrap' }}>{stocks.length} rows</span>
      </div>

      <table className="dense-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th style={{ textAlign: 'center' }}>Trend</th>
            <th style={{ textAlign: 'right' }}>Price</th>
            <th style={{ textAlign: 'right' }}>Chg%</th>
            <th style={{ textAlign: 'right' }}>Volume</th>
            {hasSignals && <th style={{ textAlign: 'right' }}>Signal</th>}
          </tr>
        </thead>
        <tbody>
          {stocks.map(([sym, d]) => {
            const symSignals = signals[sym] || [];
            const topSignal = symSignals[0];
            const sparkData = history.get(sym) || [];
            const isUp = (Number(d.changePct) || 0) >= 0;
            return (
              <tr key={sym}>
                <td style={{ color: 'var(--text-1)', fontWeight: 500, fontFamily: 'Outfit' }}>{sym}</td>
                <td style={{ textAlign: 'center' }}>
                  {sparkData.length > 1 && (
                    <MiniSparkline data={sparkData} color={isUp ? 'var(--green)' : 'var(--red)'} width={40} height={18} />
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>{(Number(d.price) || 0).toFixed(2)}</td>
                <td style={{ textAlign: 'right', color: priceChangeColor(d.changePct) }}>
                  {isUp ? '+' : ''}{(Number(d.changePct) || 0).toFixed(2)}%
                </td>
                <td style={{ textAlign: 'right', color: 'var(--text-3)' }}>{formatVolume(d.volume)}</td>
                {hasSignals && (
                  <td style={{ textAlign: 'right', fontSize: 8, color: topSignal ? (SIGNAL_COLORS[topSignal.type] || 'var(--text-3)') : 'var(--text-4)' }}>
                    {topSignal ? (SIGNAL_LABELS[topSignal.type] || topSignal.type) : '-'}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </PanelChrome>
  );
});
PanelStocks.displayName = "PanelStocks";
export default PanelStocks;
