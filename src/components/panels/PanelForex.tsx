import { memo, type ReactElement } from 'react';
import { DollarSign } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { priceChangeColor } from '../../constants/colors';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import type { MarketTick } from '../../types/market';

interface PanelForexProps {
  data?: Record<string, MarketTick>;
}

const PanelForex = memo(({ data }: PanelForexProps): ReactElement => {
  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Forex Rates" icon={DollarSign} iconColor="var(--cyan)"><PanelSkeleton /></PanelChrome>;
  }

  const pairs = Object.entries(data).slice(0, 15);

  return (
    <PanelChrome title="Forex Rates" icon={DollarSign} iconColor="var(--cyan)">
      <table className="dense-table">
        <thead>
          <tr>
            <th>Pair</th>
            <th style={{ textAlign: 'right' }}>Rate</th>
            <th style={{ textAlign: 'right' }}>Change</th>
          </tr>
        </thead>
        <tbody>
          {pairs.map(([pair, d]) => (
            <tr key={pair}>
              <td style={{ color: 'var(--text-1)', fontWeight: 500, fontFamily: 'Outfit' }}>{pair}</td>
              <td style={{ textAlign: 'right' }}>{(Number(d.price) || 0).toFixed(4)}</td>
              <td style={{ textAlign: 'right', color: priceChangeColor(d.changePct) }}>
                {(Number(d.changePct) || 0) >= 0 ? '+' : ''}{(Number(d.changePct) || 0).toFixed(2)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </PanelChrome>
  );
});
PanelForex.displayName = "PanelForex";
export default PanelForex;
