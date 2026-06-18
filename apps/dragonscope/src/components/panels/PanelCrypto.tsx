import { memo, useState, useMemo, useCallback, type ReactElement } from 'react';
import { Coins, Download, FileSpreadsheet } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import MiniSparkline from '../shared/MiniSparkline';
import SearchInput from '../shared/SearchInput';
import { priceChangeColor } from '../../constants/colors';
import { formatPrice, formatVolume } from '../../utils/formatters';
import { exportCsvFile } from '../../utils/export';
import { exportToXlsx } from '../../utils/excelExport';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

interface CryptoData {
  price?: number;
  changePct?: number;
  marketCap?: number;
  name?: string;
}

interface PanelCryptoProps {
  data?: Record<string, CryptoData>;
}

// Module-level price history accumulator
const cryptoHistory = new Map<string, number[]>();

function accumulateCryptoHistory(data: Record<string, CryptoData>): Map<string, number[]> {
  for (const [sym, d] of Object.entries(data)) {
    const price = Number(d.price);
    if (!price) continue;
    const arr = cryptoHistory.get(sym) || [];
    if (arr.length === 0 || arr[arr.length - 1] !== price) {
      arr.push(price);
      if (arr.length > 20) arr.shift();
      cryptoHistory.set(sym, arr);
    }
  }
  return cryptoHistory;
}

const PanelCrypto = memo(({ data }: PanelCryptoProps): ReactElement => {
  const [filter, setFilter] = useState('');
  const [showExport, setShowExport] = useState(false);

  const history = useMemo(() => data ? new Map(accumulateCryptoHistory(data)) : new Map<string, number[]>(), [data]);

  const handleExportCsv = useCallback(() => {
    if (!data) return;
    const headers = ['Coin', 'Name', 'Price', '24h Change%', 'Market Cap'];
    const rows = Object.entries(data).map(([sym, d]) => [
      sym, d.name || '', `$${formatPrice(d.price)}`, (Number(d.changePct) || 0).toFixed(2), `$${formatVolume(d.marketCap)}`,
    ]);
    exportCsvFile('crypto.csv', headers, rows);
    setShowExport(false);
  }, [data]);

  const handleExportXlsx = useCallback(() => {
    if (!data) return;
    const headers = ['Coin', 'Name', 'Price', '24h Change%', 'Market Cap'];
    const rows = Object.entries(data).map(([sym, d]) => ({
      Coin: sym, Name: d.name || '', Price: `$${formatPrice(d.price)}`,
      '24h Change%': (Number(d.changePct) || 0).toFixed(2), 'Market Cap': `$${formatVolume(d.marketCap)}`,
    }));
    exportToXlsx('Crypto', headers, rows, 'crypto.xlsx');
    setShowExport(false);
  }, [data]);

  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Crypto Markets" icon={Coins} iconColor="var(--orange)"><PanelSkeleton /></PanelChrome>;
  }

  const coins = Object.entries(data).filter(([sym, d]) =>
    !filter || sym.toLowerCase().includes(filter.toLowerCase()) || (d.name || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <PanelChrome title="Crypto Markets" icon={Coins} iconColor="var(--orange)">
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <SearchInput placeholder="Filter coins..." onSearch={setFilter} debounceMs={150} />
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
        <span style={{ fontSize: 9, color: 'var(--text-4)', whiteSpace: 'nowrap' }}>{coins.length} coins</span>
      </div>

      <table className="dense-table">
        <thead>
          <tr>
            <th>Coin</th>
            <th style={{ textAlign: 'center' }}>Trend</th>
            <th style={{ textAlign: 'right' }}>Price</th>
            <th style={{ textAlign: 'right' }}>24h</th>
            <th style={{ textAlign: 'right' }}>MCap</th>
          </tr>
        </thead>
        <tbody>
          {coins.map(([sym, d]) => {
            const sparkData = history.get(sym) || [];
            const isUp = (Number(d.changePct) || 0) >= 0;
            return (
              <tr key={sym}>
                <td>
                  <div style={{ fontWeight: 500, color: 'var(--text-1)', fontFamily: 'Outfit' }}>{sym}</div>
                  {d.name && <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{d.name}</div>}
                </td>
                <td style={{ textAlign: 'center' }}>
                  {sparkData.length > 1 && (
                    <MiniSparkline data={sparkData} color={isUp ? 'var(--green)' : 'var(--red)'} width={40} height={18} />
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>${formatPrice(d.price)}</td>
                <td style={{ textAlign: 'right', color: priceChangeColor(d.changePct) }}>
                  {isUp ? '+' : ''}{(Number(d.changePct) || 0).toFixed(2)}%
                </td>
                <td style={{ textAlign: 'right', color: 'var(--text-3)' }}>${formatVolume(d.marketCap)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </PanelChrome>
  );
});
PanelCrypto.displayName = "PanelCrypto";
export default PanelCrypto;
