import { memo } from 'react';
import { TrendingUp } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { priceChangeColor } from '../../constants/colors';
import { formatVolume } from '../../utils/formatters';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

const PanelStocks = memo(({ data }) => {
  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Stock Watchlist" icon={TrendingUp} iconColor="var(--blue)"><PanelSkeleton /></PanelChrome>;
  }

  const stocks = Object.entries(data);

  return (
    <PanelChrome title="Stock Watchlist" icon={TrendingUp} iconColor="var(--blue)">
      <table className="dense-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th style={{ textAlign: 'right' }}>Price</th>
            <th style={{ textAlign: 'right' }}>Chg%</th>
            <th style={{ textAlign: 'right' }}>Volume</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map(([sym, d]) => (
            <tr key={sym}>
              <td style={{ color: 'var(--text-1)', fontWeight: 500, fontFamily: 'Outfit' }}>{sym}</td>
              <td style={{ textAlign: 'right' }}>{(Number(d.price) || 0).toFixed(2)}</td>
              <td style={{ textAlign: 'right', color: priceChangeColor(d.changePct) }}>
                {(Number(d.changePct) || 0) >= 0 ? '+' : ''}{(Number(d.changePct) || 0).toFixed(2)}%
              </td>
              <td style={{ textAlign: 'right', color: 'var(--text-3)' }}>{formatVolume(d.volume)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </PanelChrome>
  );
});
PanelStocks.displayName = "PanelStocks";
export default PanelStocks;
